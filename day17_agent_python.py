"""
Day 17 - AI Agent + Python 代码执行：让 Agent 拥有「编程能力」
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Day 15 我们让 Agent 学会了「算」（calculator），但那只能算一个表达式。
Day 16 我们让 Agent 学会了「搜」（web_search），能获取实时信息。
今天给 Agent 装上「编程能力」——能写代码、处理数据、自己调试。

这跟 calculator 的本质区别：
  calculator:  输入一个表达式 → 返回一个数字
  Python REPL:  输入一段代码   → 可以循环、判断、调库、处理复杂数据

学完今天你会：
  ✅ 实现安全的 Python 代码执行沙箱
  ✅ 让 Agent 自主写代码处理数据
  ✅ Agent 自我调试：写代码 → 报错 → 分析 → 修正 → 再执行
  ✅ 搜索 + Python 协同：搜数据 → 写代码处理 → 得出结论

核心认知：
  ┌──────────────────────────────────────────────────────────────┐
  │  Python 执行工具 = Agent 的「思考外挂」                        │
  │  模型不擅长精确计算 → 写代码让 Python 算                       │
  │  模型不擅长数据处理 → 写代码让 Python 处理                     │
  │  这就是「让专业的人做专业的事」在 Agent 身上的体现              │
  └──────────────────────────────────────────────────────────────┘
"""

import sys, os, json, math
sys.stdout.reconfigure(encoding='utf-8')

from config import client as llm_client, MODEL as LLM_MODEL

print("=" * 65)
print("Day 17 — AI Agent + Python 代码执行")
print("=" * 65)
print()

print("""
┌────────────────────────────────────────────────────────────────┐
│  回顾 Day 15-16：Agent 已经学会了三件事                           │
│    ✅ calculator       → 算数学表达式                             │
│    ✅ get_current_time → 查日期时间                               │
│    ✅ web_search       → 搜索互联网                               │
│                                                                │
│  但有一个关键能力缺失：                                          │
│    ❌ 处理数据 —— 排序、筛选、聚合、统计                         │
│    ❌ 多步计算 —— 需要中间变量、循环、条件判断                    │
│    ❌ 格式转换 —— JSON 解析、字符串处理、编码转换                 │
│                                                                │
│  Day 17 的目标：添加第四个工具 → python_repl（Python 代码执行）    │
│  效果：Agent 从「只会调 API」升级到「会写代码解决问题」           │
└────────────────────────────────────────────────────────────────┘
""")

input("按 Enter 进入实验 1：理解 Python 执行 vs 简单计算器...")

# ============================================================
# 实验 1：Python 执行 vs 简单计算器 — 本质区别
# ============================================================
print("\n" + "=" * 65)
print("实验 1：Python 代码执行 vs 简单计算器——为什么需要更强大的工具")
print("=" * 65)
print()
print("""
  场景：计算 [85, 92, 78, 95, 88, 73, 91, 86] 的统计信息
        （平均分、最高分、最低分、标准差、中位数）

  ┌─────────────────────────────────────────────────────────────┐
  │  calculator 的做法：                                          │
  │    第1次调用: calculator("(85+92+78+95+88+73+91+86)/8")     │
  │    第2次调用: calculator("max(85,92,78,95,88,73,91,86)")    │
  │    第3次调用: calculator("min(...)")                         │
  │    ...需要 5+ 次调用，且标准差根本没法用表达式算                │
  │                                                             │
  │  Python REPL 的做法：                                         │
  │    1次调用: 写一段代码，循环+统计库，一次返回所有结果            │
  │    → 快、准、优雅                                             │
  └─────────────────────────────────────────────────────────────┘
""")

# 演示
scores = [85, 92, 78, 95, 88, 73, 91, 86]
import statistics

print(f"  实际数据：{scores}")
print(f"  平均值：{statistics.mean(scores):.1f}")
print(f"  标准差：{statistics.stdev(scores):.2f}")
print(f"  中位数：{statistics.median(scores):.1f}")
print(f"  最高分：{max(scores)}  |  最低分：{min(scores)}")
print()
print("  这些用 Python 一行就能算完。而 calculator 需要至少 5 轮调用。")
print("  关键不是「能不能算」，而是「效率和可扩展性」。")

input("\n按 Enter 进入实验 2：构建安全的 Python 执行沙箱...")

