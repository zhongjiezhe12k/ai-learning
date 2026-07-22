"""
Day 20 — Agent + RAG 混合系统：知识库 + 外部搜索 + 综合回答
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Day 15-19 我们分别构建了 Agent 的多工具编排能力。
但 Agent 一直缺少一个关键能力：「内部知识库检索」。

今天我们把 RAG 检索能力作为一个 Tool 注入 Agent——
让 Agent 自主决定「什么时候查内部知识库、什么时候搜外部网络」。

学完今天你会：
  ✅ 理解 Agent + RAG 混合架构的设计理念
  ✅ 把 Chroma 向量检索封装为 Function Calling Tool
  ✅ 实现「内部知识库 + 外部搜索」双通道 Agent
  ✅ 掌握来源感知综合（source-aware synthesis）——清晰标注信息出处
  ✅ 对比纯 RAG / 纯搜索 / 混合 Agent 三种方案的效果

核心架构：
  ┌─────────────────────────────────────────────────────────────┐
  │                    Agent + RAG 混合系统                       │
  │                                                             │
  │   用户提问 ──→ Agent 意图分析 ──→ Tool 选择                    │
  │                  │                                          │
  │       ┌──────────┼──────────┬──────────┐                    │
  │       ▼          ▼          ▼          ▼                    │
  │   📚 RAG      🔍 搜索    🐍 Python   🔢 计算器              │
  │   (知识库)    (B站)     (数据处理)  (快速数学)               │
  │       │          │          │          │                    │
  │       └──────────┴──────────┴──────────┘                    │
  │                  │                                          │
  │                  ▼                                          │
  │          Agent 综合 → 标注来源 → 输出答案                     │
  └─────────────────────────────────────────────────────────────┘

对比三种 AI 应用形态：
  ┌──────────────┬──────────────┬──────────────┬──────────────┐
  │  RAG 系统    │  搜索 Agent   │  混合 Agent   │  单一 LLM    │
  ├──────────────┼──────────────┼──────────────┼──────────────┤
  │ 内部文档 ✅   │ 最新信息 ✅   │ 两者都有 ✅   │ 有限知识 ⚠️  │
  │ 外部新闻 ❌   │ 内部知识 ❌   │ 自主选择 ✅   │ 可能幻觉 ❌  │
  │ 数据计算 ❌   │ 数据计算 ❌   │ 灵活编排 ✅   │ 无来源引用 ❌ │
  └──────────────┴──────────────┴──────────────┴──────────────┘
"""

import sys, os, json, math, io as _io, time
sys.stdout.reconfigure(encoding='utf-8')

from config import client as llm_client, MODEL as LLM_MODEL

print("=" * 65)
print("Day 20 — Agent + RAG 混合系统")
print("=" * 65)
print()

print("""
┌────────────────────────────────────────────────────────────────┐
│  回顾三周学习路线：                                               │
│                                                                │
│  Week 1: 学会调 API ── 从 Hello World 到健壮的 AI 应用          │
│  Week 2: 搭建 RAG ── 从文档加载到检索增强生成                   │
│  Week 3: 构建 Agent ── 从 Function Calling 到自主编排           │
│                                                                │
│  今天是 Week 3 的收官之作：把 Week 2 的 RAG 能力注入 Agent。      │
│  让 Agent 成为一个真正「内外兼修」的智能助手。                    │
│                                                                │
│  内部知识（RAG）：你的文档、教材、公司内部资料                    │
│  外部知识（搜索）：互联网最新信息、新闻、实时数据                  │
│                                                                │
│  Agent 的核心价值：自主判断什么时候用哪个知识源。                  │
└────────────────────────────────────────────────────────────────┘
""")

input("按 Enter 进入实验 1：为什么要 Agent + RAG 混合...")

# ============================================================
# 实验 1：为什么需要 Agent + RAG 混合
# ============================================================
print("\n" + "=" * 65)
print("实验 1：单一方案的局限 —— 为什么要混合？")
print("=" * 65)
print()

print("""
  三种 AI 应用的局限性：

  场景 A：「什么是 RAG？它怎么解决幻觉问题？」
    - 纯 LLM：可能回答对，但不是基于你的领域知识
    - 纯搜索 Agent：搜索互联网，信息质量参差不齐
    - 纯 RAG：如果你的知识库里有专门讲 RAG 的章节 → 完美！
    → 这种问题：RAG 最优

  场景 B：「2026年7月 AI 行业有哪些最新动态？」
    - 纯 LLM：训练数据截至某个时间点，不知道 7 月的事
    - 纯搜索 Agent：搜索最新视频 → 有信息
    - 纯 RAG：知识库里可能是几个月前的文档
    → 这种问题：搜索 Agent 最优

  场景 C：「对比我知识库里的 AI 框架 和 2026年最新的框架趋势」
    - 纯 LLM：可能编造，没有权威来源
    - 纯搜索 Agent：能搜到最新趋势，但没有你的内部资料做基准
    - 纯 RAG：只能基于知识库，看不到最新趋势
    → 这种问题：只有混合 Agent 能胜任！

  结论：真实世界的需求往往是混合的——既有需要查资料的部分，
        又有需要看最新动态的部分。混合 Agent = 最佳方案。
""")

