"""
Day 23 — API 完善 + 生产级特性 + 测试套件
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Day 22 我们搭建了 FastAPI 骨架，5 个端点都能跑通。
今天把 API 打磨到「生产可交付」的级别。

学完今天你会：
  ✅ 会话管理：多轮对话历史，session 生命周期管理
  ✅ 结构化日志：请求追踪、耗时统计、工具调用链记录
  ✅ 限流保护：简单令牌桶，防止滥用
  ✅ 错误处理：统一错误响应格式，友好提示
  ✅ 测试套件：pytest + httpx 覆盖所有端点
  ✅ 理解「原型 vs 生产」的差距在哪

启动方式：
  uvicorn day23_api_refinement:app --reload --host 0.0.0.0 --port 8000

测试方式：
  pytest day23_api_refinement.py -v
"""

import sys, os, json, math, io, time as _time
sys.stdout.reconfigure(encoding='utf-8')

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
import uvicorn

from config import client as llm_client, MODEL as LLM_MODEL
import chromadb, datetime as _dt, requests
from collections import defaultdict
import uuid
import logging

# ============================================================
# 0. 结构化日志
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("agent-api")

# ============================================================
# 1. Pydantic 数据模型（增强版）
# ============================================================

class ChatRequest(BaseModel):
    """聊天请求 — 支持会话"""
    message: str = Field(..., min_length=1, max_length=5000)
    session_id: str | None = Field(default=None, description="会话ID。不传则创建新会话")
    max_iterations: int = Field(default=6, ge=1, le=15)
    temperature: float = Field(default=0.0, ge=0.0, le=1.5)
    tools: list[str] = Field(
        default=["knowledge_base_search", "web_search", "python_repl", "calculator", "get_current_time"]
    )

class ToolCallRecord(BaseModel):
    round: int
    tool: str
    args: dict
    result: str = ""
    elapsed_ms: float = 0.0

class ChatResponse(BaseModel):
    answer: str
    session_id: str
    iterations: int
    tool_calls: list[ToolCallRecord] = []
    total_elapsed_ms: float = 0.0
    model: str = LLM_MODEL

class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    n_results: int = Field(default=3, ge=1, le=10)

class WebSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=200)
    max_results: int = Field(default=5, ge=1, le=10)
    sort: str = Field(default="relevance", pattern="^(relevance|newest)$")

class SessionInfo(BaseModel):
    session_id: str
    created_at: str
    message_count: int
    last_message_preview: str = ""

class ErrorResponse(BaseModel):
    error: str
    detail: str = ""
    code: str = "INTERNAL_ERROR"

# ============================================================
# 2. 会话管理器
# ============================================================

class SessionManager:
    """内存会话管理 — 生产环境应替换为 Redis/DB"""

    def __init__(self, ttl_seconds: int = 3600):
        self.sessions: dict[str, list[dict]] = defaultdict(list)
        self.metadata: dict[str, dict] = {}  # session_id → {created_at, ...}
        self.ttl = ttl_seconds

    def create(self) -> str:
        sid = str(uuid.uuid4())[:8]
        self.metadata[sid] = {
            "created_at": _dt.datetime.now().isoformat(),
            "last_access": _time.time(),
        }
        logger.info(f"Session created: {sid}")
        return sid

    def get_history(self, session_id: str) -> list[dict]:
        self._touch(session_id)
        return self.sessions.get(session_id, [])

    def add_message(self, session_id: str, role: str, content: str):
        self._touch(session_id)
        self.sessions[session_id].append({
            "role": role,
            "content": content,
            "time": _dt.datetime.now().isoformat(),
        })
        # 限制历史长度
        if len(self.sessions[session_id]) > 40:
            self.sessions[session_id] = self.sessions[session_id][-40:]

    def delete(self, session_id: str):
        self.sessions.pop(session_id, None)
        self.metadata.pop(session_id, None)
        logger.info(f"Session deleted: {session_id}")

    def list_sessions(self) -> list[dict]:
        now = _time.time()
        active = []
        for sid, meta in list(self.metadata.items()):
            if now - meta.get("last_access", 0) > self.ttl:
                self.delete(sid)
                continue
            messages = self.sessions.get(sid, [])
            active.append({
                "session_id": sid,
                "created_at": meta["created_at"],
                "message_count": len(messages),
                "last_message": messages[-1]["content"][:80] if messages else "",
            })
        return sorted(active, key=lambda s: s["created_at"], reverse=True)

    def build_agent_messages(self, session_id: str, system_prompt: str, user_message: str) -> list[dict]:
        """从会话历史构建 Agent 消息列表"""
        messages = [{"role": "system", "content": system_prompt}]

        # 加载历史
        history = self.get_history(session_id)
        for h in history[-20:]:  # 最近 20 条
            messages.append({"role": h["role"], "content": h["content"]})

        # 添加当前问题
        messages.append({"role": "user", "content": user_message})
        return messages

    def _touch(self, session_id: str):
        if session_id in self.metadata:
            self.metadata[session_id]["last_access"] = _time.time()