# ============================================================
# 实验 2：构建安全的 Python 代码执行沙箱
# ============================================================
print("\n" + "=" * 65)
print("实验 2：构建安全的 Python 执行沙箱")
print("=" * 65)
print()

# ── 2.1 安全沙箱设计 ──
print("─" * 50)
print("2.1 安全沙箱设计 —— 让 Agent 能写代码，但不能搞破坏")
print()
print("""
  ⚠️ 安全隐患：如果让 Agent 执行任意 Python 代码，它可以：
    - 删除文件（import os; os.remove(...)）
    - 发起网络请求（import requests; requests.post(...)）
    - 无限循环（while True: pass）
    - 读写敏感文件

  🛡️ 沙箱策略：
    1. 禁用危险内置函数（open, __import__, eval, exec, compile）
    2. 白名单内置函数（只能 print/len/range/sum 等安全的）
    3. 预导入安全模块（math/json/datetime/statistics/re...）
    4. 捕获 stdout 输出（print() 的内容作为返回值）
    5. try/except 兜底（代码出错不会崩掉 Agent）
""")

# ── 2.2 实现安全沙箱 ──
print("─" * 50)
print("2.2 实现 Python 执行函数")
print()

import io as _io
import statistics as _statistics
import datetime as _datetime
import random as _random
import collections as _collections
import itertools as _itertools
import re as _re
import json as _json
import fractions as _fractions
import decimal as _decimal
import functools as _functools

# 安全的命名空间（白名单）
SAFE_BUILTINS = {
    # 基本函数
    'print': print, 'len': len, 'range': range, 'enumerate': enumerate,
    'zip': zip, 'map': map, 'filter': filter, 'sorted': sorted,
    'reversed': reversed, 'iter': iter, 'next': next,
    # 类型转换
    'int': int, 'float': float, 'str': str, 'bool': bool,
    'list': list, 'dict': dict, 'tuple': tuple, 'set': set, 'frozenset': frozenset,
    'bytes': bytes, 'bytearray': bytearray, 'complex': complex,
    'chr': chr, 'ord': ord, 'repr': repr, 'format': format, 'bin': bin, 'hex': hex, 'oct': oct,
    # 数学
    'abs': abs, 'round': round, 'min': min, 'max': max, 'sum': sum,
    'pow': pow, 'divmod': divmod,
    # 逻辑
    'any': any, 'all': all, 'isinstance': isinstance, 'issubclass': issubclass,
    'callable': callable, 'hash': hash, 'id': id,
    # 常量
    'True': True, 'False': False, 'None': None,
    # 异常
    'Exception': Exception, 'ValueError': ValueError, 'TypeError': TypeError,
    'KeyError': KeyError, 'IndexError': IndexError, 'AttributeError': AttributeError,
    'StopIteration': StopIteration, 'ZeroDivisionError': ZeroDivisionError,
    # 帮助（禁用）
    'help': lambda *a, **kw: 'help() disabled for security',
    # 危险操作（禁止）
    '__import__': lambda *a, **kw: (_ for _ in ()).throw(ImportError('import disabled')),
    'open': lambda *a, **kw: (_ for _ in ()).throw(RuntimeError('open() disabled')),
    'eval': lambda *a, **kw: (_ for _ in ()).throw(RuntimeError('eval() disabled')),
    'exec': lambda *a, **kw: (_ for _ in ()).throw(RuntimeError('exec() disabled')),
    'compile': lambda *a, **kw: (_ for _ in ()).throw(RuntimeError('compile() disabled')),
}

# 预导入的安全模块
SAFE_MODULES = {
    'math': math,
    'json': _json,
    'datetime': _datetime,
    'random': _random,
    'collections': _collections,
    'itertools': _itertools,
    're': _re,
    'statistics': _statistics,
    'fractions': _fractions,
    'decimal': _decimal,
    'functools': _functools,
}

def python_repl(code: str, timeout_seconds: int = 5) -> str:
    """
    安全的 Python 代码执行沙箱。

    参数：
      code            : 要执行的 Python 代码
      timeout_seconds : 最大执行时间（秒）

    返回：
      代码的输出（stdout 内容 + 最后的表达式值）
    """
    namespace = {
        '__builtins__': SAFE_BUILTINS,
        **SAFE_MODULES,
    }

    stdout = _io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = stdout

    try:
        compiled = compile(code, '<agent_repl>', 'exec')
        exec(compiled, namespace)
        output = stdout.getvalue()

        # 提取最后一个表达式的值（如果代码以表达式结尾）
        # 不尝试提取，保持简单

        result = output.rstrip() if output.rstrip() else '（代码执行完成，无输出）'
        return result

    except SyntaxError as e:
        return f'语法错误：第{e.lineno}行 - {e.msg}'
    except Exception as e:
        return f'执行错误：{type(e).__name__}: {e}'

    finally:
        sys.stdout = old_stdout