# ══════════════════════════════════════════════════════════
# 先用一个简单测试，展示不同方案的差异
# ══════════════════════════════════════════════════════════

print("─" * 50)
print("快速演示：同一个问题，三种方案，三种答案")
print()

test_q = "什么是 RAG（检索增强生成）？它的核心流程是什么？"

print(f"  ❓ 问题：{test_q}")
print()

# 方案 A：纯 LLM
print("  ── 方案 A：纯 LLM（不查资料，凭记忆）──")
resp_a = llm_client.chat.completions.create(
    model=LLM_MODEL,
    messages=[{"role": "user", "content": test_q}],
    temperature=0.0,
)
answer_a = resp_a.choices[0].message.content
print(f"    回答：{answer_a[:150]}...")
print(f"    ⚠️ 可能正确，但无法验证来源，无法保证和你知识库一致")
print()

# 方案 B：纯 RAG（查知识库）
print("  ── 方案 B：纯 RAG（只查知识库）──")

# 加载 Chroma 知识库
import chromadb
import datetime as _dt

CHROMA_PATH = os.path.join(os.path.dirname(__file__), "chroma_db")
chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)

# 查找可用 collection
all_collections = chroma_client.list_collections()
KB_COLLECTION_NAME = None
for c in all_collections:
    if c.name in ("knowledge_base", "day11_kb"):
        KB_COLLECTION_NAME = c.name
        break

if KB_COLLECTION_NAME:
    collection = chroma_client.get_collection(KB_COLLECTION_NAME)
    # 获取查询向量
    q_emb = llm_client.embeddings.create(
        model="text-embedding-v2",
        input=[test_q],
    ).data[0].embedding

    rag_results = collection.query(query_embeddings=[q_emb], n_results=3)
    context_chunks = rag_results.get("documents", [[]])[0]
    metadatas = rag_results.get("metadatas", [[]])[0]

    if context_chunks:
        rag_context = "\n\n".join([f"[资料{i}] {c}" for i, c in enumerate(context_chunks, 1)])
        rag_prompt = f"""你是一个知识库问答助手。严格基于以下资料回答问题。
如果资料中找不到相关信息，请明确说「资料中未提及」。

参考资料：
{rag_context}

问题：{test_q}

请用中文回答，标注引用的资料编号。"""

        resp_b = llm_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": rag_prompt}],
            temperature=0.0,
        )
        answer_b = resp_b.choices[0].message.content
        print(f"    检索到 {len(context_chunks)} 个相关块")
        print(f"    回答：{answer_b[:150]}...")
        print(f"    ✅ 基于知识库，可溯源，但局限于知识库内容")
    else:
        print(f"    ⚠️ 知识库中未找到相关内容")
else:
    print(f"    ⚠️ 未找到可用知识库 collection")

print()
print("  🔑 关键洞察：")
print("    RAG 给了「权威性」（基于你的资料）")
print("    搜索给了「时效性」（最新信息）")
print("    混合 Agent 把两者结合起来 → 既有权威基础，又能追踪最新动态")

input("\n按 Enter 进入实验 2：构建 knowledge_base_search 工具...")

# ============================================================
# 实验 2：把 Chroma 检索封装为 Function Calling 工具
# ============================================================
print("\n" + "=" * 65)
print("实验 2：构建 knowledge_base_search 工具")
print("=" * 65)
print()

print("""
  今天最核心的工作：把 RAG 检索封装成一个 Agent 工具。

  设计要点：
    1. 函数签名：knowledge_base_search(query, n_results=3)
    2. 输入：自然语言查询字符串
    3. 处理：Embedding → Chroma 检索 → 格式化
    4. 输出：格式化的上下文文本（含相似度分数和来源）
    5. schema 描述：明确告诉 LLM 这是「内部知识库」、什么时候用

  这和我们封装 web_search 的思路完全一致——
  都是「把外部能力包装成 LLM 可理解的函数接口」。
""")

print("─" * 50)
print("2.1 加载 Chroma 知识库")
print()

if KB_COLLECTION_NAME:
    collection = chroma_client.get_collection(KB_COLLECTION_NAME)
    doc_count = collection.count()
    print(f"  ✅ 已加载知识库「{KB_COLLECTION_NAME}」")
    print(f"     Collection 路径：{CHROMA_PATH}")
    print(f"     文档数量：{doc_count} 个 chunk")
    print(f"     元数据示例：{collection.get(limit=1)['metadatas']}")
else:
    print("  ⚠️ 未找到知识库，正在从 data/ai_knowledge_base.txt 构建...")

    # 加载文档
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    kb_path = os.path.join(os.path.dirname(__file__), "data", "ai_knowledge_base.txt")
    with open(kb_path, "r", encoding="utf-8") as f:
        kb_text = f.read()

    # 切割
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500, chunk_overlap=80,
        separators=["\n\n", "\n", "。", "！", "？", "，", " ", ""],
    )
    chunks = text_splitter.split_text(kb_text)
    print(f"    文档切割完成：{len(chunks)} 个 chunk")

    # 向量化
    all_embeddings = []
    batch_size = 10
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        resp = llm_client.embeddings.create(
            model="text-embedding-v2",
            input=batch,
        )
        all_embeddings.extend([d.embedding for d in resp.data])

    # 存储到 Chroma
    collection = chroma_client.get_or_create_collection(
        name="knowledge_base",
        metadata={"source": "ai_knowledge_base.txt", "created_by": "day20_agent_rag.py"},
    )

    # 如果有新数据才添加
    if collection.count() == 0:
        for i, (chunk, emb) in enumerate(zip(chunks, all_embeddings)):
            collection.add(
                ids=[f"kb_{i}"],
                embeddings=[emb],
                documents=[chunk],
                metadatas=[{"chunk_id": i, "source": "ai_knowledge_base.txt"}],
            )

    KB_COLLECTION_NAME = "knowledge_base"
    doc_count = collection.count()
    print(f"  ✅ 知识库构建完成：{doc_count} 个 chunk 已入库")