sessions = SessionManager()

# ============================================================
# 3. 限流器
# ============================================================

class RateLimiter:
    """简单滑动窗口限流"""

    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self.clients: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, client_ip: str) -> bool:
        now = _time.time()
        window_start = now - self.window
        # 清理过期记录
        self.clients[client_ip] = [
            t for t in self.clients[client_ip] if t > window_start
        ]
        if len(self.clients[client_ip]) >= self.max_requests:
            return False
        self.clients[client_ip].append(now)
        return True

limiter = RateLimiter(max_requests=30, window_seconds=60)

# ============================================================
# 4. 初始化 FastAPI（增强版）
# ============================================================

app = FastAPI(
    title="AI Agent + RAG API (Production)",
    description="""
## 生产级 AI Agent API

基于 Day 22 增强：会话管理 + 结构化日志 + 限流 + 测试套件。

### 新增功能

| 功能 | 说明 |
|------|------|
| 🔄 会话管理 | POST /session/create → 带 session_id 的多轮对话 |
| 📊 结构日志 | 每次请求自动记录耗时、工具调用链 |
| 🛡️ 限流保护 | 每 IP 30次/分钟 |
| ⚡ 耗时追踪 | 响应中包含每步工具调用的耗时 |

### 端点列表

- `POST /session/create` — 创建会话
- `GET /session/list` — 列出所有活跃会话
- `GET /session/{id}` — 查看会话历史
- `DELETE /session/{id}` — 删除会话
- `POST /chat` — 带会话的聊天
- `POST /chat/stream` — 流式聊天
- 其他端点同 Day 22
""",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 请求日志中间件 ──
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = _time.time()

    # 限流检查
    client_ip = request.client.host if request.client else "unknown"
    if not limiter.is_allowed(client_ip):
        return JSONResponse(
            status_code=429,
            content={"error": "请求过于频繁", "detail": "请稍后再试，限制 30次/分钟", "code": "RATE_LIMITED"},
        )

    response = await call_next(request)
    elapsed = (_time.time() - start) * 1000
    logger.info(f"{request.method} {request.url.path} → {response.status_code} ({elapsed:.0f}ms)")
    return response

# ── 统一异常处理 ──
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "服务器内部错误", "detail": str(exc), "code": "INTERNAL_ERROR"},
    )

# ============================================================
# 5. 初始化工具（同 Day 22）
# ============================================================

CHROMA_PATH = os.path.join(os.path.dirname(__file__), "chroma_db")
chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)

all_collections = chroma_client.list_collections()
KB_NAME = None
for c in all_collections:
    if c.name in ("knowledge_base", "day11_kb"):
        KB_NAME = c.name
        break

collection = chroma_client.get_collection(KB_NAME) if KB_NAME else None
logger.info(f"知识库: {KB_NAME or 'N/A'} ({collection.count() if collection else 0} docs)")

