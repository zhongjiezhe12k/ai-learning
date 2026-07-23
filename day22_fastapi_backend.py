"""
Day 22 — FastAPI 后端 API：把 Agent+RAG 混合系统包装为 REST API
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
学完今天你会：
  ✅ 用 FastAPI 把 Agent+RAG 系统包装为 REST API
  ✅ Pydantic 数据模型做请求验证和响应序列化
  ✅ SSE (Server-Sent Events) 实现流式 Agent 推理
  ✅ 自动生成 API 文档（Swagger UI + ReDoc）
  ✅ 理解「AI 应用后端」的标准架构模式

架构图：
  ┌──────────────┐     HTTP/SSE     ┌──────────────────────┐
  │  前端客户端    │ ◄──────────────► │   FastAPI 后端        │
  │  (Day 24-25)  │                  │                      │
  └──────────────┘                  │  POST /chat          │
                                    │  POST /chat/stream   │
                                    │  POST /knowledge     │
                                    │  POST /web/search    │
                                    │  GET  /tools         │
                                    │                      │
                                    │  内部：5 个 Tool       │
                                    │  Agent Loop 引擎      │
                                    └──────────────────────┘

启动方式：
  uvicorn day22_fastapi_backend:app --reload --host 0.0.0.0 --port 8000

然后访问：
  http://localhost:8000/docs     ← Swagger UI（可交互测试）
  http://localhost:8000/redoc    ← ReDoc 文档
"""

import sys, os, json, math, io, time
sys.stdout.reconfigure(encoding='utf-8')

# ============================================================
# 0. 依赖检查
# ============================================================
try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import StreamingResponse
    from pydantic import BaseModel, Field
    import uvicorn
except ImportError as e:
    print(f"缺少依赖：{e}")
    print("请运行：pip install fastapi uvicorn pydantic")
    sys.exit(1)

from config import client as llm_client, MODEL as LLM_MODEL
import chromadb, datetime as _dt, requests
import asyncio

# ============================================================
# 1. Pydantic 数据模型
# ============================================================

class ChatRequest(BaseModel):
    """聊天请求"""
    message: str = Field(..., description="用户问题", min_length=1, max_length=5000)
    max_iterations: int = Field(default=6, ge=1, le=15, description="Agent 最大循环轮数")
    temperature: float = Field(default=0.0, ge=0.0, le=1.5, description="LLM 温度参数")
    tools: list[str] = Field(
        default=["knowledge_base_search", "web_search", "python_repl", "calculator", "get_current_time"],
        description="启用的工具列表"
    )

class ToolCallRecord(BaseModel):
    """工具调用记录"""
    round: int
    tool: str
    args: dict
    result: str = Field(default="", description="工具返回结果（截断到 500 字符）")

class ChatResponse(BaseModel):
    """聊天响应"""
    answer: str
    iterations: int
    tool_calls: list[ToolCallRecord] = []
    kb_sources: list[str] = Field(default=[], description="知识库来源片段")
    model: str = LLM_MODEL

class KnowledgeSearchRequest(BaseModel):
    """知识库检索请求"""
    query: str = Field(..., min_length=1, max_length=500)
    n_results: int = Field(default=3, ge=1, le=10)

class WebSearchRequest(BaseModel):
    """网页搜索请求"""
    query: str = Field(..., min_length=1, max_length=200)
    max_results: int = Field(default=5, ge=1, le=10)
    sort: str = Field(default="relevance", pattern="^(relevance|newest)$")

class HealthResponse(BaseModel):
    """健康检查"""
    status: str
    version: str
    model: str
    knowledge_base_docs: int
    tools_available: list[str]

# ============================================================
# 2. 初始化 FastAPI 应用
# ============================================================

app = FastAPI(
    title="AI Agent + RAG 混合助手 API",
    description="""
## 功能

本 API 将一个具备 **5 个工具** 的 AI Agent 包装为 REST 服务：

| 工具 | 功能 |
|------|------|
| 📚 knowledge_base_search | Chroma 向量知识库语义检索 |
| 🔍 web_search | B站外部网页搜索 |
| 🐍 python_repl | Python 安全沙箱执行 |
| 🔢 calculator | 数学表达式计算 |
| 🕐 get_current_time | 日期时间查询 |

## 使用方式

1. **POST /chat** — 发送问题，Agent 自主编排工具，返回完整答案
2. **POST /chat/stream** — 同上，但通过 SSE 实时推送推理过程
3. **POST /knowledge/search** — 直接搜索知识库（不经过 Agent）
4. **POST /web/search** — 直接搜索网页（不经过 Agent）
5. **GET /tools** — 查看所有可用工具
""",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# 3. 初始化所有工具（复用 Day 20 的核心逻辑）
# ============================================================

print("=" * 60)
print("Day 22 — FastAPI 后端启动中...")
print("=" * 60)

# ── 知识库 ──
CHROMA_PATH = os.path.join(os.path.dirname(__file__), "chroma_db")
chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)

