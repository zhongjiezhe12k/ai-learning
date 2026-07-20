"""
Day 18 - 多工具串联：Agent 自主决策与编排
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Day 15 我们让 Agent 学会了「算」和「查日期」（2个工具）
Day 16 我们让 Agent 学会了「搜」（+1个工具）
Day 17 我们让 Agent 学会了「写代码」（+1个工具）

但之前每个实验里，Agent 只用 1-3 个工具。今天把所有 4 个工具
同时交给 Agent——看它如何自主决定「用什么、按什么顺序、几轮调用」。

学完今天你会：
  ✅ 理解 Agent 如何在多工具间做选择（意图识别）
  ✅ 观察 Agent 自主编排复杂任务（搜索→Python→计算→格式化）
  ✅ 掌握 Plan-then-Execute 模式（先规划再执行，提高可靠性）
  ✅ 实现 Self-Reflection 循环（Agent 审查自己的答案并改进）
  ✅ 完整理解 Agent 的「智能」从何而来——不是工具多，是编排能力

核心认知：
  ┌──────────────────────────────────────────────────────────────┐
  │  Agent 的智能 ≠ 单个工具的能力                                 │
  │  Agent 的智能 = 在恰当的时候，选择恰当的工具，用恰当的顺序       │
  │                                                                │
  │  Day 15-17 = 造轮子（calculator, search, python）               │
  │  Day 18   = 开车（什么时候打方向盘、什么时候踩油门、什么时候刹车）│
  └──────────────────────────────────────────────────────────────┘
"""

import sys, os, json, math, io as _io, time
sys.stdout.reconfigure(encoding='utf-8')

from config import client as llm_client, MODEL as LLM_MODEL

print("=" * 65)
print("Day 18 — 多工具串联：Agent 自主决策与编排")
print("=" * 65)
print()

print("""
┌────────────────────────────────────────────────────────────────┐
│  回顾 Day 15-17：Agent 的工具箱逐步扩充                            │
│                                                                │
│  Day 15: calculator + get_current_time     (2 tools)           │
│  Day 16: + web_search                      (3 tools)           │
│  Day 17: + python_repl                     (4 tools)           │
│                                                                │
│  今天：把 4 个工具同时打开，看 Agent 如何「自主编排」               │
│                                                                │
│  类比：你有一个工具箱，里面有锤子、螺丝刀、电钻、锯子。             │
│        一个熟练的工匠知道什么情况下用哪个工具，以及使用的顺序。       │
│        Agent 的「智能」就体现在这个「知道」上。                    │
└────────────────────────────────────────────────────────────────┘
""")

input("按 Enter 进入实验 1：完整工具箱 —— 4 个工具同时就位...")

# ============================================================
# 实验 1：完整工具箱 —— 意图识别测试
# ============================================================
print("\n" + "=" * 65)
print("实验 1：完整工具箱 —— Agent 能否正确选择工具？")
print("=" * 65)
print()

# ── 构建所有工具 ──
print("─" * 50)
print("1.1 注册全部 4 个工具")
print()

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
import datetime as _dt
CURRENT_DATE = _dt.datetime.now().strftime("%Y年%m月%d日")
CURRENT_WEEKDAY = ["星期一","星期二","星期三","星期四","星期五","星期六","星期日"][_dt.datetime.now().weekday()]

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

# Tool 3: web_search（B站搜索 + 时间戳校验）
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.bilibili.com/",
}