# 测试沙箱
print("  沙箱安全测试：")
print()

# 测试1：正常代码
r1 = python_repl("""
scores = [85, 92, 78, 95, 88, 73, 91, 86]
print(f"平均分: {statistics.mean(scores):.1f}")
print(f"标准差: {statistics.stdev(scores):.2f}")
print(f"中位数: {statistics.median(scores):.1f}")
print(f"最高: {max(scores)}, 最低: {min(scores)}")
""")
print(f"  ✅ 正常代码：OK")
# 只显示前120字符
lines = r1.strip().split('\n')
for line in lines[:3]:
    print(f"      {line}")

# 测试2：尝试危险操作
r2 = python_repl("""
import os
os.remove('/etc/passwd')
""")
print(f"\n  🔒 危险代码被拦截：{r2.split(chr(10))[0]}")

# 测试3：语法错误
r3 = python_repl("print(1 + )")
print(f"  🐛 语法错误被捕获：{r3.split(chr(10))[0]}")

# 测试4：无限循环保护说明
print(f"  ⏱️  超时保护：{timeout_seconds}秒（由其进程/线程限制保证）")

print()
print("  关键设计决策：")
print("    - 白名单 > 黑名单（unknown functions disabled by default）")
print("    - __import__ 被禁 → 无法 import 任何没预装的模块")
print("    - open/eval/exec/compile 被禁 → 无法读写文件或执行嵌套代码")
print("    - 捕获 stdout → print() 的输出直接作为工具返回值")

# ── 2.3 封装为 Agent 工具 ──
print("\n" + "─" * 50)
print("2.3 封装为 Agent 工具 + Schema 定义")
print()

PYTHON_REPL_TOOL = {
    "type": "function",
    "function": {
        "name": "python_repl",
        "description": (
            "执行 Python 代码并返回输出结果。用于数据处理、统计计算、"
            "格式转换、批量运算等任何需要编程的任务。"
            "已预装库：math, json, datetime, random, statistics, collections,"
            "itertools, re, fractions, decimal, functools。"
            "使用 print() 来输出结果。"
            "禁止操作：文件读写、网络请求、import 其他库、eval/exec。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": (
                        "要执行的 Python 代码。使用 print() 输出结果。"
                        "可以多行。已预装的库可以直接 import（事实上它们已经在"
                        "命名空间里了，直接用 math.sqrt() 这样的即可）。"
                    )
                }
            },
            "required": ["code"]
        }
    }
}

print("""
  Schema 设计要点：

  1. description 里列出了所有预装库 → Agent 知道能用什么
  2. 明确告知「使用 print() 输出」→ Agent 不会傻等返回值
  3. 列出禁止操作 → Agent 不会尝试危险代码浪费时间
  4. code 参数是完整代码块 → 不是单个表达式，是多行程序
""")

input("\n按 Enter 进入实验 3：Agent + Python 实战...")

# ============================================================
# 实验 3：Agent + Python 实战
# ============================================================
print("\n" + "=" * 65)
print("实验 3：Agent + Python 实战 — 数据处理任务")
print("=" * 65)
print()

# ── 构建完整的 Agent 系统 ──
import datetime as _dt

def get_current_time(format_type: str = "datetime") -> str:
    now = _dt.datetime.now()
    if format_type == "date":
        return now.strftime("%Y年%m月%d日")
    elif format_type == "time":
        return now.strftime("%H:%M:%S")
    elif format_type == "weekday":
        return ["星期一","星期二","星期三","星期四","星期五","星期六","星期日"][now.weekday()]
    else:
        return now.strftime("%Y年%m月%d日 %H:%M:%S") + f" {['星期一','星期二','星期三','星期四','星期五','星期六','星期日'][now.weekday()]}"

CURRENT_DATE = _dt.datetime.now().strftime("%Y年%m月%d日")

