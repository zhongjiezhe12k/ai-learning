"""
Day 16 - AI Agent + 网页搜索：让 Agent 拥有「实时信息」能力
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Day 15 我们让 Agent 学会了「算」和「查日期」。
但 Agent 的知识仍然被限制在模型的训练数据里。

今天给 Agent 装上「眼睛」—— 网页搜索工具。
从此 Agent 可以查实时信息：最新新闻、天气、股价、技术文档...

学完今天你会：
  ✅ 理解为什么 Agent 需要搜索能力（知识截止日期问题）
  ✅ 用 DuckDuckGo API 实现免费的网页搜索工具
  ✅ 让 Agent 自主判断「什么时候该搜索」
  ✅ 格式化搜索结果让 LLM 高效消费
  ✅ 对比有搜索 vs 无搜索的回答质量
  ✅ 搜索 + 计算器组合：查资料 → 算数据 → 综合回答

核心认知：
  ┌──────────────────────────────────────────────────────────────┐
  │  没有搜索的 Agent = 封闭系统（只靠模型记忆，幻想严重）          │
  │  有搜索的 Agent   = 开放系统（实时查证，信息准确）              │
  │  这就是 ChatGPT 付费版和免费版的核心差异之一                     │
  └──────────────────────────────────────────────────────────────┘
"""

import sys, os, json, math
sys.stdout.reconfigure(encoding='utf-8')

from config import client as llm_client, MODEL as LLM_MODEL

# ============================================================
# Day 15 回顾：AgentRunner 核心逻辑（精简版）
# ============================================================
print("=" * 65)
print("Day 16 — AI Agent + 网页搜索：让 Agent 拥有实时信息")
print("=" * 65)
print()

print("""
┌────────────────────────────────────────────────────────────────┐
│  回顾 Day 15：Agent = LLM + 工具 + 循环                          │
│                                                                │
│  Agent 收到问题 → 判断要不要用工具 → 执行工具 → 看结果 → 循环    │
│                                                                │
│  Day 15 的工具：calculator（计算器）+ get_current_time（时间）    │
│  问题：这两个工具都只处理「确定性的计算」，Agent 仍然不会获取       │
│        模型训练数据之外的新信息。                                 │
│                                                                │
│  Day 16 的目标：添加第三个工具 → web_search（网页搜索）           │
│  效果：Agent 从此可以查实时新闻、文档、天气、股价...              │
└────────────────────────────────────────────────────────────────┘
""")

input("按 Enter 进入实验 1：理解为什么需要搜索能力...")

# ============================================================
# 实验 1：LLM 的知识截止日期问题
# ============================================================
print("\n" + "=" * 65)
print("实验 1：为什么 Agent 需要搜索？—— LLM 的知识盲区")
print("=" * 65)
print()

# 问一个明显需要实时信息的问题
question = "2026年高考数学难度怎么样？和往年比有什么变化？"
print(f"🤔 测试问题：{question}")
print()

print("━" * 40)
print("场景 A：直接问 LLM（不提供搜索工具）")
print("━" * 40)

response_no_tool = llm_client.chat.completions.create(
    model=LLM_MODEL,
    messages=[
        {"role": "system", "content": "你是一个信息助手。"},
        {"role": "user", "content": question},
    ],
    temperature=0.0,
)

answer_no_search = response_no_tool.choices[0].message.content
print(f"  📝 回答：{answer_no_search[:200]}")
print()
print("  ⚠️ 问题分析：")
print("    - 模型训练数据有截止日期，可能不知道2026年7月的事")
print("    - 即使回答了，也无法验证真假")
print("    - 这就是「幻觉」的来源——模型在编造而非查证")

print("\n（自动进入实验 2...）")

# ============================================================
# 实验 2：实现 web_search 工具
# ============================================================
print("\n" + "=" * 65)
print("实验 2：实现网页搜索工具 —— 用 DuckDuckGo API")
print("=" * 65)
print()

# ── 2.1 搜索引擎选型 ──
print("─" * 50)
print("2.1 搜索引擎选型对比")
print()
print("""
  方案 A：Tavily Search API（海外）
    ✅ 专为 AI Agent 设计
    ❌ 需要 API Key，且是国外服务

  方案 B：DDGS / DuckDuckGo（海外）
    ✅ 免费无需 Key
    ❌ 底层访问 duckduckgo.com，国内被墙，一次搜索 17-25 秒

  方案 C：国内搜索引擎（我们今天用的）
    ✅ 国内直连，0.5-1.5 秒响应
    ✅ 无需 API Key，无次数限制
    ✅ 支持多平台切换（百度/Bing中国/哔哩哔哩/搜狗）

  选用国内方案的理由：快 20 倍，且和切换 Tavily 的代码逻辑完全一致。
""")