all_collections = chroma_client.list_collections()
KB_NAME = None
for c in all_collections:
    if c.name in ("knowledge_base", "day11_kb"):
        KB_NAME = c.name
        break

if KB_NAME:
    collection = chroma_client.get_collection(KB_NAME)
else:
    collection = None

print(f"  知识库: {KB_NAME or '未找到'} ({collection.count() if collection else 0} docs)")

CURRENT_DATE = _dt.datetime.now().strftime("%Y年%m月%d日")
CURRENT_WEEKDAY = ["星期一","星期二","星期三","星期四","星期五","星期六","星期日"][_dt.datetime.now().weekday()]

# ── Tool 1: knowledge_base_search ──
def knowledge_base_search(query: str, n_results: int = 3) -> str:
    if collection is None or collection.count() == 0:
        return "（知识库为空）"

    q_emb = llm_client.embeddings.create(
        model="text-embedding-v2", input=[query],
    ).data[0].embedding

    results = collection.query(
        query_embeddings=[q_emb],
        n_results=min(n_results, collection.count()),
    )

    docs = results.get("documents", [[]])[0]
    distances = results.get("distances", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    if not docs:
        return f"（知识库中未找到与「{query}」相关的内容）"

    parts = []
    for i, (doc, dist, meta) in enumerate(zip(docs, distances, metadatas), 1):
        score = 1.0 / (1.0 + dist) if dist else 1.0
        score_pct = round(score * 100)
        if score_pct >= 55: relevance = "★★★ 高度相关"
        elif score_pct >= 40: relevance = "★★☆ 相关"
        elif score_pct >= 30: relevance = "★☆☆ 部分相关"
        else: relevance = "☆☆☆ 弱相关"
        source = meta.get("source", "未知") if meta else "未知"
        doc_text = doc[:500] + "..." if len(doc) > 500 else doc
        parts.append(
            f"[知识库片段 {i}] {relevance} | 来源: {source}\n{doc_text}"
        )

    return f"📚 知识库检索结果（共 {len(parts)} 条）\n\n" + "\n\n".join(parts)

# ── Tool 2: web_search ──
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.bilibili.com/",
}

def web_search(query: str, max_results: int = 5, fresh: bool = False) -> str:
    try:
        order = "pubdate" if fresh else "totalrank"
        url = (
            f"https://api.bilibili.com/x/web-interface/search/type"
            f"?search_type=video&keyword={query}&order={order}"
        )
        resp = requests.get(url, headers=HEADERS, timeout=8)
        if resp.status_code != 200:
            return f"搜索失败：HTTP {resp.status_code}"

        data = resp.json()
        if data.get("code") != 0:
            return f"搜索失败：{data.get('message', '未知错误')}"

        raw = data.get("data", {}).get("result", [])[:max_results]
        if not raw:
            return f"B站未找到「{query}」相关结果"

        parts = []
        for i, r in enumerate(raw, 1):
            title = r.get("title", "").replace('<em class="keyword">', '').replace('</em>', '')
            desc = r.get("description", "")[:100]
            bvid = r.get("bvid", "")
            play = r.get("play", 0)
            pubdate_ts = r.get("pubdate", 0)
            pubdate_str = _dt.datetime.fromtimestamp(pubdate_ts).strftime("%Y-%m-%d") if pubdate_ts else "未知"
            parts.append(
                f"[{i}] {title}\n"
                f"    📅 发布:{pubdate_str} | ▶️ 播放:{play}\n"
                f"    {desc}\n"
                f"    https://www.bilibili.com/video/{bvid}"
            )
        sort_label = "最新发布" if fresh else "综合排序"
        return f"🔍 外部搜索（来源：哔哩哔哩 · {sort_label}）\n\n" + "\n\n".join(parts)
    except requests.Timeout:
        return f"搜索「{query}」超时"
    except Exception as e:
        return f"搜索失败：{e}"