CURRENT_DATE = _dt.datetime.now().strftime("%Y年%m月%d日")
CURRENT_WEEKDAY = ["星期一","星期二","星期三","星期四","星期五","星期六","星期日"][_dt.datetime.now().weekday()]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.bilibili.com/",
}

# ── 5 个工具函数（精简自 Day 22）──

def knowledge_base_search(query: str, n_results: int = 3) -> str:
    if collection is None or collection.count() == 0:
        return "（知识库为空）"
    q_emb = llm_client.embeddings.create(model="text-embedding-v2", input=[query]).data[0].embedding
    results = collection.query(query_embeddings=[q_emb], n_results=min(n_results, collection.count()))
    docs = results.get("documents", [[]])[0]
    distances = results.get("distances", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    if not docs:
        return f"（知识库未找到相关内容）"
    parts = []
    for i, (doc, dist, meta) in enumerate(zip(docs, distances, metadatas), 1):
        score = 1.0 / (1.0 + dist) if dist else 1.0
        pct = round(score * 100)
        rel = "★★★" if pct >= 55 else "★★☆" if pct >= 40 else "★☆☆" if pct >= 30 else "☆☆☆"
        source = meta.get("source", "?") if meta else "?"
        doc_text = doc[:500] + "..." if len(doc) > 500 else doc
        parts.append(f"[知识库片段 {i}] {rel} | 来源:{source}\n{doc_text}")
    return f"📚 知识库检索（共 {len(parts)} 条）\n\n" + "\n\n".join(parts)

def web_search(query: str, max_results: int = 5, fresh: bool = False) -> str:
    try:
        order = "pubdate" if fresh else "totalrank"
        url = f"https://api.bilibili.com/x/web-interface/search/type?search_type=video&keyword={query}&order={order}"
        resp = requests.get(url, headers=HEADERS, timeout=8)
        if resp.status_code != 200:
            return f"搜索失败：HTTP {resp.status_code}"
        data = resp.json()
        if data.get("code") != 0:
            return f"搜索失败：{data.get('message', '?')}"
        raw = data.get("data", {}).get("result", [])[:max_results]
        if not raw:
            return f"B站未找到相关结果"
        parts = []
        for i, r in enumerate(raw, 1):
            title = r.get("title","").replace('<em class="keyword">','').replace('</em>','')
            bvid = r.get("bvid","")
            pubdate_ts = r.get("pubdate",0)
            pubdate_str = _dt.datetime.fromtimestamp(pubdate_ts).strftime("%Y-%m-%d") if pubdate_ts else "?"
            play = r.get("play",0)
            desc = r.get("description","")[:80]
            parts.append(f"[{i}] {title}\n    📅{pubdate_str} | ▶️{play}\n    {desc}\n    https://www.bilibili.com/video/{bvid}")
        return f"🔍 外部搜索（B站 · {'最新' if fresh else '综合'}）\n\n" + "\n\n".join(parts)
    except Exception as e:
        return f"搜索失败：{e}"

def calculator(expression: str) -> str:
    allowed = {"abs":abs,"round":round,"min":min,"max":max,"pow":pow,"sqrt":math.sqrt,
               "sin":math.sin,"cos":math.cos,"log":math.log,"pi":math.pi,"e":math.e,
               "ceil":math.ceil,"floor":math.floor}
    try:
        code = compile(expression, "<calc>", "eval")
        for name in code.co_names:
            if name not in allowed:
                return f"错误：'{name}' 不允许"
        return str(eval(code, {"__builtins__": {}}, allowed))
    except Exception as e:
        return f"计算错误：{e}"

def get_current_time(format_type: str = "datetime") -> str:
    now = _dt.datetime.now()
    if format_type == "date": return now.strftime("%Y年%m月%d日")
    elif format_type == "time": return now.strftime("%H:%M:%S")
    elif format_type == "weekday": return ["星期一","星期二","星期三","星期四","星期五","星期六","星期日"][now.weekday()]
    else: return now.strftime("%Y年%m月%d日 %H:%M:%S") + f" {CURRENT_WEEKDAY}"

import statistics, random as _random, re as _re, collections, itertools, fractions, decimal, functools

SAFE_BUILTINS = {
    'print':print,'len':len,'range':range,'enumerate':enumerate,'zip':zip,'map':map,
    'filter':filter,'sorted':sorted,'reversed':reversed,'sum':sum,'min':min,'max':max,
    'abs':abs,'round':round,'int':int,'float':float,'str':str,'bool':bool,
    'list':list,'dict':dict,'tuple':tuple,'set':set,'True':True,'False':False,'None':None,
    'Exception':Exception,'ValueError':ValueError,'TypeError':TypeError,
    'any':any,'all':all,'isinstance':isinstance,'pow':pow,'divmod':divmod,
    'chr':chr,'ord':ord,'bin':bin,'hex':hex,
    '__import__':lambda *a,**kw:(_ for _ in()).throw(ImportError('import disabled')),
    'open':lambda *a,**kw:(_ for _ in()).throw(RuntimeError('open() disabled')),
    'eval':lambda *a,**kw:(_ for _ in()).throw(RuntimeError('eval() disabled')),
    'exec':lambda *a,**kw:(_ for _ in()).throw(RuntimeError('exec() disabled')),
}
SAFE_MODULES = {
    'math':math,'json':json,'datetime':_dt,'random':_random,
    'statistics':statistics,'collections':collections,'itertools':itertools,
    're':_re,'fractions':fractions,'decimal':decimal,'functools':functools,
}

def python_repl(code: str) -> str:
    namespace = {'__builtins__': SAFE_BUILTINS, **SAFE_MODULES}
    stdout = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = stdout
    try:
        exec(compile(code, '<agent_repl>', 'exec'), namespace)
        output = stdout.getvalue()
        return output.rstrip() if output.rstrip() else "（无输出）"
    except SyntaxError as e:
        return f"语法错误：第{e.lineno}行 - {e.msg}"
    except Exception as e:
        return f"执行错误：{type(e).__name__}: {e}"
    finally:
        sys.stdout = old_stdout

# ── 工具注册表 ──
ALL_TOOLS: dict[str, dict] = {
    "knowledge_base_search": {
        "name": "知识库检索", "icon": "📚",
        "schema": {
            "type": "function", "function": {
                "name": "knowledge_base_search",
                "description": "在本地知识库中语义检索。知识库包含AI/LLM/RAG/Agent等专业知识。用于概念解释、技术原理、框架用法。时效性问题请用web_search。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "检索查询，10-30字"},
                        "n_results": {"type": "integer", "description": "返回条数，默认3"},
                    },
                    "required": ["query"],
                },
            },
        },
        "func": lambda query, n_results=3: knowledge_base_search(query, n_results),
    },
    "web_search": {
        "name": "外部搜索", "icon": "🔍",
        "schema": {
            "type": "function", "function": {
                "name": "web_search",
                "description": "搜索B站获取外部实时信息。用于最新新闻、行业动态、实时数据。时效性问题设置sort='newest'。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索关键词"},
                        "max_results": {"type": "integer", "description": "返回条数，默认5"},
                        "sort": {"type": "string", "enum": ["relevance", "newest"], "description": "排序方式"},
                    },
                    "required": ["query"],
                },
            },
        },
        "func": lambda query, max_results=5, sort="relevance": web_search(query, max_results, sort == "newest"),
    },
    "calculator": {
        "name": "数学计算", "icon": "🔢",
        "schema": {
            "type": "function", "function": {
                "name": "calculator",
                "description": "计算数学表达式。支持+-*/、sqrt、sin/cos、log、pi等。",
                "parameters": {
                    "type": "object",
                    "properties": {"expression": {"type": "string", "description": "数学表达式"}},
                    "required": ["expression"],
                },
            },
        },
        "func": lambda expression: calculator(expression),
    },
    "get_current_time": {
        "name": "日期时间", "icon": "🕐",
        "schema": {
            "type": "function", "function": {
                "name": "get_current_time",
                "description": "获取当前日期、时间或星期几。",
                "parameters": {
                    "type": "object",
                    "properties": {"format_type": {"type": "string", "enum": ["datetime", "date", "time", "weekday"]}},
                    "required": ["format_type"],
                },
            },
        },
        "func": lambda format_type="datetime": get_current_time(format_type),
    },
    "python_repl": {
        "name": "Python执行", "icon": "🐍",
        "schema": {
            "type": "function", "function": {
                "name": "python_repl",
                "description": "执行Python代码。用于数据处理、统计分析。使用print()输出。已预装math/json/statistics等。",
                "parameters": {
                    "type": "object",
                    "properties": {"code": {"type": "string", "description": "Python代码"}},
                    "required": ["code"],
                },
            },
        },
        "func": lambda code: python_repl(code),
    },
}