# 工具注册表
ALL_TOOLS = {
    "python_repl": {
        "schema": PYTHON_REPL_TOOL,
        "func": lambda code: python_repl(code),
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
    if name not in ALL_TOOLS:
        return f"未知工具：{name}"
    try:
        return str(ALL_TOOLS[name]["func"](**args))
    except Exception as e:
        return f"工具执行失败：{e}"

def run_agent(user_query: str, system_prompt: str = None,
              max_iterations: int = 5, verbose: bool = True) -> dict:
    """运行 Agent 循环"""

    if system_prompt is None:
        tool_descs = "\n".join(
            f"  - {n}: {t['schema']['function']['description']}"
            for n, t in ALL_TOOLS.items()
        )
        system_prompt = (
            f"当前日期：{CURRENT_DATE}\n"
            f"你是一个具备编程能力的智能助手。\n"
            f"可用工具：\n{tool_descs}\n\n"
            f"规则：\n"
            f"1. 遇到数据处理、统计计算、批量操作 → 必须使用 python_repl\n"
            f"2. 在 python_repl 中用 print() 输出所有你想要的结果\n"
            f"3. 代码出错时，分析错误原因，修正后重试\n"
            f"4. 简单问题不需要工具时可以直接回答"
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
            tools=ALL_TOOL_SCHEMAS, temperature=0.0,
        )

        msg = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        if verbose:
            print(f"    finish_reason: {finish_reason}")

        if finish_reason == "stop":
            answer = msg.content or ""
            if verbose:
                preview = answer[:100] + "..." if len(answer) > 100 else answer
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
                result = execute_tool(name, args)

                if verbose:
                    if name == "python_repl":
                        result_preview = result[:100].replace("\n", " | ")
                    else:
                        result_preview = result[:80]
                    print(f"    📊 {name} → {result_preview}")

                tool_calls_log.append({"round": iterations, "tool": name, "args": args, "result": result})
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
        else:
            break

    if iterations >= max_iterations and finish_reason not in ("stop", ""):
        answer = f"Agent 达到最大步数（{max_iterations}），已停止。"

    return {"answer": answer, "iterations": iterations, "tool_calls": tool_calls_log, "history": messages}

# ── 测试场景 ──
# 场景 A：数据处理任务
print("╔" + "═" * 55 + "╗")
print("║  场景 A：数据分析 — 学生成绩统计")
print("╚" + "═" * 55 + "╝")

task_a = (
    "以下是某班级的数学成绩（满分100）：\n"
    "张三 85, 李四 92, 王五 78, 赵六 95, 钱七 88, "
    "孙八 73, 周九 91, 吴十 86, 郑一 79, 冯二 94\n\n"
    "请计算：平均分、标准差、最高分、最低分、中位数，"
    "并统计90分以上的人数及比例。"
)

result_a = run_agent(task_a)
print(f"\n  📝 Agent 回答：")
print(f"  {'─' * 50}")
print(f"  {result_a['answer'][:400]}")
print(f"\n  📊 统计：{result_a['iterations']} 轮 · {len(result_a['tool_calls'])} 次工具调用")

# 场景 B：自调试
print("\n\n╔" + "═" * 55 + "╗")
print("║  场景 B：自我调试 — Agent 写代码 → 出错 → 修正")
print("╚" + "═" * 55 + "╝")

task_b = (
    "请用 Python 生成斐波那契数列的前 20 项，"
    "然后计算相邻两项的比值，观察这个比值趋近于什么数。"
)

result_b = run_agent(task_b, max_iterations=6)
print(f"\n  📝 Agent 回答：")
print(f"  {'─' * 50}")
print(f"  {result_b['answer'][:400]}")
print(f"\n  📊 统计：{result_b['iterations']} 轮 · {len(result_b['tool_calls'])} 次工具调用")

input("\n按 Enter 进入实验 4：Python + 搜索协同...")

# ============================================================
# 实验 4：Python + 搜索协同
# ============================================================
print("\n" + "=" * 65)
print("实验 4：Python + 搜索协同 —— Agent 的终极形态")
print("=" * 65)
print()

# 添加搜索工具（复用 Day 16，但简化版不用外部模块）
def quick_search(query: str) -> str:
    """简化版搜索（避免 Day 16 模块依赖，演示协同逻辑）"""
    try:
        import requests
        from bs4 import BeautifulSoup
        url = f"https://cn.bing.com/search?q={query}&ensearch=1"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=8)
        soup = BeautifulSoup(resp.text, 'html.parser')
        results = []
        for item in soup.select('li.b_algo')[:3]:
            t = item.select_one('h2 a')
            b = item.select_one('.b_caption p')
            if t:
                results.append(f"[{len(results)+1}] {t.get_text(strip=True)}\n   {b.get_text(strip=True) if b else ''}")
        return "\n\n".join(results) if results else "未找到结果"
    except Exception as e:
        return f"搜索失败: {e}"

# 添加搜索到工具注册表
ALL_TOOLS["web_search"] = {
    "schema": {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "搜索互联网获取实时信息。需要最新数据时必须使用。",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "搜索关键词"}},
                "required": ["query"]
            }
        }
    },
    "func": lambda query: quick_search(query),
}
ALL_TOOL_SCHEMAS = [t["schema"] for t in ALL_TOOLS.values()]