# ── Tool 3: calculator ──
def calculator(expression: str) -> str:
    allowed = {
        "abs": abs, "round": round, "min": min, "max": max,
        "pow": pow, "sqrt": math.sqrt, "sin": math.sin,
        "cos": math.cos, "log": math.log, "pi": math.pi, "e": math.e,
        "ceil": math.ceil, "floor": math.floor,
    }
    try:
        code = compile(expression, "<calc>", "eval")
        for name in code.co_names:
            if name not in allowed:
                return f"错误：'{name}' 不允许"
        return str(eval(code, {"__builtins__": {}}, allowed))
    except Exception as e:
        return f"计算错误：{e}"

# ── Tool 4: get_current_time ──
def get_current_time(format_type: str = "datetime") -> str:
    now = _dt.datetime.now()
    if format_type == "date":
        return now.strftime("%Y年%m月%d日")
    elif format_type == "time":
        return now.strftime("%H:%M:%S")
    elif format_type == "weekday":
        return ["星期一","星期二","星期三","星期四","星期五","星期六","星期日"][now.weekday()]
    else:
        return now.strftime("%Y年%m月%d日 %H:%M:%S") + f" {CURRENT_WEEKDAY}"

# ── Tool 5: python_repl ──
import statistics, random, re, collections, itertools, fractions, decimal, functools

SAFE_BUILTINS = {
    'print': print, 'len': len, 'range': range, 'enumerate': enumerate,
    'zip': zip, 'map': map, 'filter': filter, 'sorted': sorted,
    'reversed': reversed, 'sum': sum, 'min': min, 'max': max, 'abs': abs,
    'round': round, 'int': int, 'float': float, 'str': str, 'bool': bool,
    'list': list, 'dict': dict, 'tuple': tuple, 'set': set,
    'True': True, 'False': False, 'None': None,
    'Exception': Exception, 'ValueError': ValueError, 'TypeError': TypeError,
    'any': any, 'all': all, 'isinstance': isinstance,
    'pow': pow, 'divmod': divmod, 'chr': chr, 'ord': ord, 'bin': bin, 'hex': hex,
    '__import__': lambda *a, **kw: (_ for _ in ()).throw(ImportError('import disabled')),
    'open': lambda *a, **kw: (_ for _ in ()).throw(RuntimeError('open() disabled')),
    'eval': lambda *a, **kw: (_ for _ in ()).throw(RuntimeError('eval() disabled')),
    'exec': lambda *a, **kw: (_ for _ in ()).throw(RuntimeError('exec() disabled')),
}

SAFE_MODULES = {
    'math': math, 'json': json, 'datetime': _dt, 'random': random,
    'statistics': statistics, 'collections': collections,
    'itertools': itertools, 're': re, 'fractions': fractions,
    'decimal': decimal, 'functools': functools,
}

def python_repl(code: str, timeout_seconds: int = 5) -> str:
    namespace = {'__builtins__': SAFE_BUILTINS, **SAFE_MODULES}
    stdout = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = stdout
    try:
        compiled = compile(code, '<agent_repl>', 'exec')
        exec(compiled, namespace)
        output = stdout.getvalue()
        return output.rstrip() if output.rstrip() else "（代码执行完成，无输出）"
    except SyntaxError as e:
        return f"语法错误：第{e.lineno}行 - {e.msg}"
    except Exception as e:
        return f"执行错误：{type(e).__name__}: {e}"
    finally:
        sys.stdout = old_stdout