print()

# ── 2.2 封装 RAG 工具函数 ──
print("─" * 50)
print("2.2 封装 knowledge_base_search 工具")
print()

def knowledge_base_search(query: str, n_results: int = 3) -> str:
    """
    Agent 工具：在本地知识库中进行语义检索。

    内部流程：
      1. 将查询转为向量（text-embedding-v2）
      2. 在 Chroma 中检索最相似的 n_results 个 chunk
      3. 格式化为 LLM 友好的文本返回
    """
    global collection

    if collection is None or collection.count() == 0:
        return "（知识库为空，请联系管理员添加文档）"

    # 1. Embedding
    q_emb = llm_client.embeddings.create(
        model="text-embedding-v2",
        input=[query],
    ).data[0].embedding

    # 2. 检索
    results = collection.query(
        query_embeddings=[q_emb],
        n_results=min(n_results, collection.count()),
    )

    docs = results.get("documents", [[]])[0]
    distances = results.get("distances", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    if not docs:
        return f"（知识库中未找到与「{query}」相关的内容）"

    # 3. 格式化
    parts = []
    for i, (doc, dist, meta) in enumerate(zip(docs, distances, metadatas), 1):
        # 百炼 text-embedding-v2 向量未 L2 归一化，欧氏距离无固定上界
        # 用 1/(1+dist) 映射到 (0,1)，再转为百分制
        # 典型值：dist≈0.8→55%, dist≈1.0→50%, dist≈1.4→42%, dist≈2.0→33%
        score = 1.0 / (1.0 + dist) if dist else 1.0
        score_pct = round(score * 100)

        # 相关性标签
        if score_pct >= 55:
            relevance = "★★★ 高度相关"
        elif score_pct >= 40:
            relevance = "★★☆ 相关"
        elif score_pct >= 30:
            relevance = "★☆☆ 部分相关"
        else:
            relevance = "☆☆☆ 弱相关"

        source = meta.get("source", "未知来源") if meta else "未知来源"
        chunk_id = meta.get("chunk_id", "?") if meta else "?"

        # 截断过长的文本
        doc_text = doc[:500] + "..." if len(doc) > 500 else doc

        parts.append(
            f"[知识库片段 {i}] {relevance} | 来源: {source}\n"
            f"{doc_text}"
        )

    header = f"📚 知识库检索结果（共 {len(parts)} 条）\n"
    return header + "\n\n" + "\n\n".join(parts)


# ── 2.3 注册为 Function Calling Schema ──
KNOWLEDGE_BASE_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "knowledge_base_search",
        "description": (
            "在本地知识库中进行语义检索。知识库包含：AI应用开发、LLM基础、Prompt工程、"
            "RAG系统、Agent开发、LangChain等领域的专业知识。"
            "当用户询问以下类型问题时，应优先使用此工具：\n"
            "1. 概念解释（如：什么是RAG？什么是Embedding？）\n"
            "2. 技术原理（如：Agent的Planning机制是什么？）\n"
            "3. 最佳实践（如：chunk_size应该怎么设？）\n"
            "4. 框架用法（如：LangChain怎么加载文档？）\n"
            "⚠️ 对于最新新闻、实时数据、价格、天气等时效性问题，请使用 web_search，"
            "不要使用 knowledge_base_search。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "检索查询语句。使用自然语言描述你要找的信息，10-30字为佳。"
                },
                "n_results": {
                    "type": "integer",
                    "description": "返回结果数量，默认3。需要更全面信息时可设为5。"
                },
            },
            "required": ["query"],
        },
    },
}

print("""
  knowledge_base_search 工具 Schema 设计要点：

  1. description 明确列出「什么时候用」和「什么时候不用」
     → 防止 Agent 用知识库搜索最新新闻（应该用 web_search）
     → 也防止 Agent 用搜索查概念解释（应该用 knowledge_base_search）

  2. 参数设计简洁
     → query（必填）：自然语言描述
     → n_results（可选，默认3）

  3. 返回格式友好
     → 标注相似度分数（让 Agent 判断可信度）
     → 标注来源文件（让 Agent 引用时有据可查）
     → 限制长度（避免撑爆上下文窗口）
""")

# ── 2.4 快速测试 ──
print("─" * 50)
print("2.3 快速测试 knowledge_base_search")
print()

test_queries = [
    "什么是RAG？",
    "Embedding 的作用是什么？",
    "Agent 和 RAG 有什么区别？",
]