ALL_TOOL_SCHEMAS = [t["schema"] for t in ALL_TOOLS.values()]

# ============================================================
# 6. Agent 循环（增强版 — 支持回调）
# ============================================================

SYSTEM_PROMPT = (
    f"当前日期：{CURRENT_DATE} {CURRENT_WEEKDAY}\n\n"
    f"你是具备「内部知识库+外部搜索」双通道的智能助手。\n\n"
    f"## 工具箱\n"
    f"- 📚 knowledge_base_search: 本地知识库（AI/LLM/RAG/Agent等）\n"
    f"- 🔍 web_search: 外部互联网（B站，最新信息）\n"
    f"- 🐍 python_repl: Python代码执行\n"
    f"- 🔢 calculator: 数学计算\n"
    f"- 🕐 get_current_time: 日期时间\n\n"
    f"## ⚠️ 工具选择原则\n"
    f"1. 概念/原理/技术解释 → 必须先查 📚 knowledge_base_search\n"
    f"2. 最新新闻/实时数据/动态 → 🔍 web_search\n"
    f"3. 综合问题 → 同时查知识库+搜索\n"
    f"4. 数据处理 → 🐍 python_repl\n"
    f"5. 简单数学 → 🔢 calculator\n"
    f"6. 只有闲聊/问候才直接回答\n\n"
    f"## 答案格式\n"
    f"- 知识库来源标注「📚 内部资料」\n"
    f"- 搜索来源标注「🔍 外部信息」"
)