# ── 工具注册表 ──
ALL_TOOLS: dict[str, dict] = {
    "knowledge_base_search": {
        "name": "知识库检索",
        "icon": "📚",
        "schema": {
            "type": "function",
            "function": {
                "name": "knowledge_base_search",
                "description": (
                    "在本地知识库中进行语义检索。知识库包含AI应用开发、LLM基础、"
                    "Prompt工程、RAG系统、Agent开发等专业知识。"
                    "用于概念解释、技术原理、框架用法。⚠️ 时效性问题请用web_search。"
                ),
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
        "name": "外部搜索",
        "icon": "🔍",
        "schema": {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": (
                    "搜索B站视频获取外部实时信息。用于最新新闻、行业动态、实时数据、"
                    "价格、工具测评等时效性问题。时效性问题设置 sort='newest'。"
                    "返回标题+发布时间+描述+链接。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索关键词"},
                        "max_results": {"type": "integer", "description": "返回条数，默认5"},
                        "sort": {
                            "type": "string",
                            "enum": ["relevance", "newest"],
                            "description": "综合排序/最新发布。时效性问题用newest",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        "func": lambda query, max_results=5, sort="relevance": web_search(query, max_results, sort == "newest"),
    },
    "calculator": {
        "name": "数学计算",
        "icon": "🔢",
        "schema": {
            "type": "function",
            "function": {
                "name": "calculator",
                "description": "计算数学表达式。用于精确数学计算。支持 +-*/、sqrt、sin/cos、log、pi 等。",
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
        "name": "日期时间",
        "icon": "🕐",
        "schema": {
            "type": "function",
            "function": {
                "name": "get_current_time",
                "description": "获取当前日期、时间或星期几。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "format_type": {
                            "type": "string",
                            "enum": ["datetime", "date", "time", "weekday"],
                        }
                    },
                    "required": ["format_type"],
                },
            },
        },
        "func": lambda format_type="datetime": get_current_time(format_type),
    },
    "python_repl": {
        "name": "Python执行",
        "icon": "🐍",
        "schema": {
            "type": "function",
            "function": {
                "name": "python_repl",
                "description": (
                    "执行 Python 代码并返回输出。用于数据处理、统计分析、批量运算等。"
                    "使用 print() 输出。已预装 math/json/statistics/collections/itertools 等。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {"code": {"type": "string", "description": "Python 代码"}},
                    "required": ["code"],
                },
            },
        },
        "func": lambda code: python_repl(code),
    },
}

ALL_TOOL_SCHEMAS = [t["schema"] for t in ALL_TOOLS.values()]

# ============================================================
# 4. Agent 循环引擎
# ============================================================

SYSTEM_PROMPT = (
    f"当前日期：{CURRENT_DATE} {CURRENT_WEEKDAY}\n\n"
    f"你是一个具备「内部知识库 + 外部搜索」双通道的智能助手。\n\n"
    f"## 你的工具箱\n"
    f"- 📚 knowledge_base_search: 本地知识库（AI/LLM/RAG/Agent等专业知识）\n"
    f"- 🔍 web_search: 外部互联网（B站视频，最新信息）\n"
    f"- 🐍 python_repl: Python代码执行（数据处理/统计分析）\n"
    f"- 🔢 calculator: 快速数学计算\n"
    f"- 🕐 get_current_time: 当前日期时间\n\n"
    f"## ⚠️ 工具选择原则（严格遵守！）\n"
    f"1. ⚠️ 概念/原理/框架/技术解释 → 必须先查 📚 knowledge_base_search！不要凭记忆回答\n"
    f"2. 最新新闻/实时数据/行业动态/价格 → 🔍 web_search（时效性问题 sort='newest'）\n"
    f"3. 综合问题 → 同时调用 knowledge_base_search + web_search\n"
    f"4. 数据处理/统计分析 → 🐍 python_repl\n"
    f"5. 简单数学 → 🔢 calculator\n"
    f"6. 只有纯粹闲聊/问候才直接回答\n\n"
    f"## 答案格式\n"
    f"- 知识库来源标注「📚 内部资料」\n"
    f"- 搜索来源标注「🔍 外部信息」\n"
    f"- ❌ 禁止：未调用知识库却声称来自内部资料"
)


def run_agent(
    user_query: str,
    max_iterations: int = 6,
    temperature: float = 0.0,
    tools_enabled: list[str] = None,
    on_tool_call: callable = None,  # 回调：每步工具调用时触发
) -> dict:
    """运行 Agent 循环，返回完整结果"""

    if tools_enabled is None:
        tool_schemas = ALL_TOOL_SCHEMAS
    else:
        tool_schemas = [ALL_TOOLS[n]["schema"] for n in tools_enabled if n in ALL_TOOLS]

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_query},
    ]

    tool_calls_log = []
    iterations = 0
    finish_reason = ""

    while iterations < max_iterations:
        iterations += 1

        response = llm_client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            tools=tool_schemas if tool_schemas else None,
            temperature=temperature,
        )

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

                if name in ALL_TOOLS:
                    result = ALL_TOOLS[name]["func"](**args)
                else:
                    result = f"错误：未知工具 '{name}'"

                # 截断过长的结果
                result_display = result[:500] + "..." if len(result) > 500 else result

                tool_record = {
                    "round": iterations,
                    "tool": name,
                    "args": args,
                    "result": result_display,
                }
                tool_calls_log.append(tool_record)

                # 回调通知
                if on_tool_call:
                    on_tool_call(tool_record)

                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
        else:
            break

    if iterations >= max_iterations and finish_reason not in ("stop", ""):
        answer = f"Agent 达到最大步数（{max_iterations}），已停止。"

    return {
        "answer": answer,
        "iterations": iterations,
        "tool_calls": tool_calls_log,
    }