for q in test_queries:
    result = knowledge_base_search(q, n_results=2)
    preview = result[:120].replace("\n", " ")
    print(f"  查询：「{q}」")
    print(f"  结果：{preview}...")
    print()

input("\n按 Enter 进入实验 3：混合 Agent 实战...")

# ============================================================
# 实验 3：混合 Agent —— 知识库 + 搜索 + 计算 同时就位
# ============================================================
print("\n" + "=" * 65)
print("实验 3：混合 Agent 实战 —— 5 个工具同时就位")
print("=" * 65)
print()

# ── 复用 Day 18 的工具 ──
CURRENT_DATE = _dt.datetime.now().strftime("%Y年%m月%d日")
CURRENT_WEEKDAY = ["星期一","星期二","星期三","星期四","星期五","星期六","星期日"][_dt.datetime.now().weekday()]

import requests
import statistics as _statistics, random as _random, re as _re, json as _json
import collections as _collections, itertools as _itertools
import fractions as _fractions, decimal as _decimal, functools as _functools

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.bilibili.com/",
}

# Tool 1: calculator
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

# Tool 2: get_current_time
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

# Tool 3: web_search (Day 18 版本)
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

        raw_text = resp.text.strip()
        if not raw_text:
            return f"搜索失败：B站返回空响应"

        try:
            data = resp.json()
        except Exception:
            return f"搜索失败：B站返回非JSON数据"

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

# Tool 4: python_repl
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
    'math': math, 'json': _json, 'datetime': _dt, 'random': _random,
    'statistics': _statistics, 'collections': _collections,
    'itertools': _itertools, 're': _re, 'fractions': _fractions,
    'decimal': _decimal, 'functools': _functools,
}

def python_repl(code: str, timeout_seconds: int = 5) -> str:
    namespace = {'__builtins__': SAFE_BUILTINS, **SAFE_MODULES}
    stdout = _io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = stdout
    try:
        compiled = compile(code, '<agent_repl>', 'exec')
        exec(compiled, namespace)
        output = stdout.getvalue()
        return output.rstrip() if output.rstrip() else '（代码执行完成，无输出）'
    except SyntaxError as e:
        return f'语法错误：第{e.lineno}行 - {e.msg}'
    except Exception as e:
        return f'执行错误：{type(e).__name__}: {e}'
    finally:
        sys.stdout = old_stdout

# ── 注册所有工具 ──
ALL_TOOLS = {
    "knowledge_base_search": {
        "schema": KNOWLEDGE_BASE_TOOL_SCHEMA,
        "func": lambda query, n_results=3: knowledge_base_search(query, n_results),
    },
    "web_search": {
        "schema": {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": (
                    "搜索B站视频获取外部实时信息。每条结果包含【发布时间】。"
                    "用于：最新新闻、行业动态、实时数据、价格、工具测评等时效性问题。"
                    "时效性问题必须设 sort='newest' 按最新发布排序。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索关键词，5-15个字"},
                        "max_results": {"type": "integer", "description": "返回条数，默认5"},
                        "sort": {
                            "type": "string",
                            "enum": ["relevance", "newest"],
                            "description": "综合排序/最新发布。时效性问题必须用newest"
                        }
                    },
                    "required": ["query"]
                }
            }
        },
        "func": lambda query, max_results=5, sort="relevance": web_search(query, max_results, sort == "newest"),
    },
    "calculator": {
        "schema": {
            "type": "function",
            "function": {
                "name": "calculator",
                "description": "计算数学表达式。用于精确数学计算。",
                "parameters": {
                    "type": "object",
                    "properties": {"expression": {"type": "string", "description": "数学表达式"}},
                    "required": ["expression"]
                }
            }
        },
        "func": lambda expression: calculator(expression),
    },
    "get_current_time": {
        "schema": {
            "type": "function",
            "function": {
                "name": "get_current_time",
                "description": "获取当前日期、时间或星期几。",
                "parameters": {
                    "type": "object",
                    "properties": {"format_type": {"type": "string", "enum": ["datetime", "date", "time", "weekday"]}},
                    "required": ["format_type"]
                }
            }
        },
        "func": lambda format_type="datetime": get_current_time(format_type),
    },
    "python_repl": {
        "schema": {
            "type": "function",
            "function": {
                "name": "python_repl",
                "description": (
                    "执行 Python 代码并返回输出。用于数据处理、统计分析、批量计算等。"
                    "使用 print() 输出结果。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {"code": {"type": "string", "description": "Python 代码，用 print() 输出"}},
                    "required": ["code"]
                }
            }
        },
        "func": lambda code: python_repl(code),
    },
}

ALL_TOOL_SCHEMAS = [t["schema"] for t in ALL_TOOLS.values()]

print(f"  ✅ 已注册 {len(ALL_TOOLS)} 个工具：")
for name, t in ALL_TOOLS.items():
    desc = t['schema']['function']['description'][:70]
    icon = {"knowledge_base_search": "📚", "web_search": "🔍", "calculator": "🔢",
            "get_current_time": "🕐", "python_repl": "🐍"}.get(name, "🔧")
    print(f"    {icon} {name}: {desc}...")
print()

# ── Agent 循环 ──
print("─" * 50)
print("Agent 循环引擎（与 Day 18 相同的 run_agent）")
print("─" * 50)
print()