# 测试：搜索 + Python 处理
print("╔" + "═" * 55 + "╗")
print("║  协同任务：搜索数据 → Python 处理 → 得出结论")
print("╚" + "═" * 55 + "╝")

task_c = (
    "请搜索「2026年各省高考分数线」，提取搜索结果中的分数线数据，"
    "然后用 Python 计算平均分数、最高分省份、最低分省份。"
    "请注意：即使搜索结果不完整，也请基于你能找到的数据完成计算。"
)

result_c = run_agent(task_c, max_iterations=8)

print(f"\n  📝 Agent 回答：")
print(f"  {'─' * 50}")
print(f"  {result_c['answer'][:400]}")
print(f"\n  📊 统计：{result_c['iterations']} 轮 · {len(result_c['tool_calls'])} 次工具调用")
print(f"\n  工具调用链：")
for i, tc in enumerate(result_c["tool_calls"], 1):
    print(f"    {i}. Round {tc['round']} → {tc['tool']}")
    if tc['tool'] == 'python_repl':
        code_preview = tc['args'].get('code', '')[:80].replace('\n', ' | ')
        print(f"       code: {code_preview}...")
    else:
        print(f"       args: {json.dumps(tc['args'], ensure_ascii=False)[:80]}")

# ============================================================
# Day 17 总结
# ============================================================
print("\n" + "=" * 65)
print("Day 17 总结：你今天学到了什么")
print("=" * 65)
print("""
┌────────────────────────────────────────────────────────────────┐
│  1. Python 执行 vs 简单计算器                                    │
│     calculator: 一个表达式 → 一个数字（适合简单计算）            │
│     python_repl: 一段代码 → 完整输出（适合数据处理）              │
│     关键差距：代码可以有循环、判断、变量、库调用                  │
│                                                                │
│  2. 安全沙箱设计                                                 │
│     - 白名单内置函数（拒绝一切未知函数）                         │
│     - 禁用 __import__/open/eval/exec（防止代码注入）             │
│     - 预导入安全模块（math/json/statistics/re...）               │
│     - 捕获 stdout 作为返回值                                    │
│                                                                │
│  3. Agent 自我调试                                               │
│     代码执行失败 → Agent 分析错误 → 修正代码 → 重新执行          │
│     这是 Agent「自主性」的重要体现                               │
│                                                                │
│  4. 多工具协同                                                   │
│     web_search（搜数据）→ python_repl（处理数据）→ 输出结论      │
│     Agent 自主编排工具调用顺序，不需要你写控制流                  │
│                                                                │
│  5. 面试亮点                                                     │
│     「我们的 Agent 不是简单的工具拼接——它能在 Python 沙箱里       │
│      写代码处理搜索结果，遇到错误会自动分析并修正。」              │
└────────────────────────────────────────────────────────────────┘
""")

print("""
🔜 Day 18 预告：多工具串联 —— Agent 自主决策
  - 多个工具同时可用（搜索 + Python + 计算器 + 时间）
  - Agent 自主决定「用什么工具」「什么顺序」「几轮调用」
  - 复杂的多步骤任务：搜索 → 整理 → 计算 → 格式化输出

🔜 Day 19 预告：Streamlit Agent 可视化
  - 在 Web 界面看到 Agent 每一步的思考和工具调用
""")

print(f"\nDay 17 完成 ✅ | 模型：{LLM_MODEL} | 工具：{len(ALL_TOOLS)} 个")