def web_search(query: str, max_results: int = 5, fresh: bool = False) -> str:
    """
    B站视频搜索。返回标题 + 发布时间 + 描述 + 链接。

    参数：
      fresh: True=按最新发布排序（时效性问题必须用），False=按综合相关性排序
    """
    try:
        order = "pubdate" if fresh else "totalrank"
        url = (
            f"https://api.bilibili.com/x/web-interface/search/type"
            f"?search_type=video&keyword={query}&order={order}"
        )
        resp = requests.get(url, headers=HEADERS, timeout=8)

        if resp.status_code != 200:
            return f"搜索失败：HTTP {resp.status_code}（B站API暂时不可用）"

        raw_text = resp.text.strip()
        if not raw_text:
            return f"搜索失败：B站返回空响应（可能触发了反爬机制，请稍后重试）"

        try:
            data = resp.json()
        except Exception:
            preview = raw_text[:200].replace("\n", " ")
            return f"搜索失败：B站返回非JSON数据（{preview}...）"

        if data.get("code") != 0:
            err_msg = data.get("message", "未知错误")
            return f"搜索失败：B站API错误 (code={data.get('code')}) - {err_msg}"

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
            if pubdate_ts:
                pubdate_str = _dt.datetime.fromtimestamp(pubdate_ts).strftime("%Y-%m-%d")
            else:
                pubdate_str = "未知"
            parts.append(
                f"[{i}] {title}\n"
                f"    📅 发布:{pubdate_str} | ▶️ 播放:{play}\n"
                f"    {desc}\n"
                f"    https://www.bilibili.com/video/{bvid}"
            )
        sort_label = "最新发布" if fresh else "综合排序"
        return f"（来源：哔哩哔哩 · {sort_label}）\n\n" + "\n\n".join(parts)
    except requests.Timeout:
        return f"搜索「{query}」超时，请稍后重试"
    except requests.RequestException as e:
        return f"搜索失败：网络错误 - {e}"
    except Exception as e:
        return f"搜索失败：{e}"

# Tool 4: python_repl (安全沙箱，精简自 Day 17)
import statistics as _statistics, random as _random, re as _re, json as _json
import collections as _collections, itertools as _itertools
import fractions as _fractions, decimal as _decimal, functools as _functools

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