def run_agent(user_query: str, system_prompt: str = None,
              max_iterations: int = 6, verbose: bool = True,
              tools_enabled: list[str] = None) -> dict:
    """运行 Agent 循环"""
    if tools_enabled is None:
        tool_schemas = ALL_TOOL_SCHEMAS
        tool_names_str = "全部"
    else:
        tool_schemas = [ALL_TOOLS[n]["schema"] for n in tools_enabled if n in ALL_TOOLS]
        tool_names_str = ", ".join(tools_enabled)

    if system_prompt is None:
        system_prompt = (
            f"当前日期：{CURRENT_DATE} {CURRENT_WEEKDAY}\n\n"
            f"你是一个具备「内部知识库 + 外部搜索」双通道的智能助手。\n\n"
            f"## 你的工具箱\n"
            f"- 📚 knowledge_base_search: 搜索本地知识库（AI/LLM/RAG/Agent/Prompt工程等专业知识）\n"
            f"- 🔍 web_search: 搜索外部互联网（B站视频，获取最新信息）\n"
            f"- 🐍 python_repl: 执行Python代码（数据处理、统计分析、批量运算）\n"
            f"- 🔢 calculator: 快速数学计算\n"
            f"- 🕐 get_current_time: 获取当前日期时间\n\n"
            f"## ⚠️ 工具选择原则（严格遵守！）\n"
            f"1. ⚠️ 概念/原理/框架/技术解释类问题 → 必须先调用 📚 knowledge_base_search！\n"
            f"   不要凭记忆回答，必须从知识库检索后基于检索结果回答。\n"
            f"   示例：问「什么是RAG/Embedding/Agent」→ 先查知识库\n"
            f"2. 最新新闻、实时数据、行业动态、价格 → 🔍 web_search（外部搜索）\n"
            f"3. 两者都相关的综合问题 → 同时调用 knowledge_base_search + web_search\n"
            f"   （先建立理论基础，再补充最新动态，两个工具可以在同一轮并行调用）\n"
            f"4. 数据处理/统计分析 → 🐍 python_repl\n"
            f"5. 简单数学计算 → 🔢 calculator\n"
            f"6. 只有纯粹的闲聊/问候/常识问题才可以直接回答\n\n"
            f"## 答案格式要求\n"
            f"- 基于知识库的内容标注为「📚 内部资料」\n"
            f"- 基于搜索的内容标注为「🔍 外部信息」\n"
            f"- 如果信息来源之间存在矛盾，明确指出并给出判断\n"
            f"- ❌ 禁止：在没有调用知识库的情况下，声称信息来自「内部资料」"
        )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query},
    ]

    tool_calls_log = []
    iterations = 0
    finish_reason = ""

    while iterations < max_iterations:
        iterations += 1

        if verbose:
            print(f"\n  ══ Round {iterations} ══")

        response = llm_client.chat.completions.create(
            model=LLM_MODEL, messages=messages,
            tools=tool_schemas if tool_schemas else None,
            temperature=0.0,
        )

        msg = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        if verbose:
            print(f"    finish_reason: {finish_reason}")

        if finish_reason == "stop":
            answer = msg.content or ""
            if verbose:
                preview = answer[:120].replace("\n", " ") + ("..." if len(answer) > 120 else "")
                print(f"    ✅ 完成 → {preview}")
            break

        elif msg.tool_calls:
            names = [tc.function.name for tc in msg.tool_calls]
            if verbose:
                print(f"    🔧 调用：{', '.join(names)}")

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
                result = ALL_TOOLS[name]["func"](**args)

                if verbose:
                    preview = result[:100].replace("\n", " | ")
                    print(f"    📊 {name} → {preview}{'...' if len(result) > 100 else ''}")

                tool_calls_log.append({
                    "round": iterations, "tool": name, "args": args, "result": result
                })
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
        else:
            break

    if iterations >= max_iterations and finish_reason not in ("stop", ""):
        answer = f"Agent 达到最大步数（{max_iterations}），已停止。"

    return {
        "answer": answer, "iterations": iterations,
        "tool_calls": tool_calls_log, "history": messages
    }

# ── 3.1 意图识别测试 ──
print("─" * 50)
print("3.1 意图识别测试：同样的问题，Agent 自己选择用什么工具")
print()

test_queries_v3 = [
    ("纯概念", "什么是 Embedding？它在 RAG 中起什么作用？"),
    ("实时信息", "2026年7月 AI 应用开发有什么最新趋势？"),
    ("混合问题", "我的知识库里讲了 RAG 的工作原理。但现在（2026年7月）RAG 技术有什么最新的发展方向？"),
    ("计算+知识", "如果 Token 的价格是 0.002元/千token，处理10万字中文大约需要多少费用？（提示：中文1-2字符≈1 token）"),
]

for label, query in test_queries_v3:
    print(f"\n  🏷️  [{label}] {query[:80]}...")
    result = run_agent(query, verbose=False)
    tools_used = [tc["tool"] for tc in result["tool_calls"]]
    tool_icons = " → ".join([{
        "knowledge_base_search": "📚", "web_search": "🔍",
        "calculator": "🔢", "python_repl": "🐍", "get_current_time": "🕐"
    }.get(t, t) for t in tools_used]) if tools_used else "(直接回答)"
    print(f"      🔗 工具链：{tool_icons}")
    print(f"      📝 回答：{result['answer'][:120].replace(chr(10), ' ')}...")
    print(f"      📊 {result['iterations']} 轮 · {len(result['tool_calls'])} 次调用")