# ── 2.2 国内多平台搜索架构 ──
print("─" * 50)
print("2.2 国内搜索平台对比 + 架构设计")
print()

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# 哔哩哔哩需要额外的 Referer 头
BILIBILI_HEADERS = {
    **HEADERS,
    "Referer": "https://www.bilibili.com/",
}

# ╔══════════════════════════════════════════════════════════════╗
# ║  🔧 平台配置区 —— 想换搜索平台？改这里就行！                   ║
# ║                                                              ║
# ║  每个平台需要两个东西：                                        ║
# ║    1. url:     搜索 URL，用 {query} 作为关键词占位符            ║
# ║    2. parser:  解析函数，输入 requests.Response，输出结果列表    ║
# ║                                                              ║
# ║  返回格式统一为: [{"title": "标题", "body": "摘要", "href": "链接"}] ║
# ╚══════════════════════════════════════════════════════════════╝

# ── 平台1: Bing 中国版 — 通用搜索首选 ──
def _parse_bing(response) -> list[dict]:
    """解析 Bing 中国版搜索结果"""
    soup = BeautifulSoup(response.text, 'html.parser')
    results = []
    for item in soup.select('li.b_algo')[:10]:
        title_el = item.select_one('h2 a')
        body_el = item.select_one('.b_caption p, .b_lineclamp2')
        if title_el:
            results.append({
                "title": title_el.get_text(strip=True),
                "body": body_el.get_text(strip=True) if body_el else "",
                "href": title_el.get('href', ''),
            })
    return results

# ── 平台2: 哔哩哔哩 — 视频/教程/评测类搜索首选 ──
def _parse_bilibili(response) -> list[dict]:
    """解析哔哩哔哩搜索结果（JSON API，无需解析 HTML）"""
    data = response.json()
    results = []
    for r in data.get("data", {}).get("result", [])[:10]:
        # 去除 HTML 标签
        title = r.get("title", "").replace('<em class="keyword">', '').replace('</em>', '')
        desc = r.get("description", "")[:80]
        results.append({
            "title": title,
            "body": f"播放:{r.get('play',0)} | 弹幕:{r.get('video_review',0)} | {desc}",
            "href": f"https://www.bilibili.com/video/{r.get('bvid', '')}",
        })
    return results

# ── 平台3: 搜狗搜索 — 微信文章/中文内容搜索 ──
def _parse_sogou(response) -> list[dict]:
    """解析搜狗搜索结果"""
    soup = BeautifulSoup(response.text, 'html.parser')
    results = []
    for item in soup.select('.vrwrap, .rb')[:10]:
        title_el = item.select_one('.vr-title a, h3 a')
        body_el = item.select_one('.star-wiki, .str-text, .space-txt')
        if title_el:
            results.append({
                "title": title_el.get_text(strip=True),
                "body": body_el.get_text(strip=True) if body_el else "",
                "href": title_el.get('href', ''),
            })
    return results

# ╔══════════════════════════════════════════════════════════════╗
# ║  搜索引擎注册表 —— 添加新平台只需在这里加一行                   ║
# ╚══════════════════════════════════════════════════════════════╝
SEARCH_ENGINES = {
    "bing": {
        "name": "Bing 中国版",
        "url": "https://cn.bing.com/search?q={query}&ensearch=1",
        "parser": _parse_bing,
    },
    "bilibili": {
        "name": "哔哩哔哩",
        "url": "https://api.bilibili.com/x/web-interface/search/type?search_type=video&keyword={query}",
        "parser": _parse_bilibili,
    },
    "sogou": {
        "name": "搜狗搜索",
        "url": "https://www.sogou.com/web?query={query}",
        "parser": _parse_sogou,
    },
}

# 默认搜索引擎
DEFAULT_ENGINE = "bing"

print("  已注册搜索引擎：")
for key, engine in SEARCH_ENGINES.items():
    marker = " ← 默认" if key == DEFAULT_ENGINE else ""
    print(f"    {key}: {engine['name']}{marker}")
print()
print("  切换方法：")
print("    搜索时传参 engine='bilibili' 即可切换")
print("    添加新平台：在 SEARCH_ENGINES 字典加一项 + 写一个 _parse_xxx 函数")