# ============================================================
# 5. API 端点
# ============================================================

@app.get("/", response_model=HealthResponse)
async def root():
    """健康检查 + 基本信息"""
    return {
        "status": "running",
        "version": "1.0.0",
        "model": LLM_MODEL,
        "knowledge_base_docs": collection.count() if collection else 0,
        "tools_available": list(ALL_TOOLS.keys()),
    }


@app.get("/tools")
async def list_tools():
    """列出所有可用工具及其描述"""
    tools_info = []
    for key, t in ALL_TOOLS.items():
        tools_info.append({
            "id": key,
            "name": t["name"],
            "icon": t["icon"],
            "description": t["schema"]["function"]["description"],
            "parameters": t["schema"]["function"]["parameters"]["properties"],
        })
    return {
        "count": len(tools_info),
        "tools": tools_info,
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """主聊天端点 — 非流式，返回完整结果"""
    try:
        result = run_agent(
            user_query=req.message,
            max_iterations=req.max_iterations,
            temperature=req.temperature,
            tools_enabled=req.tools,
        )

        # 提取知识库来源
        kb_sources = []
        for tc in result["tool_calls"]:
            if tc["tool"] == "knowledge_base_search":
                # 提取片段标题
                for line in tc["result"].split("\n"):
                    if line.startswith("[知识库片段"):
                        kb_sources.append(line[:120])
                        break

        return ChatResponse(
            answer=result["answer"],
            iterations=result["iterations"],
            tool_calls=[ToolCallRecord(**tc) for tc in result["tool_calls"]],
            kb_sources=kb_sources,
            model=LLM_MODEL,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent 执行失败：{str(e)}")


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """流式聊天端点 — SSE 实时推送 Agent 推理过程"""

    async def event_generator():
        events = []
        tool_call_count = [0]  # 用列表包装以便在闭包中修改

        def on_tool(tc: dict):
            tool_call_count[0] += 1
            events.append({
                "type": "tool_call",
                "data": tc,
            })

        try:
            result = run_agent(
                user_query=req.message,
                max_iterations=req.max_iterations,
                temperature=req.temperature,
                tools_enabled=req.tools,
                on_tool_call=on_tool,
            )

            # 发送工具调用事件
            for evt in events:
                yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"

            # 发送最终答案
            final_event = {
                "type": "answer",
                "data": {
                    "answer": result["answer"],
                    "iterations": result["iterations"],
                    "total_tool_calls": len(result["tool_calls"]),
                },
            }
            yield f"data: {json.dumps(final_event, ensure_ascii=False)}\n\n"

            # 结束信号
            yield f"data: {json.dumps({'type': 'done', 'data': {}})}\n\n"

        except Exception as e:
            error_event = {
                "type": "error",
                "data": {"message": str(e)},
            }
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/knowledge/search")
async def search_knowledge(req: KnowledgeSearchRequest):
    """直接搜索知识库（不经过 Agent）"""
    result = knowledge_base_search(req.query, req.n_results)
    return {
        "query": req.query,
        "n_results": req.n_results,
        "result": result,
    }


@app.post("/web/search")
async def search_web(req: WebSearchRequest):
    """直接搜索网页（不经过 Agent）"""
    fresh = req.sort == "newest"
    result = web_search(req.query, req.max_results, fresh)
    return {
        "query": req.query,
        "max_results": req.max_results,
        "sort": req.sort,
        "result": result,
    }


# ============================================================
# 6. 启动入口
# ============================================================

if __name__ == "__main__":
    print()
    print("=" * 60)
    print("🚀 启动 FastAPI 服务...")
    print("=" * 60)
    print(f"""
    📡 API 地址:      http://localhost:8000
    📖 Swagger UI:   http://localhost:8000/docs
    📚 ReDoc:        http://localhost:8000/redoc
    ❤️  健康检查:     http://localhost:8000/
    🔧 工具列表:     http://localhost:8000/tools

    快速测试：
      curl -X POST http://localhost:8000/chat \\
        -H "Content-Type: application/json" \\
        -d '{{"message": "什么是RAG？"}}'
""")
    uvicorn.run(app, host="0.0.0.0", port=8000)