print()
print("  🔑 观察：Agent 自动区分了「查知识库」和「查外部」的场景。")
print("     「纯概念」→ 只用知识库，「实时信息」→ 只用搜索，「混合」→ 知识库+搜索。")

input("\n按 Enter 进入实验 4：来源感知综合...")

# ============================================================
# 实验 4：来源感知综合 —— Agent 融合内外部信息
# ============================================================
print("\n" + "=" * 65)
print("实验 4：来源感知综合 —— Agent 如何融合内外部信息")
print("=" * 65)
print()

print("""
  混合 Agent 最强大但也是最难的地方：来源融合。

  Agent 需要：
    1. 从知识库获取「理论基础」（如 Prompt 工程的最佳实践）
    2. 从搜索引擎获取「最新动态」（如 2026 年 Prompt 工程新玩法）
    3. 将两者融合成连贯的回答
    4. 明确标注每部分信息来自哪里

  这要求 Agent 具备「来源感知」（Source Awareness）——
  知道什么信息来自哪里，可信度如何，有没有矛盾。

  下面用三个不同难度的任务测试 Agent 的融合能力。
""")

# ── 场景 A：基础融合 ──
print("╔" + "═" * 55 + "╗")
print("║  场景 A：内部知识 + 外部补充")
print("╚" + "═" * 55 + "╝")

task_a = (
    "请从以下几个方面对比 RAG 和 Agent 两种 AI 应用架构：\n"
    "1. 基本概念和工作原理（优先用内部知识库）\n"
    "2. 2026年的最新发展趋势和应用案例（搜索外部信息）\n"
    "3. 什么时候该用 RAG，什么时候该用 Agent，什么时候该结合两者？\n"
    "请明确标注每部分的信息来源。"
)

print(f"\n  📋 任务：{task_a[:100]}...")
print()

result_a = run_agent(task_a, max_iterations=8)

print(f"\n  {'─' * 50}")
print(f"  📝 Agent 最终回答：")
print(f"  {'─' * 50}")
print(f"  {result_a['answer'][:600]}")
print(f"\n  ...（共 {len(result_a['answer'])} 字符）")

print(f"\n  📊 工具调用链（{len(result_a['tool_calls'])} 次）：")
for i, tc in enumerate(result_a["tool_calls"], 1):
    if tc['tool'] == 'knowledge_base_search':
        print(f"    {i}. R{tc['round']} 📚 知识库: \"{tc['args'].get('query', '')}\"")
    elif tc['tool'] == 'web_search':
        print(f"    {i}. R{tc['round']} 🔍 搜索: \"{tc['args'].get('query', '')}\"")
    else:
        print(f"    {i}. R{tc['round']} {tc['tool']}")

print()
print("  🔑 关键观察：Agent 应该先查知识库建立基础，再搜外部补充最新动态。")

# ── 场景 B：矛盾检测 ──
print("\n\n╔" + "═" * 55 + "╗")
print("║  场景 B：信息冲突检测 —— 知识库 vs 外部信息")
print("╚" + "═" * 55 + "╝")

task_b = (
    f"据我所知，我的知识库（{CURRENT_DATE}之前创建）中记录了一些 AI 技术最佳实践。\n"
    "请帮我做以下分析：\n"
    "1. 从知识库中检索关于「Prompt 工程最佳实践」的内容\n"
    "2. 从外部搜索2026年最新的 Prompt 工程技术\n"
    "3. 对比内外部信息：哪些做法依然有效？哪些已经过时？\n"
    "4. 如果存在矛盾，明确指出并给出你的判断"
)

print(f"\n  📋 任务：{task_b[:120]}...")
print()

result_b = run_agent(task_b, max_iterations=8)

print(f"\n  {'─' * 50}")
print(f"  📝 Agent 回答：")
print(f"  {'─' * 50}")
print(f"  {result_b['answer'][:500]}")
print(f"\n  ...（共 {len(result_b['answer'])} 字符）")

print(f"\n  📊 工具调用链：")
for i, tc in enumerate(result_b["tool_calls"], 1):
    icon = "📚" if tc['tool'] == 'knowledge_base_search' else "🔍" if tc['tool'] == 'web_search' else "🔧"
    print(f"    {i}. R{tc['round']} {icon} {tc['tool']}(\"{tc['args'].get('query', tc['args'].get('expression', ''))}\")")

print()
print("  🔑 来源冲突检测是 Agent 高级能力的关键标志。")

# ── 场景 C：综合研究 ──
print("\n\n╔" + "═" * 55 + "╗")
print("║  场景 C：综合研究 —— 知识库 + 搜索 + 数据分析")
print("╚" + "═" * 55 + "╝")

task_c = (
    "请做一份关于「2026年 AI 应用开发工程师 学习路线」的综合分析：\n"
    "1. 从知识库检索 AI 应用开发的核心知识点（LLM、RAG、Agent 等）\n"
    "2. 搜索外部最新的招聘要求（需要什么技能、有什么新要求）\n"
    "3. 用 Python 把知识库知识点和招聘要求做一个技能覆盖矩阵\n"
    "4. 给出「最有价值的学习顺序」建议\n"
    "请标注信息来源。"
)