# ── 2.3 统一搜索入口 ──
print("\n" + "─" * 50)
print("2.3 统一搜索入口 —— 替换原来的 raw_web_search")
print()

def raw_web_search(query: str, max_results: int = 5,
                   engine: str = None, timeout: float = 8.0) -> list[dict]:
    """
    统一搜索入口 —— 支持多平台切换。

    参数：
      query       : 搜索关键词
      max_results : 最大返回条数
      engine      : 搜索引擎名。可选: bing / bilibili / sogou。默认 bing。
      timeout     : 超时时间（秒）

    返回：
      [{"title": "...", "body": "...", "href": "..."}, ...]
    """
    engine = engine or DEFAULT_ENGINE

    if engine not in SEARCH_ENGINES:
        return [{"title": "错误", "body": f"未知搜索引擎 '{engine}'，可选：{list(SEARCH_ENGINES.keys())}", "href": ""}]

    cfg = SEARCH_ENGINES[engine]
    url = cfg["url"].format(query=query)

    # B站需要 Referer 头，其他平台用默认 headers
    hdrs = BILIBILI_HEADERS if engine == "bilibili" else HEADERS

    try:
        resp = requests.get(url, headers=hdrs, timeout=timeout)
        resp.raise_for_status()
        results = cfg["parser"](resp)
        return results[:max_results] if results else [
            {"title": "无结果", "body": f"「{query}」未找到相关结果", "href": ""}
        ]
    except requests.Timeout:
        return [{"title": "搜索超时", "body": f"搜索「{query}」超时（{timeout}秒）", "href": ""}]
    except Exception as e:
        return [{"title": "搜索失败", "body": str(e), "href": ""}]

# 测试各平台搜索速度
test_query = "2026年高考数学难度"
print(f"  搜索关键词：「{test_query}」")
print()

for eng_key in ["bing", "bilibili", "sogou"]:
    import time
    start = time.time()
    results = raw_web_search(test_query, max_results=2, engine=eng_key)
    elapsed = time.time() - start
    name = SEARCH_ENGINES[eng_key]["name"]
    if results and results[0].get("title") not in ("搜索超时", "搜索失败", "错误"):
        print(f"  ✅ {name}: {elapsed:.1f}s, {len(results)}条结果")
    else:
        print(f"  ❌ {name}: {elapsed:.1f}s, {results[0].get('title', '?')}")

# 用默认引擎展示详细结果
print(f"\n  ── 默认引擎（{SEARCH_ENGINES[DEFAULT_ENGINE]['name']}）搜索详情 ──")
results = raw_web_search(test_query, max_results=3)
for i, r in enumerate(results, 1):
    title = r['title'][:60] + "..." if len(r['title']) > 60 else r['title']
    body = r['body'][:100] + "..." if len(r['body']) > 100 else r['body']
    print(f"  [{i}] {title}")
    print(f"      {body}")
    print(f"      🔗 {r['href']}")
    print()

# ── 2.4 格式化为 LLM 友好格式 ──
print("─" * 50)
print("2.4 格式化搜索结果 —— 让 LLM 高效消费")
print()

def format_search_results(results: list[dict], max_body_len: int = 150) -> str:
    """
    将搜索结果格式化为 LLM 友好的文本。
    """
    if not results:
        return "（未找到相关搜索结果）"

    title = results[0].get("title", "")
    if title in ("搜索失败", "搜索超时", "错误", "无结果"):
        return f"（{title}：{results[0]['body']}）"

    parts = []
    for i, r in enumerate(results, 1):
        title = r["title"]
        body = r["body"][:max_body_len]
        url = r["href"]
        parts.append(f"[{i}] {title}\n    摘要：{body}\n    链接：{url}")
    return "\n\n".join(parts)

formatted = format_search_results(results)
print(f"\n  格式化后的搜索结果（共 {len(formatted)} 字符）：")
print(f"  {'─' * 50}")
print(f"  {formatted[:400]}...")
print()
print("  关键设计：")
print("    - 每个平台只需实现「URL模板」+「HTML/JSON解析函数」")
print("    - 切换平台 = 改 DEFAULT_ENGINE 或传参 engine='bilibili'")
print("    - 添加新平台 = SEARCH_ENGINES 加一项 + 写一个 _parse_xxx 函数")

# ── 2.5 封装为 Agent 工具 ──
print("\n" + "─" * 50)
print("2.5 封装为 Agent 工具函数")
print()