def run_agent(
    messages: list[dict],
    max_iterations: int = 6,
    temperature: float = 0.0,
    tools_enabled: list[str] = None,
    on_tool_call: callable = None,
) -> dict:
    """运行 Agent 循环，每次工具调用触发 on_tool_call 回调"""

    if tools_enabled is None:
        tool_schemas = ALL_TOOL_SCHEMAS
    else:
        tool_schemas = [ALL_TOOLS[n]["schema"] for n in tools_enabled if n in ALL_TOOLS]

    tool_calls_log = []
    iterations = 0
    finish_reason = ""
    start_time = _time.time()

    while iterations < max_iterations:
        iterations += 1

        t0 = _time.time()
        response = llm_client.chat.completions.create(
            model=LLM_MODEL, messages=messages,
            tools=tool_schemas if tool_schemas else None,
            temperature=temperature,
        )
        llm_elapsed = (_time.time() - t0) * 1000

        msg = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        if finish_reason == "stop":
            answer = msg.content or ""
            break

        elif msg.tool_calls:
            serialized = []
            for tc in msg.tool_calls:
                serialized.append({
                    "id": tc.id, "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                })
            messages.append({
                "role": "assistant", "content": msg.content or "", "tool_calls": serialized,
            })

            for tc in msg.tool_calls:
                name = tc.function.name
                args = json.loads(tc.function.arguments)

                t_tool = _time.time()
                if name in ALL_TOOLS:
                    result = ALL_TOOLS[name]["func"](**args)
                else:
                    result = f"未知工具: {name}"
                tool_elapsed = (_time.time() - t_tool) * 1000

                result_display = result[:500] + "..." if len(result) > 500 else result

                record = {
                    "round": iterations, "tool": name, "args": args,
                    "result": result_display, "elapsed_ms": round(tool_elapsed, 1),
                }
                tool_calls_log.append(record)

                logger.info(f"  R{iterations} {name}({json.dumps(args, ensure_ascii=False)[:60]}) → {tool_elapsed:.0f}ms")

                if on_tool_call:
                    on_tool_call(record)

                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
        else:
            break

    total_elapsed = (_time.time() - start_time) * 1000

    if iterations >= max_iterations and finish_reason not in ("stop", ""):
        answer = f"Agent 达到最大步数（{max_iterations}），已停止。"

    logger.info(f"Agent done: {iterations} iters, {len(tool_calls_log)} calls, {total_elapsed:.0f}ms")

    return {
        "answer": answer, "iterations": iterations,
        "tool_calls": tool_calls_log, "total_elapsed_ms": round(total_elapsed, 1),
    }


# ============================================================
# 7. API 端点
# ============================================================

@app.get("/")
async def root():
    """健康检查 + 系统信息"""
    return {
        "status": "running", "version": "2.0.0", "model": LLM_MODEL,
        "knowledge_base_docs": collection.count() if collection else 0,
        "tools_available": list(ALL_TOOLS.keys()),
        "active_sessions": len(sessions.list_sessions()),
    }

@app.get("/tools")
async def list_tools():
    """列出所有工具"""
    return {
        "count": len(ALL_TOOLS),
        "tools": [{
            "id": k,
            "name": t["name"], "icon": t["icon"],
            "description": t["schema"]["function"]["description"],
        } for k, t in ALL_TOOLS.items()],
    }

# ── 会话管理端点 ──

@app.post("/session/create")
async def create_session():
    """创建新会话，返回 session_id"""
    sid = sessions.create()
    return {"session_id": sid, "message": "会话已创建"}

@app.get("/session/list")
async def list_sessions():
    """列出所有活跃会话"""
    return {"sessions": sessions.list_sessions()}

@app.get("/session/{session_id}")
async def get_session(session_id: str):
    """查看指定会话的对话历史"""
    history = sessions.get_history(session_id)
    if not history and session_id not in sessions.metadata:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在或已过期")
    return {
        "session_id": session_id,
        "created_at": sessions.metadata.get(session_id, {}).get("created_at", ""),
        "message_count": len(history),
        "messages": history[-20:],
    }

@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    if session_id not in sessions.metadata:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
    sessions.delete(session_id)
    return {"message": f"会话 {session_id} 已删除"}

# ── 聊天端点 ──

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """主聊天端点 — 支持会话，返回完整结果"""

    # 创建或复用会话
    session_id = req.session_id or sessions.create()

    # 保存用户消息
    sessions.add_message(session_id, "user", req.message)

    # 构建消息列表（含历史）
    messages = sessions.build_agent_messages(session_id, SYSTEM_PROMPT, req.message)

    try:
        result = run_agent(
            messages=messages,
            max_iterations=req.max_iterations,
            temperature=req.temperature,
            tools_enabled=req.tools,
        )

        # 保存 AI 回复
        sessions.add_message(session_id, "assistant", result["answer"])

        return ChatResponse(
            answer=result["answer"],
            session_id=session_id,
            iterations=result["iterations"],
            tool_calls=[ToolCallRecord(**tc) for tc in result["tool_calls"]],
            total_elapsed_ms=result["total_elapsed_ms"],
            model=LLM_MODEL,
        )
    except Exception as e:
        logger.error(f"Agent error: {e}")
        raise HTTPException(status_code=500, detail=f"Agent 执行失败：{str(e)}")


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """流式聊天 — SSE 实时推送"""

    session_id = req.session_id or sessions.create()
    sessions.add_message(session_id, "user", req.message)
    messages = sessions.build_agent_messages(session_id, SYSTEM_PROMPT, req.message)

    full_answer = ""
    events = []

    def on_tool(tc: dict):
        events.append({"type": "tool_call", "data": tc})

    async def event_gen():
        nonlocal full_answer
        try:
            result = run_agent(
                messages=messages,
                max_iterations=req.max_iterations,
                temperature=req.temperature,
                tools_enabled=req.tools,
                on_tool_call=on_tool,
            )
            full_answer = result["answer"]

            for evt in events:
                yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'type': 'answer', 'data': {'answer': full_answer, 'iterations': result['iterations'], 'total_elapsed_ms': result['total_elapsed_ms']}}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'data': {}})}\n\n"

            sessions.add_message(session_id, "assistant", full_answer)
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'data': {'message': str(e)}}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )

# ── 其他端点 ──

@app.post("/knowledge/search")
async def search_knowledge(req: KnowledgeSearchRequest):
    return {"query": req.query, "n_results": req.n_results, "result": knowledge_base_search(req.query, req.n_results)}

@app.post("/web/search")
async def search_web(req: WebSearchRequest):
    fresh = req.sort == "newest"
    return {"query": req.query, "sort": req.sort, "result": web_search(req.query, req.max_results, fresh)}

# ============================================================
# 8. 测试套件（pytest 可用）
# ============================================================

# 运行方式：pytest day23_api_refinement.py -v

def test_imports():
    """测试：所有依赖可正常导入"""
    assert FastAPI is not None
    assert LLM_MODEL is not None
    assert len(ALL_TOOLS) == 5

def test_session_create_delete():
    """测试：会话创建和删除"""
    sid = sessions.create()
    assert len(sid) == 8  # UUID 前 8 位
    assert sid in sessions.metadata

    sessions.delete(sid)
    assert sid not in sessions.metadata

def test_session_chat_history():
    """测试：会话对话历史"""
    sid = sessions.create()
    sessions.add_message(sid, "user", "你好")
    sessions.add_message(sid, "assistant", "你好！有什么可以帮你的？")

    history = sessions.get_history(sid)
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"

    sessions.delete(sid)