print(f"\n  📋 任务（需要 3 种工具协作）：{task_c[:120]}...")
print()

result_c = run_agent(task_c, max_iterations=10)

print(f"\n  {'─' * 50}")
print(f"  📝 Agent 回答：")
print(f"  {'─' * 50}")
print(f"  {result_c['answer'][:600]}")
print(f"\n  ...（共 {len(result_c['answer'])} 字符）")

# ── 工具使用统计 ──
tool_counts = {}
for tc in result_c["tool_calls"]:
    tool_counts[tc["tool"]] = tool_counts.get(tc["tool"], 0) + 1
print(f"\n  📈 工具使用分布：{tool_counts}")
print(f"  📊 总轮数：{result_c['iterations']} · 总调用：{len(result_c['tool_calls'])}")

print()
print("  🔑 这才是混合 Agent 的真正价值——3 种工具协作完成复杂研究任务。")

input("\n按 Enter 进入实验 5：对比实验...")

# ============================================================
# 实验 5：对比实验 — 纯 RAG vs 纯搜索 vs 混合 Agent
# ============================================================
print("\n" + "=" * 65)
print("实验 5：三方对比 —— 纯 RAG vs 纯搜索 vs 混合 Agent")
print("=" * 65)
print()

print("""
  实验设计：同一个复杂问题，用三种方案分别回答。
  对比维度：完整性、时效性、准确性、可溯源、灵活性。

  问题设计为「混合型」——既需要内部知识又需要外部信息。
""")

comparison_task = (
    "对比分析：AI Agent 系统在2026年的主流架构方案。\n"
    "请包含以下内容：\n"
    "1. Agent 的基本架构模式（ReAct、Plan-Execute 等）\n"
    "2. 2026年最新的 Agent 框架和工具\n"
    "3. 各架构的优缺点和适用场景"
)

print(f"  📋 统一测试问题：")
print(f"     {comparison_task[:100]}...")
print()

# ── 方案 A：纯 RAG（只允许 knowledge_base_search）──
print("━" * 45)
print("方案 A：纯 RAG Agent（只提供 knowledge_base_search）")
print("━" * 45)
print()

result_a = run_agent(
    comparison_task,
    tools_enabled=["knowledge_base_search"],
    max_iterations=4,
    system_prompt=(
        f"当前日期：{CURRENT_DATE} {CURRENT_WEEKDAY}\n"
        f"你是一个知识库问答助手。你只能从本地知识库检索信息。\n"
        f"对于知识库中没有的信息，请诚实地标注「知识库中未找到」。\n"
        f"在答案末尾标注引用来源。"
    ),
)

print(f"\n  📝 纯 RAG 回答：")
print(f"  {'─' * 50}")
print(f"  {result_a['answer'][:400]}")
print(f"\n  ...（共 {len(result_a['answer'])} 字符）")
print(f"  📊 {result_a['iterations']} 轮 · {len(result_a['tool_calls'])} 次调用")

# ── 方案 B：纯搜索（只允许 web_search）──
print("\n\n━" * 45)
print("方案 B：纯搜索 Agent（只提供 web_search）")
print("━" * 45)
print()

result_b = run_agent(
    comparison_task,
    tools_enabled=["web_search"],
    max_iterations=6,
    system_prompt=(
        f"当前日期：{CURRENT_DATE} {CURRENT_WEEKDAY}\n"
        f"你是一个搜索助手。你必须通过 web_search 获取信息，不要凭记忆回答。\n"
        f"搜索结果来自B站视频，请注意甄别信息质量。\n"
        f"在答案末尾标注引用来源。"
    ),
)

print(f"\n  📝 纯搜索回答：")
print(f"  {'─' * 50}")
print(f"  {result_b['answer'][:400]}")
print(f"\n  ...（共 {len(result_b['answer'])} 字符）")
print(f"  📊 {result_b['iterations']} 轮 · {len(result_b['tool_calls'])} 次调用")

# ── 方案 C：混合 Agent（全部工具）──
print("\n\n━" * 45)
print("方案 C：混合 Agent（knowledge_base_search + web_search + python_repl）")
print("━" * 45)
print()

result_c = run_agent(
    comparison_task,
    tools_enabled=["knowledge_base_search", "web_search", "python_repl", "calculator", "get_current_time"],
    max_iterations=8,
)

print(f"\n  📝 混合 Agent 回答：")
print(f"  {'─' * 50}")
print(f"  {result_c['answer'][:400]}")
print(f"\n  ...（共 {len(result_c['answer'])} 字符）")
print(f"  📊 {result_c['iterations']} 轮 · {len(result_c['tool_calls'])} 次调用")

# ── 汇总对比 ──
print("\n\n" + "─" * 65)
print("三方对比结果汇总")
print("─" * 65)