def web_search(query: str, max_results: int = 5) -> str:
    """
    Agent 工具：搜索互联网并返回格式化结果。

    这是给 Agent 调用的「门面函数」—— 内部调用 raw_web_search，
    外部只暴露一个简单的字符串接口。
    """
    results = raw_web_search(query, max_results)
    return format_search_results(results)

WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "搜索互联网获取实时信息。后端使用国内搜索引擎（Bing中国/哔哩哔哩/搜狗），"
            "速度快（<2秒）。当用户询问最新新闻、当前事件、"
            "实时数据、或任何你不知道的时效性信息时，必须使用此工具。"
            "不要凭记忆回答需要实时信息的问题。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词。中文搜索效果更好。精炼到5-15个字。"
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大返回条数，默认5。如果问题需要多角度信息可设置更多。"
                }
            },
            "required": ["query"]
        }
    }
}

print("""
  工具 Schema 设计要点：

  1. description 里明确写了「必须使用此工具」
     → 防止模型偷懒不搜索，凭记忆瞎编

  2. 参数设计简洁
     → query（必填）+ max_results（可选，默认5）

  3. 返回值是格式化字符串
     → 直接放进 LLM 上下文，无需二次处理
""")

print("\n（自动进入实验 3：Agent + 搜索实战...）")

# ============================================================
# 实验 3：Agent + 搜索实战 — 对比有搜索 vs 没有搜索
# ============================================================
print("\n" + "=" * 65)
print("实验 3：对比实验 —— 有搜索 Agent vs 无搜索 Agent")
print("=" * 65)
print()

# 从 Day 15 引入 AgentRunner（精简版，专注于今天的实验）
# 工具注册表
import datetime

CURRENT_DATE = datetime.datetime.now().strftime("%Y年%m月%d日")
CURRENT_WEEKDAY = ["星期一","星期二","星期三","星期四","星期五","星期六","星期日"][datetime.datetime.now().weekday()]

def get_current_time(format_type: str = "datetime") -> str:
    """获取当前时间"""
    now = datetime.datetime.now()
    if format_type == "date":
        return now.strftime("%Y年%m月%d日")
    elif format_type == "time":
        return now.strftime("%H:%M:%S")
    elif format_type == "weekday":
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        return weekdays[now.weekday()]
    else:
        return now.strftime("%Y年%m月%d日 %H:%M:%S") + f" {['星期一','星期二','星期三','星期四','星期五','星期六','星期日'][now.weekday()]}"

def calculator(expression: str) -> str:
    """安全计算数学表达式"""
    import math as _math
    allowed = {
        "abs": abs, "round": round, "min": min, "max": max,
        "pow": pow, "sqrt": _math.sqrt, "sin": _math.sin,
        "cos": _math.cos, "tan": _math.tan, "log": _math.log,
        "pi": _math.pi, "e": _math.e, "ceil": _math.ceil, "floor": _math.floor,
    }
    try:
        code = compile(expression, "<calc>", "eval")
        for name in code.co_names:
            if name not in allowed:
                return f"错误：'{name}' 不是允许的数学函数"
        return str(eval(code, {"__builtins__": {}}, allowed))
    except Exception as e:
        return f"计算错误：{e}"