def test_session_build_messages():
    """测试：从会话构建 Agent 消息"""
    sid = sessions.create()
    sessions.add_message(sid, "user", "第一个问题")
    sessions.add_message(sid, "assistant", "第一个回答")

    msgs = sessions.build_agent_messages(sid, "SYSTEM", "第二个问题")
    assert msgs[0]["role"] == "system"
    assert msgs[0]["content"] == "SYSTEM"
    assert msgs[1]["role"] == "user"
    assert msgs[3]["role"] == "user"
    assert msgs[3]["content"] == "第二个问题"

    sessions.delete(sid)

def test_rate_limiter():
    """测试：限流器"""
    limiter2 = RateLimiter(max_requests=3, window_seconds=60)
    assert limiter2.is_allowed("127.0.0.1") == True
    assert limiter2.is_allowed("127.0.0.1") == True
    assert limiter2.is_allowed("127.0.0.1") == True
    assert limiter2.is_allowed("127.0.0.1") == False  # 第 4 次被限

def test_knowledge_search():
    """测试：知识库检索"""
    result = knowledge_base_search("RAG", n_results=2)
    assert "知识库" in result or "知识库" in result
    assert len(result) > 50

def test_calculator():
    """测试：计算器"""
    assert "42" in calculator("6*7")
    assert "错误" in calculator("__import__('os')")

def test_web_search_error_handling():
    """测试：搜索错误处理 — 空查询不抛异常，返回错误消息"""
    result = web_search("", max_results=1)
    assert isinstance(result, str)
    assert len(result) > 3  # 至少返回错误信息