print(f"""
  ┌──────────────────┬────────────────┬────────────────┬────────────────┐
  │      维度         │   方案 A       │   方案 B       │   方案 C       │
  │                  │   纯 RAG       │   纯搜索        │   混合 Agent   │
  ├──────────────────┼────────────────┼────────────────┼────────────────┤
  │ 工具调用           │ {result_a['tool_calls'][0]['tool'] if result_a['tool_calls'] else 'N/A':<14} │ {result_b['tool_calls'][0]['tool'] if result_b['tool_calls'] else 'N/A':<14} │ 多种组合         │
  │ 调用次数           │ {len(result_a['tool_calls']):<14} │ {len(result_b['tool_calls']):<14} │ {len(result_c['tool_calls']):<14} │
  │ 回答长度           │ {len(result_a['answer']):<14} │ {len(result_b['answer']):<14} │ {len(result_c['answer']):<14} │
  │ 轮数              │ {result_a['iterations']:<14} │ {result_b['iterations']:<14} │ {result_c['iterations']:<14} │
  └──────────────────┴────────────────┴────────────────┴────────────────┘
""")

print("  🔑 结论：")
print("    ✅ 纯 RAG：基础概念准确、可溯源，但缺少最新信息")
print("    ✅ 纯搜索：有最新信息，但缺少理论基础，信息质量参差不齐")
print("    ✅ 混合 Agent：既有理论基础，又有最新动态 → 最完整的答案")
print()
print("  💡 面试要点：")
print("     Q: 「你们公司的 AI 系统用 RAG 还是 Agent？」")
print("     A: 「我们的核心架构是 Agent + RAG 混合。Agent 负责任务编排和")
print("         工具调度，RAG 作为其中一个工具提供知识库检索能力。")
print("         这样既保留了 RAG 的准确性，又扩展了 Agent 的灵活性。」")

# ============================================================
# Day 20 总结
# ============================================================
print("\n\n" + "=" * 65)
print("Day 20 总结：你今天学到了什么")
print("=" * 65)
print("""
┌────────────────────────────────────────────────────────────────┐
│  1. 为什么要 Agent + RAG 混合                                   │
│     - 真实需求往往是混合的：既要查内部资料，又要看最新动态       │
│     - 单一方案总有盲区：RAG 缺时效性，搜索缺权威性               │
│     - 混合 = 互补 = 1+1 > 2                                    │
│                                                                │
│  2. RAG 作为 Tool 的封装方法                                      │
│     和 web_search 完全相同的模式：                               │
│     - Chroma 检索 → 格式化 → Function Calling Schema            │
│     - Schema description 明确告诉 LLM「什么时候用这个工具」       │
│     - 相似度分数 + 来源标注 → Agent 可以判断可信度               │
│                                                                │
│  3. 来源感知综合（Source-Aware Synthesis）                        │
│     - Agent 需要知道什么信息来自知识库、什么来自搜索             │
│     - 答案中明确标注来源 → 提高可信度和可解释性                  │
│     - 当内外部信息矛盾时 → Agent 应该指出并给出判断              │
│                                                                │
│  4. 混合 Agent 的工程模式                                        │
│     - 知识库用于「概念/原理/框架」类问题                         │
│     - 搜索引擎用于「最新/趋势/动态」类问题                       │
│     - Python/计算器用于「数据处理/分析」                         │
│     - System Prompt 中明确「工具选择原则」→ 减少误判             │
│                                                                │
│  5. 这个项目在简历上的描述（参考）                               │
│     「设计并实现了 Agent + RAG 混合 AI 助手，将 Chroma 向量     │
│       检索封装为 Function Calling 工具，Agent 在5个工具之间      │
│       自主决策编排，完成知识库检索、外部搜索、数据处理等多源     │
│       信息融合，答案带有明确来源标注。」                          │
└────────────────────────────────────────────────────────────────┘
""")

print(f"""
🔜 Day 21 预告：Week 3 复盘 + GitHub 发布
  - 整理 Day 15-20 的代码和文档
  - 对比三种 Agent 架构的优劣
  - 更新 README、写 Week 3 复盘文档
  - 准备进入 Week 4：FastAPI + 部署上线！

📊 三周完整回顾：
  Week 1 (Day 1-7):   学会调 API ── 从 Hello World 到 Streamlit Web 应用
  Week 2 (Day 8-14):  搭建 RAG ── 从文档加载到检索质量调优
  Week 3 (Day 15-20): 构建 Agent ── 从 Function Calling 到 Agent+RAG 混合系统

🎯 Week 3 完整工具箱：
  📚 knowledge_base_search — 知识库语义检索（今天新增！）
  🔍 web_search — B站搜索
  🐍 python_repl — Python 代码执行
  🔢 calculator — 数学计算
  🕐 get_current_time — 日期时间

🗂️ Week 3 代码文件：
  day15_agent_intro.py         — Agent 入门：Function Calling 基础
  day16_agent_search.py        — Agent + 搜索：国内多平台搜索
  day17_agent_python.py        — Agent + Python：沙箱执行+自我调试
  day18_agent_orchestration.py — 多工具编排：Plan-Execute + Reflection
  day19_agent_visual.py        — Streamlit 可视化监控台
  day20_agent_rag.py           — Agent + RAG 混合系统（今天！⭐）
""")

print(f"Day 20 完成 ✅ | 模型：{LLM_MODEL} | 工具：{len(ALL_TOOLS)} 个 | 实验：5 个")
print(f"Agent 工具箱：{', '.join(ALL_TOOLS.keys())}")