# 完整工具集
ALL_TOOLS = {
    "web_search": {
        "schema": WEB_SEARCH_TOOL,
        "func": lambda query, max_results=5: web_search(query, max_results),
    },
    "calculator": {
        "schema": {
            "type": "function",
            "function": {
                "name": "calculator",
                "description": "计算数学表达式。用于任何需要精确计算的问题。",
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
}

ALL_TOOL_SCHEMAS = [t["schema"] for t in ALL_TOOLS.values()]

def execute_tool(name: str, args: dict) -> str:
    """工具分发器"""
    if name not in ALL_TOOLS:
        return f"错误：未知工具 '{name}'"
    try:
        return str(ALL_TOOLS[name]["func"](**args))
    except Exception as e:
        return f"工具执行失败：{e}"

# ── Agent 循环 ──
def run_agent(user_query: str, tools_enabled: list[str] = None,
              system_prompt: str = None, max_iterations: int = 5,
              verbose: bool = True) -> dict:
    """
    运行 Agent 循环。

    参数：
      user_query    : 用户问题
      tools_enabled : 启用的工具名列表。None = 全部启用。[] = 无工具（纯 LLM）。
    """
    if tools_enabled is None:
        tool_schemas = ALL_TOOL_SCHEMAS
    else:
        tool_schemas = [ALL_TOOLS[name]["schema"] for name in tools_enabled if name in ALL_TOOLS]

    if system_prompt is None:
        tool_names = ", ".join(tools_enabled) if tools_enabled else "无"
        system_prompt = (
            f"当前日期：{CURRENT_DATE} {CURRENT_WEEKDAY}\n"
            f"你是一个智能助手。你可以使用以下工具：{tool_names}。\n"
            f"规则：\n"
            f"1. 需要实时信息时，必须使用 web_search 工具，不要凭记忆回答\n"
            f"2. 搜索时使用精炼的关键词，优先用英文\n"
            f"3. 在答案中引用信息来源（标注编号和链接）\n"
            f"4. 不需要工具的问题可以直接回答"
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
            model=LLM_MODEL,
            messages=messages,
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
                print(f"    ✅ Agent 完成回答（{len(answer)} 字符）")
            break

        elif msg.tool_calls:
            if verbose:
                names = [tc.function.name for tc in msg.tool_calls]
                print(f"    🔧 调用工具：{', '.join(names)}")

            # 添加 assistant 消息（含 tool_calls）
            serialized = []
            for tc in msg.tool_calls:
                serialized.append({
                    "id": tc.id, "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                })
            messages.append({
                "role": "assistant", "content": msg.content or "", "tool_calls": serialized,
            })

            # 执行工具
            for tc in msg.tool_calls:
                name = tc.function.name
                args = json.loads(tc.function.arguments)
                result = execute_tool(name, args)

                if verbose:
                    result_preview = result[:80].replace("\n", " ") + ("..." if len(result) > 80 else "")
                    print(f"    📊 {name} → {result_preview}")

                tool_calls_log.append({"round": iterations, "tool": name, "args": args, "result": result})
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
        else:
            break

    if iterations >= max_iterations and finish_reason not in ("stop", ""):
        answer = f"Agent 达到最大步数（{max_iterations}），已强制停止。"

    return {"answer": answer, "iterations": iterations, "tool_calls": tool_calls_log, "history": messages}

# ── 对比测试 ──
print("╔" + "═" * 55 + "╗")
print("║  场景 A：无搜索 Agent（禁掉 web_search）")
print("╚" + "═" * 55 + "╝")

# 选一个明显的实时问题
real_time_question = "2026年高考数学难度如何？请搜索相关信息并总结。"

result_no_search = run_agent(
    real_time_question,
    tools_enabled=[],  # 空列表 = 没有工具
)

print(f"\n  📝 无搜索 Agent 回答：")
print(f"  {'─' * 50}")
print(f"  {result_no_search['answer'][:250]}")

print(f"\n\n╔" + "═" * 55 + "╗")
print(f"║  场景 B：有搜索 Agent（启用 web_search）")
print(f"╚" + "═" * 55 + "╝")

result_with_search = run_agent(
    real_time_question,
    tools_enabled=["web_search"],
)

print(f"\n  📝 有搜索 Agent 回答：")
print(f"  {'─' * 50}")
print(f"  {result_with_search['answer'][:350]}")
print(f"\n  📊 统计：{result_with_search['iterations']} 轮 · {len(result_with_search['tool_calls'])} 次工具调用")

print("\n  🔑 对比结论：")
print("    有搜索的 Agent：基于实时搜索结果回答，信息有时效性")
print("    无搜索的 Agent：只能凭训练数据猜测，可能过时或编造")

print("\n（自动进入实验 4：多工具协同...）")

# ============================================================
# 实验 4：多工具协同 —— 搜索 + 计算
# ============================================================
print("\n" + "=" * 65)
print("实验 4：多工具协同 —— 搜索查资料 + 计算器算数据")
print("=" * 65)
print()
print("  这才是 Agent 真正强大的地方：不是单个工具多厉害，")
print("  而是 Agent 能自主编排多个工具完成复杂任务。")
print()

# 场景：需要先搜索信息，再基于信息做计算
print("╔" + "═" * 55 + "╗")
print("║  综合任务：搜索 + 计算")
print("╚" + "═" * 55 + "╝")

complex_question = (
    "请搜索当前人民币对美元的汇率，"
    "然后计算：如果我要兑换 5000 美元，需要多少人民币？"
)

result_complex = run_agent(
    complex_question,
    tools_enabled=["web_search", "calculator"],
)

print(f"\n  📝 Agent 回答：")
print(f"  {'─' * 50}")
print(f"  {result_complex['answer']}")

print(f"\n  📊 工具调用链：")
for i, tc in enumerate(result_complex["tool_calls"], 1):
    print(f"    {i}. Round {tc['round']} → {tc['tool']}")
    args_str = json.dumps(tc['args'], ensure_ascii=False)
    print(f"       参数：{args_str}")
    result_preview = tc['result'][:100].replace("\n", " ")
    print(f"       结果：{result_preview}...")

print()
print("  🔑 观察：Agent 自主完成了 「先搜索汇率 → 再计算」 的流程。")
print("     你不需要写 if-else 告诉它步骤顺序——模型自己决定了。")

print("\n（自动进入实验 5：进阶用法...）")

# ============================================================
# 实验 5：进阶 —— 多步搜索 + 信息综合
# ============================================================
print("\n" + "=" * 65)
print("实验 5：进阶用法 —— 对比搜索 + 信息综合")
print("=" * 65)
print()

print("╔" + "═" * 55 + "╗")
print("║  进阶任务：多角度搜索 + 综合对比")
print("╚" + "═" * 55 + "╝")

compare_question = (
    "请分别搜索 Python 和 JavaScript 在 2026 年的最新发展趋势，"
    "然后做一个简短对比。"
)

result_compare = run_agent(
    compare_question,
    tools_enabled=["web_search"],
    max_iterations=6,  # 多步搜索需要更多轮次
)

print(f"\n  📝 Agent 回答：")
print(f"  {'─' * 50}")
print(f"  {result_compare['answer'][:400]}")

print(f"\n  📊 工具调用记录：")
for i, tc in enumerate(result_compare["tool_calls"], 1):
    print(f"    {i}. Round {tc['round']} → {tc['tool']}({json.dumps(tc['args'], ensure_ascii=False)})")

if len(result_compare["tool_calls"]) >= 2:
    print(f"\n  🔑 观察：Agent 可能需要多次搜索（Python + JavaScript 分别搜），")
    print(f"     然后在最后一次推理中综合两个搜索结果给出对比。")
    print(f"     这就是 Agent 比 RAG 更灵活的地方——能动态决定搜什么、搜几次。")

# ============================================================
# Day 16 总结
# ============================================================
print("\n" + "=" * 65)
print("Day 16 总结：你今天学到了什么")
print("=" * 65)
print("""
┌────────────────────────────────────────────────────────────────┐
│  1. 为什么 Agent 需要搜索                                        │
│     LLM 训练数据有截止日期 → 无法回答实时问题                    │
│     搜索让 Agent 从「封闭系统」变成「开放系统」                   │
│                                                                │
│  2. 网页搜索工具的工程实现                                       │
│     - DuckDuckGo API (ddgs 库)：免费、无需 Key                   │
│     - 三层封装：raw → format → tool function                    │
│     - 结果格式化：限制长度 + 编号 + 保留 URL                      │
│                                                                │
│  3. Agent 自主决策                                               │
│     - Agent 自己判断「什么时候该搜索」vs「可以直接回答」           │
│     - Agent 自己决定搜索关键词（你用自然语言提问即可）             │
│     - Agent 可以多次搜索、组合多个来源的信息                      │
│                                                                │
│  4. 多工具协同                                                   │
│     - 搜索 + 计算 = 查汇率 → 算金额                              │
│     - 搜索 + 搜索 = 多角度对比                                   │
│     - Agent 不需要你写流程控制代码                               │
│                                                                │
│  5. 搜索 Agent 的局限（面试常问）                                 │
│     - 搜索可能不准确或过时（免费 API 的代价）                     │
│     - 搜索结果可能太多，需要合理截断                              │
│     - 网络延迟增加响应时间                                       │
│     - 可能搜到低质量来源（需要 Agent 甄别）                       │
└────────────────────────────────────────────────────────────────┘
""")

print("""
🔜 Day 17 预告：给 Agent 安装「大脑」—— Python 代码执行工具
  - 让 Agent 执行 Python 代码（sandbox 安全模式）
  - 处理数据、画图、读写文件
  - 搜索 + 计算 + 代码执行 = 真正的「数字助手」

🔜 Day 18 预告：多工具串联 —— Agent 在复杂任务中自主切换工具
""")

print(f"\nDay 16 完成 ✅ | 模型：{LLM_MODEL} | 工具：{len(ALL_TOOLS)} 个")