# ── 工具注册表 ──
ALL_TOOLS = {
    "calculator": {
        "schema": {
            "type": "function",
            "function": {
                "name": "calculator",
                "description": "计算数学表达式。用于精确数学计算。支持 +-*/、sqrt、sin/cos、log、pi 等。",
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
                "description": "获取当前日期、时间或星期几。用于需要知道「现在是什么时间」的问题。",
                "parameters": {
                    "type": "object",
                    "properties": {"format_type": {"type": "string", "enum": ["datetime", "date", "time", "weekday"]}},
                    "required": ["format_type"]
                }
            }
        },
        "func": lambda format_type="datetime": get_current_time(format_type),
    },
    "web_search": {
        "schema": {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": (
                    "搜索B站视频获取实时信息。每条结果包含【发布时间】，"
                    "请务必检查发布日期判断信息是否过时。"
                    "时效性问题（如'最新''现在''当前''今年'）必须设 fresh=true 按最新排序。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索关键词，5-15个字为佳"},
                        "max_results": {"type": "integer", "description": "返回条数，默认5"},
                        "sort": {
                            "type": "string",
                            "enum": ["relevance", "newest"],
                            "description": (
                                "排序方式：relevance=综合排序, newest=最新发布。"
                                "问'最新/现在/当前/最近/今年'等时效性问题时必须设为newest！"
                            )
                        }
                    },
                    "required": ["query"]
                }
            }
        },
        "func": lambda query, max_results=5, sort="relevance": web_search(query, max_results, sort == "newest"),
    },
    "python_repl": {
        "schema": {
            "type": "function",
            "function": {
                "name": "python_repl",
                "description": (
                    "执行 Python 代码并返回输出。用于数据处理、统计分析、批量计算等。"
                    "已预装：math, json, datetime, random, statistics, collections, "
                    "itertools, re, fractions, decimal, functools。"
                    "使用 print() 输出结果。不可读写文件或网络请求。"
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

print(f"  已注册 {len(ALL_TOOLS)} 个工具：")
for name, t in ALL_TOOLS.items():
    desc = t['schema']['function']['description'][:60]
    print(f"    🔧 {name}: {desc}...")
print()

# ── Agent 循环 ──
def run_agent(user_query: str, system_prompt: str = None,
              max_iterations: int = 6, verbose: bool = True,
              tools_enabled: list[str] = None) -> dict:
    """运行 Agent 循环（Day 15-17 打磨出的版本）"""
    if tools_enabled is None:
        tool_schemas = ALL_TOOL_SCHEMAS
        tool_names_str = "全部"
    else:
        tool_schemas = [ALL_TOOLS[n]["schema"] for n in tools_enabled if n in ALL_TOOLS]
        tool_names_str = ", ".join(tools_enabled)

    if system_prompt is None:
        system_prompt = (
            f"当前日期：{CURRENT_DATE} {CURRENT_WEEKDAY}\n"
            f"你是一个具备多种工具的智能助手。可用工具：{tool_names_str}。\n\n"
            f"核心原则：\n"
            f"1. 需要精确计算 → calculator\n"
            f"2. 需要实时信息 → web_search\n"
            f"3. 需要数据处理/统计分析/批量运算 → python_repl\n"
            f"4. 需要日期时间 → get_current_time\n"
            f"5. 复杂任务可以组合多个工具，按合理顺序调用\n"
            f"6. 简单常识问题直接回答，不要调用工具\n"
            f"7. 搜索结果中的数据，用 python_repl 来统计和分析\n"
            f"8. ⚠️ 时效性关键原则（重要！）：\n"
            f"   - 问「最新/现在/当前/今年/第几赛季」→ web_search 必须 sort='newest'\n"
            f"   - 每条结果都有 📅 发布时间，优先采信最近发布的视频\n"
            f"   - 旧视频（发布时间超过3个月）的信息可能已过时，谨慎引用\n"
            f"   - 如果新旧视频信息矛盾，以最新的为准"
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
                    if name == "python_repl":
                        preview = result[:80].replace("\n", " | ")
                    elif name == "web_search":
                        preview = result[:80].replace("\n", " ")
                    else:
                        preview = result[:80]
                    print(f"    📊 {name} → {preview}{'...' if len(result) > 80 else ''}")

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

# ── 1.2 意图识别测试 ──
print("─" * 50)
print("1.2 意图识别测试：同一个 Agent，不同问题，看它选什么工具")
print()

test_queries = [
    ("纯计算", "12345 × 67890 等于多少？"),
    ("实时信息", "2026年7月有什么重要的科技新闻？"),
    ("数据处理", "计算 [23, 45, 67, 89, 12, 34, 56, 78] 的平均值、方差和中位数"),
    ("常识问答", "什么是机器学习？用一句话解释。"),
]

for label, query in test_queries:
    print(f"\n  🏷️  [{label}] {query}")
    result = run_agent(query, verbose=False)
    tools_used = [tc["tool"] for tc in result["tool_calls"]]
    print(f"      📞 工具调用链：{' → '.join(tools_used) if tools_used else '(无需工具)'}")
    print(f"      📝 回答预览：{result['answer'][:100].replace(chr(10), ' ')}...")
    print(f"      📊 {result['iterations']} 轮 · {len(result['tool_calls'])} 次调用")

print()
print("  🔑 观察：Agent 根据问题类型自动选择合适的工具。")
print("     你不需要写 if-else 判断——模型自己会判断。")
print("     这就是 Function Calling 的「意图识别」能力。")

input("\n按 Enter 进入实验 2：复杂多步任务编排...")

# ============================================================
# 实验 2：复杂多步任务编排 —— 搜索 → Python → 分析
# ============================================================
print("\n" + "=" * 65)
print("实验 2：复杂多步任务 —— Agent 自主编排工具链")
print("=" * 65)
print()
print("""
  这才是 Agent 真正强大的地方——
  不是「能调用工具」，而是「能自主编排多个工具的调用顺序」。

  类比：一个好的项目经理，不是自己干活，而是知道：
    - 什么时候该调研（web_search）
    - 什么时候该计算（calculator / python_repl）
    - 什么时候该整理输出（python_repl）
    - 什么时候该确认时间（get_current_time）

  下面我们给 Agent 一个需要至少 3 步的复杂任务。
""")

# ── 场景 A：搜索 + Python 处理 ──
print("╔" + "═" * 55 + "╗")
print("║  场景 A：搜索数据 → Python 处理 → 得出结论")
print("╚" + "═" * 55 + "╝")

task_a = (
    "请研究2026年最值得学习的3种编程语言。\n"
    "步骤：\n"
    "1. 搜索2026年编程语言趋势和排名\n"
    "2. 提取关键信息（语言名称、学习难度、就业前景、平均薪资）\n"
    "3. 用Python将信息整理成结构化数据，计算综合评分\n"
    "4. 给出最终推荐排名和理由"
)

print(f"\n  📋 任务：{task_a[:100]}...")
print()

result_a = run_agent(task_a, max_iterations=8)

print(f"\n  {'─' * 50}")
print(f"  📝 Agent 最终回答：")
print(f"  {'─' * 50}")
print(f"  {result_a['answer'][:500]}")

print(f"\n  📊 工具调用链（共 {len(result_a['tool_calls'])} 次）：")
for i, tc in enumerate(result_a["tool_calls"], 1):
    if tc['tool'] == 'python_repl':
        code_preview = tc['args'].get('code', '')[:60].replace('\n', ' | ')
        print(f"    {i}. R{tc['round']} {tc['tool']}: {code_preview}...")
    elif tc['tool'] == 'web_search':
        print(f"    {i}. R{tc['round']} {tc['tool']}: \"{tc['args'].get('query', '')}\"")
    else:
        print(f"    {i}. R{tc['round']} {tc['tool']}({json.dumps(tc['args'], ensure_ascii=False)})")

print()
print("  🔑 关键观察：")
print("    Agent 自主决定了「先搜什么→搜几次→何时用Python→何时结束」")
print("    这整个流程没有一行 if-else 代码——完全是模型自己推理出来的。")

# ── 场景 B：更复杂的混合任务 ──
print("\n\n╔" + "═" * 55 + "╗")
print("║  场景 B：时间 + 计算 + 搜索 三重组合")
print("╚" + "═" * 55 + "╝")

task_b = (
    f"假设我从今天（{CURRENT_DATE}）开始，每月定投5000元到一只年化收益率8%的指数基金。\n"
    "请帮我：\n"
    "1. 用Python计算10年、20年、30年后分别能积累多少资金（复利计算）\n"
    "2. 搜索一下市场上主流指数基金的实际历史年化收益率，验证8%是否合理\n"
    "3. 如果实际收益率只有6%，最终金额会差多少？\n"
    "4. 给出投资建议"
)

print(f"\n  📋 任务涉及 3 种工具：python_repl（计算）+ web_search（验证）+ calculator（对比）")
print()

result_b = run_agent(task_b, max_iterations=8)

print(f"\n  {'─' * 50}")
print(f"  📝 Agent 最终回答：")
print(f"  {'─' * 50}")
print(f"  {result_b['answer'][:500]}")

print(f"\n  📊 工具调用链：")
for i, tc in enumerate(result_b["tool_calls"], 1):
    if tc['tool'] == 'python_repl':
        code = tc['args'].get('code', '')[:80].replace('\n', ' | ')
        print(f"    {i}. R{tc['round']} 🐍 {code}...")
    elif tc['tool'] == 'web_search':
        print(f"    {i}. R{tc['round']} 🔍 \"{tc['args'].get('query', '')}\"")
    elif tc['tool'] == 'calculator':
        print(f"    {i}. R{tc['round']} 🔢 {tc['args'].get('expression', '')}")
    else:
        print(f"    {i}. R{tc['round']} {tc['tool']}")

# ── 工具使用统计 ──
tool_counts = {}
for tc in result_b["tool_calls"]:
    tool_counts[tc["tool"]] = tool_counts.get(tc["tool"], 0) + 1
print(f"\n  📈 工具使用分布：{tool_counts}")
print(f"  📊 总轮数：{result_b['iterations']} · 总调用：{len(result_b['tool_calls'])}")

input("\n按 Enter 进入实验 3：Plan-then-Execute 模式...")

# ============================================================
# 实验 3：Plan-then-Execute 模式 —— 先规划再执行
# ============================================================
print("\n" + "=" * 65)
print("实验 3：Plan-then-Execute —— 让 Agent 先做计划再行动")
print("=" * 65)
print()
print("""
  前面实验中，Agent 是「边走边看」——
  调一个工具 → 看结果 → 决定下一步。

  但对于复杂任务，更好的模式是 Plan-then-Execute：
  1. Plan（规划）：先列出要做什么、用什么工具、什么顺序
  2. Execute（执行）：按计划一步步调工具
  3. Verify（验证）：检查结果是否完整

  这在面试中是加分项——面试官想知道你是否理解
  「ReAct vs Plan-then-Execute」的区别。
""")

# ── Plan-then-Execute 的 system prompt ──
PLAN_SYSTEM_PROMPT = (
    f"当前日期：{CURRENT_DATE} {CURRENT_WEEKDAY}\n"
    f"你是一个会「先规划再执行」的智能助手。\n\n"
    f"## 可用工具\n"
    f"- calculator: 计算数学表达式\n"
    f"- get_current_time: 获取当前日期时间\n"
    f"- web_search: 搜索互联网获取实时信息\n"
    f"- python_repl: 执行Python代码处理数据\n\n"
    f"## 工作流程（重要！）\n"
    f"对于复杂任务，你必须先输出一段【执行计划】，然后再按计划调用工具。\n"
    f"计划格式：\n"
    f"  📋 执行计划：\n"
    f"  Step 1: [做什么] → [用什么工具]\n"
    f"  Step 2: [做什么] → [用什么工具]\n"
    f"  ...\n"
    f"然后按照计划逐步执行。\n\n"
    f"## 规则\n"
    f"1. 简单问题不需要计划，直接回答\n"
    f"2. 复杂任务（需要2个以上工具）必须先写计划\n"
    f"3. 执行过程中如果发现计划不够好，可以调整\n"
    f"4. 完成后对照计划检查是否有遗漏"
)

print("─" * 50)
print("Plan-then-Execute vs 传统 ReAct 对比")
print()

# 测试任务
plan_task = (
    "帮我做一个完整的分析：比较 Python、JavaScript、Go 三种语言在2026年的\n"
    "1) 流行程度排名\n"
    "2) 平均薪资水平\n"
    "3) 主要应用领域\n"
    "然后用 Python 做一个综合评分（流行度30% + 薪资40% + 应用广度30%），\n"
    "输出最终排名。"
)

print(f"  📋 任务（需要多步搜索 + Python 处理）：")
print(f"     {plan_task[:80]}...")
print()

# 对比：不用 Plan 的版本
print("━" * 40)
print("场景 A：不用 Plan-then-Execute（传统方式）")
print("━" * 40)

result_no_plan = run_agent(plan_task, max_iterations=8)

print(f"\n  📊 工具调用链：")
for i, tc in enumerate(result_no_plan["tool_calls"], 1):
    print(f"    {i}. R{tc['round']} {tc['tool']}")

print(f"\n  📝 回答长度：{len(result_no_plan['answer'])} 字符")
print(f"  📊 {result_no_plan['iterations']} 轮 · {len(result_no_plan['tool_calls'])} 次调用")

# 使用 Plan-then-Execute
print("\n━" * 40)
print("场景 B：使用 Plan-then-Execute（先规划再执行）")
print("━" * 40)

result_with_plan = run_agent(plan_task, system_prompt=PLAN_SYSTEM_PROMPT, max_iterations=10)

print(f"\n  📊 工具调用链：")
for i, tc in enumerate(result_with_plan["tool_calls"], 1):
    print(f"    {i}. R{tc['round']} {tc['tool']}")

print(f"\n  📝 回答长度：{len(result_with_plan['answer'])} 字符")
print(f"  📊 {result_with_plan['iterations']} 轮 · {len(result_with_plan['tool_calls'])} 次调用")

print()
print("  🔑 对比分析：")
print("    Plan-then-Execute 的优势：")
print("      ✅ 更系统——不会被中间结果带偏")
print("      ✅ 更完整——对照计划不容易遗漏步骤")
print("      ✅ 更可解释——用户能看到「Agent在想什么」")
print("    传统 ReAct 的优势：")
print("      ✅ 更灵活——每步根据实际结果调整")
print("      ✅ 更快——简单任务不需要额外的规划步骤")
print()
print("  💡 面试要点：两种模式不互斥——高级 Agent 是「Plan-then-Execute + ReAct 调整」")

input("\n按 Enter 进入实验 4：Self-Reflection 自我审查...")

# ============================================================
# 实验 4：Self-Reflection —— Agent 审查自己的答案
# ============================================================
print("\n" + "=" * 65)
print("实验 4：Self-Reflection —— Agent 审查并改进自己的答案")
print("=" * 65)
print()
print("""
  前面实验的 Agent 是「一次性」的——给出答案就结束了。

  但真正的智能体应该能自我反思：
    1. 给出初步答案
    2. 审查这个答案是否完整、准确
    3. 如果不够好 → 搜索更多信息或重新计算
    4. 迭代直到满意

  这就是 Reflection Pattern，LangChain/LLamaIndex 里叫「Self-Reflection」。
""")

# ── 实现 Reflection Agent ──
def run_reflection_agent(user_query: str, max_rounds: int = 3,
                         max_iterations_per_round: int = 5,
                         verbose: bool = True) -> dict:
    """
    Self-Reflection Agent：
    1. Round 1: 正常 Agent 循环 → 得到初步答案
    2. Reflection: 让 LLM 审查这个答案
    3. Round 2: 如果不够好，带着审查意见再搜/再算
    4. 重复直到满意或达到上限
    """
    all_tool_calls = []
    total_iterations = 0
    current_answer = ""
    reflection_notes = ""

    for reflection_round in range(1, max_rounds + 1):
        if verbose:
            if reflection_round == 1:
                print(f"\n  ── Reflection Round {reflection_round}：初始回答 ──")
            else:
                print(f"\n  ── Reflection Round {reflection_round}：改进回答 ──")

        # 构建任务
        if reflection_round == 1:
            task = user_query
        else:
            task = (
                f"原始问题：{user_query}\n\n"
                f"你上一轮的答案：\n{current_answer}\n\n"
                f"审查意见（你必须改进的方面）：\n{reflection_notes}\n\n"
                f"请根据审查意见，搜索更多信息或重新计算，给出改进后的完整答案。"
                f"特别注意审查意见中指出的不足之处。"
            )

        result = run_agent(
            task,
            max_iterations=max_iterations_per_round,
            verbose=verbose,
        )
        current_answer = result["answer"]
        all_tool_calls.extend(result["tool_calls"])
        total_iterations += result["iterations"]

        # 最后一轮不再反思
        if reflection_round == max_rounds:
            if verbose:
                print(f"\n  ⏹️  达到最大反思轮数，输出最终答案")
            break

        # Reflection 阶段：让 LLM 审查答案
        if verbose:
            print(f"\n  🔍 Reflection：审查答案质量...")

        reflection_prompt = (
            f"用户问题：{user_query}\n\n"
            f"当前答案：\n{current_answer}\n\n"
            f"请严格审查这个答案：\n"
            f"1. 是否完整回答了问题的所有部分？\n"
            f"2. 数据是否具体、有来源？\n"
            f"3. 有没有需要补充或修正的地方？\n"
            f"4. 逻辑是否清晰？\n\n"
            f"如果答案已经很好，回复「SATISFIED」。\n"
            f"如果有改进空间，回复「NEEDS_IMPROVEMENT: <具体需要改进的地方>」"
        )

        reflection_response = llm_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "你是一个严格的答案审查员。只关注事实准确性、完整性和逻辑性。"},
                {"role": "user", "content": reflection_prompt},
            ],
            temperature=0.0,
        )

        reflection_notes = reflection_response.choices[0].message.content or "SATISFIED"

        if verbose:
            preview = reflection_notes[:150].replace("\n", " ")
            print(f"    审查结果：{preview}...")

        if reflection_notes.strip().upper().startswith("SATISFIED"):
            if verbose:
                print(f"  ✅ Agent 对自己的答案满意，停止反思")
            break

    return {
        "answer": current_answer,
        "iterations": total_iterations,
        "reflection_rounds": reflection_round,
        "tool_calls": all_tool_calls,
        "final_reflection": reflection_notes,
    }

# ── 测试 Reflection Agent ──
print("─" * 50)
print("测试 Self-Reflection Agent")
print()

reflection_task = (
    "分析一下2026年人工智能行业就业市场：\n"
    "1. 最热门的3个AI岗位是什么？\n"
    "2. 各自需要什么技能？\n"
    "3. 平均薪资范围是多少？\n"
    "请尽量提供具体数据。"
)

print(f"  📋 任务：{reflection_task[:80]}...")
print(f"  📊 最多反思 2 轮")
print()

result_reflection = run_reflection_agent(reflection_task, max_rounds=2, max_iterations_per_round=5)

print(f"\n  {'─' * 50}")
print(f"  📝 最终答案：")
print(f"  {'─' * 50}")
print(f"  {result_reflection['answer'][:500]}")

print(f"\n  📊 Self-Reflection 统计：")
print(f"    反思轮数：{result_reflection['reflection_rounds']}")
print(f"    总迭代：{result_reflection['iterations']} 轮")
print(f"    总工具调用：{len(result_reflection['tool_calls'])} 次")

print()
print("  🔑 Self-Reflection 的价值：")
print("    ✅ 提高答案质量——Agent 不会满足于第一个不完美的答案")
print("    ✅ 减少幻觉——审查阶段会检查数据是否合理")
print("    ✅ 补充遗漏——如果第一轮漏了某部分，第二轮会补上")
print("    ⚠️  代价：需要更多 API 调用（时间 + 费用）")
print()
print("  💡 面试：这叫「Reflection Pattern」，ReAct 的进阶版本。")

# ============================================================
# Day 18 总结
# ============================================================
print("\n" + "=" * 65)
print("Day 18 总结：你今天学到了什么")
print("=" * 65)
print("""
┌────────────────────────────────────────────────────────────────┐
│  1. 多工具意图识别                                               │
│     Agent 面对 4 个工具，能正确判断「什么时候用哪个」             │
│     这不是 if-else 规则，是模型理解工具描述后做的语义判断        │
│                                                                │
│  2. 复杂工具链编排                                               │
│     web_search → python_repl → calculator → 最终答案            │
│     Agent 自主决定调用顺序、调用次数、何时该停                    │
│     这是 Agent 区别于「单个 API 调用」的核心能力                 │
│                                                                │
│  3. Plan-then-Execute 模式                                       │
│     复杂任务先写计划再执行，比「走一步看一步」更可靠              │
│     面试常考：ReAct vs Plan-Execute 的区别和适用场景             │
│     - ReAct: 灵活，适合探索性任务                                │
│     - Plan-Execute: 系统，适合步骤明确的复杂任务                 │
│                                                                │
│  4. Self-Reflection 模式                                         │
│     Agent 审查自己的答案 → 发现不足 → 补充搜索/计算 → 改进       │
│     这是让 Agent 「靠谱」的关键——不会满足于第一个不完美的答案     │
│     代价：更多 API 调用，但质量和可靠性显著提升                   │
│                                                                │
│  5. Agent 的「智能」从哪来？                                      │
│     不是工具多 → 是编排能力                                      │
│     不是模型强 → 是循环 + 反思                                    │
│     不是替代人 → 是 augment（增强）人的能力                       │
└────────────────────────────────────────────────────────────────┘
""")

print("""
🔜 Day 19 预告：Streamlit Agent 可视化
  - 把 Agent 的每一步「思考→调用→结果」变成可视化界面
  - 实时看到 Agent 的工具调用链
  - 对比不同策略的效果
  - 最终成果：一个可演示的 Agent Dashboard

📊 三周学习路线回顾：
  Week 1 (Day 1-5):  学会调 API —— 从 Hello World 到流式输出
  Week 2 (Day 8-13): 搭建 RAG —— 从文档加载到检索增强生成
  Week 3 (Day 15-19): Agent —— 从 Function Calling 到自主编排
""")

print(f"\nDay 18 完成 ✅ | 模型：{LLM_MODEL} | 工具：{len(ALL_TOOLS)} 个 | 实验：4 个")
print(f"\n当前 Agent 工具箱：{', '.join(ALL_TOOLS.keys())}")