def test_python_repl_safety():
    """测试：Python 沙箱安全性"""
    r1 = python_repl("print(1+1)")
    assert "2" in r1

    r2 = python_repl("open('/etc/passwd')")
    assert "执行错误" in r2 or "disabled" in r2.lower()

def test_chat_request_validation():
    """测试：请求验证"""
    # 有效请求
    req = ChatRequest(message="测试")
    assert req.message == "测试"
    assert req.max_iterations == 6

    # 无效：空消息
    try:
        ChatRequest(message="")
        assert False, "应该抛出验证错误"
    except Exception:
        pass


# ══════════════════════════════════════════════════════
# API 集成测试（需要服务运行）
# 用法：启动服务后运行
#   pytest day23_api_refinement.py -v -k "test_api"
# ══════════════════════════════════════════════════════

import pytest  # type: ignore

@pytest.mark.api
class TestAPI:
    """集成测试 — 需要启动服务"""

    BASE = "http://localhost:8000"

    @pytest.fixture(autouse=True)
    def setup(self):
        import requests as req
        self.req = req
        # 验证服务是否在运行
        try:
            self.req.get(f"{self.BASE}/", timeout=2)
        except Exception:
            pytest.skip("服务未启动，跳过集成测试")

    def test_health(self):
        r = self.req.get(f"{self.BASE}/", timeout=5)
        assert r.status_code == 200
        assert r.json()["status"] == "running"

    def test_tools(self):
        r = self.req.get(f"{self.BASE}/tools", timeout=5)
        assert r.status_code == 200
        assert r.json()["count"] == 5

    def test_session_lifecycle(self):
        # 创建
        r = self.req.post(f"{self.BASE}/session/create", timeout=5)
        assert r.status_code == 200
        sid = r.json()["session_id"]

        # 列出
        r = self.req.get(f"{self.BASE}/session/list", timeout=5)
        assert any(s["session_id"] == sid for s in r.json()["sessions"])

        # 删除
        r = self.req.delete(f"{self.BASE}/session/{sid}", timeout=5)
        assert r.status_code == 200

    def test_chat_with_session(self):
        # 创建会话
        r = self.req.post(f"{self.BASE}/session/create", timeout=5)
        sid = r.json()["session_id"]

        # 第一轮
        r = self.req.post(f"{self.BASE}/chat", json={
            "message": "你好", "session_id": sid, "max_iterations": 2
        }, timeout=30)
        assert r.status_code == 200
        assert len(r.json()["answer"]) > 5

        # 第二轮（带历史）
        r = self.req.post(f"{self.BASE}/chat", json={
            "message": "我刚才问了你什么？", "session_id": sid, "max_iterations": 2
        }, timeout=30)
        assert r.status_code == 200

        # 查看历史
        r = self.req.get(f"{self.BASE}/session/{sid}", timeout=5)
        assert r.json()["message_count"] >= 3  # user + assistant + user + assistant

    def test_knowledge_search(self):
        r = self.req.post(f"{self.BASE}/knowledge/search", json={
            "query": "Embedding", "n_results": 2
        }, timeout=10)
        assert r.status_code == 200
        assert "result" in r.json()


if __name__ == "__main__":
    print()
    print("=" * 60)
    print("Day 23 — API 完善 + 生产级特性")
    print("=" * 60)
    print(f"""
  启动服务：
    uvicorn day23_api_refinement:app --reload --port 8000

  运行测试：
    pytest day23_api_refinement.py -v

  📖 Swagger UI: http://localhost:8000/docs

  🆕 相比 Day 22 新增：
    - 🔄 会话管理（/session/create, /session/list, /session/{{id}}）
    - 📊 结构化日志（请求追踪 + 耗时统计）
    - 🛡️ 限流保护（30次/分钟/IP）
    - ⚡ API 集成测试套件（单元测试 + 集成测试）
    - 🎯 统一错误响应格式
""")
    uvicorn.run(app, host="0.0.0.0", port=8000)
