"""
Day 15 - AI Agent 入门：理解 Agent 概念 + Function Calling + 第一个 Tool
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
前两周我们学会了调 API（Week 1）和搭 RAG（Week 2）。
但从「回答问题」到「动手干活」，中间缺了一环——Agent。

Agent = LLM + 工具调用能力 + 自主决策循环。

学完今天你会：
  ✅ 理解 Agent 和普通 LLM 调用的本质区别
  ✅ 掌握 Function Calling 的底层机制
  ✅ 手写 Agent 循环：Plan → Act → Observe → Reflect
  ✅ 实现第一个可用 Agent（计算器 + 时间查询）
  ✅ 封装可复用的 AgentRunner

核心认知：
  ┌──────────────────────────────────────────────────────────────┐
  │  普通 LLM：你问 → 它答                                          │
  │  Agent：   你问 → 它想 → 它选工具 → 执行 → 看结果 → 再想 → 再答     │
  │  区别不是模型变了，是多了「工具」和「循环」                          │
  └──────────────────────────────────────────────────────────────┘

Agent 三步循环（面试必考）：
  ┌──────────┐      ┌──────────┐      ┌──────────┐
  │ Planning │ ───→ │ Tool Use │ ───→ │Reflection│
  │  制定计划  │      │  调用工具  │      │  评估结果  │
  └──────────┘      └──────────┘      └──────────┘
       ↑                                      │
       └──────────── 信息足够就结束 ←──────────┘
"""

import sys, os, json, math
sys.stdout.reconfigure(encoding='utf-8')

from config import client as llm_client, MODEL as LLM_MODEL

# ============================================================
# 概念铺垫：普通 LLM vs Agent
# ============================================================
print("=" * 65)
print("Day 15 — AI Agent 入门：让 AI 动手干活")
print("=" * 65)
print()

print("""
┌────────────────────────────────────────────────────────────────┐
│  先搞清楚一个核心问题：Agent 到底是什么？                          │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  普通 LLM 调用（Week 1-2 一直在做的）：                           │
│    用户："1 + 2 * 3 等于多少？"                                  │
│    LLM： "等于 7"  ← 靠「背诵」回答，不是真的在算                    │
│                                                                │
│  Agent 调用（今天要学的）：                                       │
│    用户："1 + 2 * 3 等于多少？"                                  │
│    Agent: "我需要计算 1 + 2 * 3"                                │
│           → 调用 calculator("1 + 2 * 3")                       │
│           → 得到结果: 7                                         │
│           → "计算结果为 7"  ← 真的在算！                          │
│                                                                │
│  关键差异：                                                      │
│    - 普通 LLM：只有一个动作（生成文本）                            │
│    - Agent：有两个动作（决定用不用工具 + 生成文本）                  │
│    - Agent 的「工具」是真正的代码执行，不会算错                       │
│                                                                │
│  类比理解：                                                      │
│    普通 LLM = 一个博学但只会说话的顾问                             │
│    Agent    = 同一个顾问 + 手里有计算器 + 能查日历 + 能上网搜       │
│                                                                │
└────────────────────────────────────────────────────────────────┘
""")

input("按 Enter 进入实验 1：Function Calling 底层机制...")

# ============================================================
# 实验 1：Function Calling 底层机制
# ============================================================
print("\n" + "=" * 65)
print("实验 1：Function Calling 底层机制 —— 模型如何「选择」调用工具？")
print("=" * 65)
print()
print("Function Calling 是 Agent 的核心机制。它不是「模型真的执行了函数」，而是：")
print("  ① 你告诉模型：有哪些工具可用（名称 + 描述 + 参数 schema）")
print("  ② 模型决定：要不要用工具？用哪个？传什么参数？")
print("  ③ 你执行工具：把结果告诉模型")
print("  ④ 模型基于结果：生成最终答案")
print()

# ── 1.1 定义工具（Tool Schema） ──
print("─" * 50)
print("1.1 定义工具：告诉模型你有哪些「武器」")

# 工具定义 = JSON Schema，这是模型能理解的「函数说明书」
CALCULATOR_TOOL = {
    "type": "function",
    "function": {
        "name": "calculator",
        "description": "计算数学表达式。支持加减乘除、乘方、三角函数。例如：'2 + 3 * 4'、'sqrt(16)'、'sin(pi/2)'",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "要计算的数学表达式，必须是纯数学表达式，不要包含'计算'这类描述词"
                }
            },
            "required": ["expression"]
        }
    }
}

print("""
工具定义（JSON Schema 格式）：
{
    "type": "function",
    "function": {
        "name": "calculator",           ← 工具名称
        "description": "计算数学...",    ← 工具用途（给模型看的）
        "parameters": {                ← 参数定义
            "expression": { ... }      ← 必须告诉模型参数叫什么、什么类型
        }
    }
}

关键点：
  - description 是给模型看的！写清楚它才能正确判断何时调用
  - parameters 用 JSON Schema 格式，模型会按要求输出参数
  - required 字段告诉模型哪些参数必须填
""")

# ── 1.2 看模型如何决定调用工具 ──
print("─" * 50)
print("1.2 第一次调用：模型决定要不要用工具")

# 造一个让模型必须用计算器的问题
test_question = "12345679 × 72 等于多少？"
print(f"\n用户问题：{test_question}")
print("\n（这种大数乘法，模型不怎么出错的，但我们可以看它会不会选择用工具）")

response = llm_client.chat.completions.create(
    model=LLM_MODEL,
    messages=[
        {"role": "system", "content": "你是一个数学助手。遇到计算题请使用 calculator 工具。"},
        {"role": "user", "content": test_question}
    ],
    tools=[CALCULATOR_TOOL],
    temperature=0.0,
)

msg = response.choices[0].message

print(f"\n📊 模型返回分析：")
print(f"  finish_reason: {response.choices[0].finish_reason}")
print(f"  有工具调用吗？ {'是 ✅' if msg.tool_calls else '否 ❌'}")
print(f"  有文本内容吗？ {'是' if msg.content else '否'}")

if msg.tool_calls:
    tc = msg.tool_calls[0]
    print(f"\n  🔧 工具调用详情：")
    print(f"    工具 ID：{tc.id}")
    print(f"    工具名：{tc.function.name}")
    print(f"    参数（原始 JSON）：{tc.function.arguments}")
    print(f"\n  ⚡ 模型不返回文本！它返回的是「函数调用指令」。")
    print(f"     这跟之前的所有实验都不一样——以前模型只返回文本。")
else:
    print("\n  ⚠️ 模型没有调用工具（可能它觉得自己能算对）")

print()
print("关键认知：")
print("  finish_reason = 'tool_calls' → 模型说:「我不回答，我要求调用工具」")
print("  finish_reason = 'stop'       → 模型说:「我直接回答，不用工具」")
print("  这个判断是 Agent 循环的基石。")

input("\n按 Enter 进入实验 2：实现真正的工具执行...")

# ============================================================
# 实验 2：手动 Agent 循环 — Plan → Act → Observe → Reflect
# ============================================================
print("\n" + "=" * 65)
print("实验 2：手动 Agent 循环 —— 让 AI 真正「动手」")
print("=" * 65)
print()

# ── 2.1 实现工具函数 ──
print("─" * 50)
print("2.1 实现真正的工具函数")

# 安全的数学计算器
def calculator(expression: str) -> str:
    """安全地计算数学表达式"""
    # 白名单：只允许安全的数学函数
    allowed_names = {
        "abs": abs, "round": round, "min": min, "max": max,
        "pow": pow, "sqrt": math.sqrt, "sin": math.sin,
        "cos": math.cos, "tan": math.tan, "log": math.log,
        "log10": math.log10, "pi": math.pi, "e": math.e,
        "ceil": math.ceil, "floor": math.floor,
        "radians": math.radians, "degrees": math.degrees,
    }
    try:
        # 编译表达式，只允许安全函数
        code = compile(expression, "<calc>", "eval")
        # 检查是否有未授权的名字
        for name in code.co_names:
            if name not in allowed_names:
                return f"错误：'{name}' 不是允许的数学函数"
        result = eval(code, {"__builtins__": {}}, allowed_names)
        return str(result)
    except Exception as e:
        return f"计算错误：{e}"

# 测试
print(f"  calculator('2 + 3 * 4')  = {calculator('2 + 3 * 4')}")
print(f"  calculator('sqrt(144)')  = {calculator('sqrt(144)')}")
print(f"  calculator('sin(pi/2)')  = {calculator('sin(pi/2)')}")
print(f"  calculator('12345679 * 72') = {calculator('12345679 * 72')}")

# ── 2.2 工具注册表和分发器 ──
print("\n" + "─" * 50)
print("2.2 工具注册表：让 Agent 找到并调用工具")

# 工具注册表：把工具名映射到实际函数
TOOLS = {
    "calculator": {
        "schema": CALCULATOR_TOOL,
        "func": lambda expression: calculator(expression),
    }
}

def execute_tool(tool_name: str, arguments: dict) -> str:
    """
    工具分发器 —— Agent 说「我要调用 calculator」，你就调用 calculator。

    参数：
      tool_name : 工具名（跟 schema 里的 name 一致）
      arguments : 参数 dict（模型返回的是 JSON 字符串，需要先 json.loads）

    返回：
      工具执行结果（字符串）
    """
    if tool_name not in TOOLS:
        return f"错误：未知工具 '{tool_name}'"

    tool = TOOLS[tool_name]
    try:
        result = tool["func"](**arguments)
        return result
    except Exception as e:
        return f"工具执行失败：{e}"

print("""
工具注册表结构：
  TOOLS = {
      "calculator": {
          "schema": {...},    ← 给 LLM 看的定义
          "func": lambda ...  ← 实际执行的函数
      }
  }

工具分发器 execute_tool() 的作用：
  Agent 返回 → {"name": "calculator", "arguments": {"expression": "1+1"}}
                ↓
  execute_tool("calculator", {"expression": "1+1"})
                ↓
  calculator(expression="1+1") → "2"
                ↓
  把 "2" 作为工具结果返回给模型
""")

# ── 2.3 完整的手动 Agent 循环 ──
print("─" * 50)
print("2.3 完整 Agent 循环：一个问题走完 Plan → Act → Observe → Reflect")
print()

# 准备问题
question = "计算 2 的 10 次方，然后除以 256"

print(f"🤔 用户问题：{question}")
print()

# Step 1: 第一次 LLM 调用 —— Planning
print("━" * 40)
print("🔄 Round 1: Planning（规划阶段）")
print("━" * 40)
print("  Agent 收到问题 → 分析 → 决定要不要用工具")

messages = [
    {"role": "system", "content": (
        "你是一个数学助手。对于任何数学计算问题，你必须使用 calculator 工具，不要自己计算。"
        "可以分步计算：先算一部分，把结果记下来，再算下一部分。"
    )},
    {"role": "user", "content": question},
]

response1 = llm_client.chat.completions.create(
    model=LLM_MODEL,
    messages=messages,
    tools=[CALCULATOR_TOOL],
    temperature=0.0,
)

msg1 = response1.choices[0].message
print(f"  finish_reason: {response1.choices[0].finish_reason}")

if msg1.tool_calls:
    print(f"  🧠 模型决定：使用工具！理由是它可以精算")
    for i, tc in enumerate(msg1.tool_calls):
        args = json.loads(tc.function.arguments)
        print(f"  📞 工具调用 #{i+1}：{tc.function.name}({args})")

    # Step 2: 执行工具 —— Tool Use
    print()
    print("━" * 40)
    print("⚡ Tool Use（执行阶段）")
    print("━" * 40)

    # 把模型的工具调用消息添加到对话
    messages.append({
        "role": "assistant",
        "content": msg1.content or "",
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                }
            }
            for tc in msg1.tool_calls
        ]
    })

    # 执行每个工具并添加结果
    for tc in msg1.tool_calls:
        tool_name = tc.function.name
        arguments = json.loads(tc.function.arguments)
        result = execute_tool(tool_name, arguments)
        print(f"  🔧 {tool_name}({json.dumps(arguments, ensure_ascii=False)})")
        print(f"  📊 结果：{result}")

        messages.append({
            "role": "tool",
            "tool_call_id": tc.id,
            "content": result,
        })

    # Step 3: 第二次 LLM 调用 —— Reflection + 可能的新行动
    print()
    print("━" * 40)
    print("🔄 Round 2: Reflection（反思阶段）")
    print("━" * 40)
    print("  Agent 看到工具结果 → 评估是否需要更多操作 → 回答或继续")

    response2 = llm_client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        tools=[CALCULATOR_TOOL],
        temperature=0.0,
    )

    msg2 = response2.choices[0].message
    print(f"  finish_reason: {response2.choices[0].finish_reason}")

    if msg2.tool_calls:
        # 还要继续调工具（多步推理的场景）
        print(f"  🧠 模型还需要继续使用工具！（这就是多步推理）")
        for tc in msg2.tool_calls:
            args = json.loads(tc.function.arguments)
            print(f"  📞 工具调用：{tc.function.name}({args})")
    elif msg2.content:
        print(f"  ✅ 模型给出最终答案：")
        print(f"  📝 {msg2.content[:200]}")
    else:
        print(f"  ⚠️ 模型既没有调用工具也没有返回文本")

print()
print("─" * 50)
print("🔑 Agent 循环的本质：")
print()
print("  while True:")
print("      1. 调 LLM（带上所有历史 + 工具定义）")
print("      2. 如果模型返回 tool_calls → 执行工具 → 把结果加回对话")
print("      3. 如果模型返回 content → 这就是最终答案，结束")
print("      4. 如果循环次数 > 上限 → 强制停止（安全阀）")
print()

input("\n按 Enter 进入实验 3：多工具 Agent + 完整循环...")

# ============================================================
# 实验 3：多工具 Agent — 计算器 + 时间查询
# ============================================================
print("\n" + "=" * 65)
print("实验 3：多工具 Agent —— Agent 自主决定用哪个工具")
print("=" * 65)
print()

# ── 3.1 添加第二个工具 ──
print("─" * 50)
print("3.1 添加时间查询工具")

def get_current_time(format_type: str = "datetime") -> str:
    """
    获取当前时间。

    参数：
      format_type: "datetime" 完整日期时间, "date" 仅日期, "time" 仅时间, "weekday" 星期几
    """
    import datetime
    now = datetime.datetime.now()

    if format_type == "date":
        return now.strftime("%Y年%m月%d日")
    elif format_type == "time":
        return now.strftime("%H:%M:%S")
    elif format_type == "weekday":
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        return weekdays[now.weekday()]
    else:  # datetime
        return now.strftime("%Y年%m月%d日 %H:%M:%S") + f" {['星期一','星期二','星期三','星期四','星期五','星期六','星期日'][now.weekday()]}"

# 测试
print(f"  get_current_time('datetime') = {get_current_time('datetime')}")
print(f"  get_current_time('weekday')  = {get_current_time('weekday')}")

DATETIME_TOOL = {
    "type": "function",
    "function": {
        "name": "get_current_time",
        "description": "获取当前日期、时间或星期几。当用户问'今天几号''现在几点''今天星期几'时使用。",
        "parameters": {
            "type": "object",
            "properties": {
                "format_type": {
                    "type": "string",
                    "enum": ["datetime", "date", "time", "weekday"],
                    "description": "返回格式：datetime=完整日期时间, date=仅日期, time=仅时间, weekday=星期几"
                }
            },
            "required": ["format_type"]
        }
    }
}

# 更新工具注册表
TOOLS["get_current_time"] = {
    "schema": DATETIME_TOOL,
    "func": lambda format_type="datetime": get_current_time(format_type),
}

ALL_TOOL_SCHEMAS = [CALCULATOR_TOOL, DATETIME_TOOL]

print(f"\n  当前工具注册表：{list(TOOLS.keys())}")
print(f"  共 {len(TOOLS)} 个工具：计算器 + 时间查询")

# ── 3.2 封装完整的 Agent 循环 ──
print("\n" + "─" * 50)
print("3.2 完整 Agent 循环 —— 处理多工具、多轮调用")
print()

def run_agent(user_query: str, system_prompt: str = None,
              max_iterations: int = 5, verbose: bool = True) -> dict:
    """
    完整的 Agent 循环实现 —— 这是 Day 15 最核心的产出。

    流程：
      while 还没结束:
          1. 调 LLM（带上对话历史 + 工具定义）
          2. 如果 finish_reason='stop' → 返回最终答案
          3. 如果 finish_reason='tool_calls' → 执行工具 → 结果追加到对话 → 继续循环
          4. 如果超过 max_iterations → 强制停止

    参数：
      user_query      : 用户问题
      system_prompt   : 系统提示（可选）
      max_iterations  : 最大推理步数（安全阀，防止无限循环）
      verbose         : 是否打印每一步的详情

    返回：
      {
          "answer": "最终答案",
          "iterations": 实际循环次数,
          "tool_calls": [{"tool": "calculator", "args": {...}, "result": "..."}, ...],
          "history": messages列表（完整对话历史）
      }
    """
    if system_prompt is None:
        system_prompt = (
            "你是一个智能助手，可以使用工具来完成用户的请求。"
            "遇到数学计算请使用 calculator 工具，遇到日期时间问题请使用 get_current_time 工具。"
            "你可以分步骤解决复杂问题——先调用一个工具，根据结果再决定下一步。"
            "当用户问题不需要工具时，直接回答即可。"
        )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query},
    ]

    tool_calls_log = []
    iterations = 0

    while iterations < max_iterations:
        iterations += 1

        if verbose:
            print(f"\n  ══ Round {iterations} ══")

        # Step 1: 调 LLM
        response = llm_client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            tools=ALL_TOOL_SCHEMAS,
            temperature=0.0,
        )

        msg = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        if verbose:
            print(f"    finish_reason: {finish_reason}")

        # Step 2: 判断结束条件
        if finish_reason == "stop":
            # 模型直接回答（不需要工具，或工具结果已足够）
            answer = msg.content or ""
            if verbose:
                print(f"    ✅ Agent 完成回答")
                preview = answer[:100] + "..." if len(answer) > 100 else answer
                print(f"    📝 {preview}")
            break

        elif finish_reason == "tool_calls" or msg.tool_calls:
            # 模型要求调用工具
            if verbose:
                print(f"    🧠 模型决定调用 {len(msg.tool_calls)} 个工具")

            # 把 assistant 消息（含 tool_calls）加入对话
            # 注意：tool_calls 格式需要和 OpenAI API 一致
            serialized_tool_calls = []
            for tc in msg.tool_calls:
                serialized_tool_calls.append({
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                })

            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": serialized_tool_calls,
            })

            # 执行每个工具
            for tc in msg.tool_calls:
                tool_name = tc.function.name
                arguments = json.loads(tc.function.arguments)

                if verbose:
                    print(f"    🔧 执行：{tool_name}({json.dumps(arguments, ensure_ascii=False)})")

                result = execute_tool(tool_name, arguments)

                if verbose:
                    print(f"    📊 结果：{result}")

                tool_calls_log.append({
                    "round": iterations,
                    "tool": tool_name,
                    "args": arguments,
                    "result": result,
                })

                # 把工具结果加入对话
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })

        else:
            # 异常情况：既没有 stop 也没有 tool_calls
            if verbose:
                print(f"    ⚠️ 意外的 finish_reason: {finish_reason}")
            break

    # 超限强制停止
    if iterations >= max_iterations and finish_reason != "stop":
        answer = f"⚠️ Agent 已达到最大推理步数（{max_iterations}），强制停止。请简化问题或增加 max_iterations。"

    return {
        "answer": answer,
        "iterations": iterations,
        "tool_calls": tool_calls_log,
        "history": messages,
    }

# ── 3.3 测试 Agent ──
print("\n" + "─" * 50)
print("3.3 测试 Agent：三个不同场景")
print()

# 场景 A：需要计算器
print("╔" + "═" * 50 + "╗")
print("║  场景 A：纯数学计算（应该触发 calculator）")
print("╚" + "═" * 50 + "╝")

result_a = run_agent("小明有 150 块钱，买了 3 本书每本 28.5 元，又买了 5 支笔每支 3.8 元，他还剩多少钱？")

print(f"\n  🎯 最终答案：{result_a['answer']}")
print(f"  📊 统计：{result_a['iterations']} 轮推理 · {len(result_a['tool_calls'])} 次工具调用")

# 场景 B：需要时间查询
print("\n\n╔" + "═" * 50 + "╗")
print("║  场景 B：时间查询（应该触发 get_current_time）")
print("╚" + "═" * 50 + "╝")

result_b = run_agent("今天星期几？今年还剩多少天？（注意：一个月按30天估算即可）")

print(f"\n  🎯 最终答案：{result_b['answer']}")
print(f"  📊 统计：{result_b['iterations']} 轮推理 · {len(result_b['tool_calls'])} 次工具调用")

# 场景 C：不需要工具
print("\n\n╔" + "═" * 50 + "╗")
print("║  场景 C：常识问答（不需要工具，直接回答）")
print("╚" + "═" * 50 + "╝")

result_c = run_agent("Python 是什么？用一两句话解释。")

print(f"\n  🎯 最终答案：{result_c['answer']}")
print(f"  📊 统计：{result_c['iterations']} 轮推理 · {len(result_c['tool_calls'])} 次工具调用")

input("\n按 Enter 进入实验 4：封装可复用的 AgentRunner 类...")

# ============================================================
# 实验 4：封装 AgentRunner 类 — 可复用的 Agent 引擎
# ============================================================
print("\n" + "=" * 65)
print("实验 4：封装 AgentRunner —— 一个可复用的 Agent 引擎")
print("=" * 65)
print("""
前三个实验我们逐步实现了 Agent 循环的核心逻辑。
现在把它封装成一个类——就像 Week 1 把 API 调用封装成 ai_utils.py 一样。

设计目标：
  ✅ 注册工具：add_tool(name, schema, func)
  ✅ 运行 Agent：run(query) → 自动循环
  ✅ 查看过程：tool_calls_log 记录每一步
  ✅ 安全阀：max_iterations 防止无限循环
""")

class AgentRunner:
    """
    AI Agent 运行器 —— 一个可复用的 Agent 引擎。

    用法：
      agent = AgentRunner()
      agent.add_tool("calculator", schema, calculator_func)
      agent.add_tool("get_time", schema, time_func)
      result = agent.run("今天几号？帮我算一下 123 * 456")

    Agent 循环（每次 run 的内部逻辑）：
      ┌─────────────────────────────────────────────┐
      │ while 没结束 and 没超限:                     │
      │   调 LLM（对话历史 + 所有工具定义）           │
      │   if 模型返回 tool_calls:                    │
      │     → 执行工具 → 结果加入对话 → 继续循环      │
      │   elif 模型返回 content:                     │
      │     → 这就是最终答案，返回！                  │
      │   else:                                      │
      │     → 异常，退出                             │
      └─────────────────────────────────────────────┘
    """

    def __init__(self, model: str = None, temperature: float = 0.0,
                 max_iterations: int = 5):
        self.model = model or LLM_MODEL
        self.temperature = temperature
        self.max_iterations = max_iterations

        # 工具注册表
        self._tools = {}       # {"tool_name": {"schema": ..., "func": ...}}
        self._tool_schemas = [] # 传给 LLM 的 schema 列表

        # 运行记录
        self.tool_calls_log = []
        self.iterations = 0
        self.last_history = []

    def add_tool(self, name: str, description: str, parameters: dict, func):
        """
        注册一个工具。

        参数：
          name        : 工具名（如 "calculator"）
          description : 工具用途描述（给模型看的，要写清楚！）
          parameters  : 参数 JSON Schema
          func        : 实际执行的函数，接收 **kwargs
        """
        schema = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters,
            }
        }
        self._tools[name] = {"schema": schema, "func": func}
        self._tool_schemas.append(schema)
        return self  # 支持链式调用

    def run(self, user_query: str, system_prompt: str = None,
            verbose: bool = True) -> dict:
        """
        运行 Agent：接收用户问题，自主决定用什么工具，返回最终答案。

        返回：
          {
              "answer": "最终答案",
              "iterations": 循环次数,
              "tool_calls": 工具调用记录列表,
              "history": 完整对话历史,
          }
        """
        if system_prompt is None:
            tool_descriptions = "\n".join(
                f"  - {name}: {t['schema']['function']['description']}"
                for name, t in self._tools.items()
            )
            system_prompt = (
                f"你是一个智能助手，可以使用以下工具来帮助用户：\n"
                f"{tool_descriptions}\n\n"
                f"规则：\n"
                f"1. 遇到需要计算的问题，使用工具而不是自己算\n"
                f"2. 可以分步解决复杂问题\n"
                f"3. 如果问题不需要工具，直接回答\n"
                f"4. 在答案中告诉用户你使用了什么工具"
            )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query},
        ]

        self.tool_calls_log = []
        self.iterations = 0
        answer = ""
        finish_reason = ""

        while self.iterations < self.max_iterations:
            self.iterations += 1

            if verbose:
                print(f"\n  ══ Round {self.iterations} ══")

            response = llm_client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self._tool_schemas if self._tool_schemas else None,
                temperature=self.temperature,
            )

            msg = response.choices[0].message
            finish_reason = response.choices[0].finish_reason

            if verbose:
                print(f"    finish_reason: {finish_reason}")

            # 模型直接用文本回答
            if finish_reason == "stop":
                answer = msg.content or ""
                if verbose:
                    print(f"    ✅ 完成 —— {len(answer)} 字符")
                break

            # 模型要求调用工具
            elif (finish_reason == "tool_calls" or
                  getattr(finish_reason, 'startswith', lambda x: False)("tool") or
                  msg.tool_calls):

                if verbose and msg.tool_calls:
                    tool_names = [tc.function.name for tc in msg.tool_calls]
                    print(f"    🔧 调用工具：{', '.join(tool_names)}")

                # 序列化 tool_calls
                serialized = []
                for tc in (msg.tool_calls or []):
                    serialized.append({
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    })

                messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": serialized,
                })

                # 执行工具
                for tc in (msg.tool_calls or []):
                    tool_name = tc.function.name
                    arguments = json.loads(tc.function.arguments)

                    result = self._execute_tool(tool_name, arguments)

                    if verbose:
                        result_preview = result[:60] + "..." if len(result) > 60 else result
                        print(f"    📊 {tool_name} → {result_preview}")

                    self.tool_calls_log.append({
                        "round": self.iterations,
                        "tool": tool_name,
                        "args": arguments,
                        "result": result,
                    })

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })
            else:
                # 意外情况
                if verbose:
                    print(f"    ⚠️ 意外的 finish_reason: {finish_reason}")
                break

        # 超限保护
        if self.iterations >= self.max_iterations and finish_reason not in ("stop", ""):
            answer = (
                f"⚠️ Agent 已达到最大推理步数（{self.max_iterations}），强制停止。\n"
                f"已完成 {len(self.tool_calls_log)} 次工具调用。\n"
                f"请尝试简化问题。"
            )

        self.last_history = messages

        return {
            "answer": answer,
            "iterations": self.iterations,
            "tool_calls": self.tool_calls_log,
            "history": messages,
        }

    def _execute_tool(self, tool_name: str, arguments: dict) -> str:
        """内部工具分发器"""
        if tool_name not in self._tools:
            return f"错误：未知工具 '{tool_name}'。可用工具：{list(self._tools.keys())}"

        tool = self._tools[tool_name]
        try:
            result = tool["func"](**arguments)
            return str(result)
        except Exception as e:
            return f"工具执行失败：{e}"

    def print_summary(self):
        """打印 Agent 执行摘要"""
        print(f"\n  ══ Agent 执行摘要 ══")
        print(f"  推理轮次：{self.iterations}")
        print(f"  工具调用：{len(self.tool_calls_log)} 次")
        for i, tc in enumerate(self.tool_calls_log):
            print(f"    {i+1}. Round {tc['round']} → {tc['tool']}({tc['args']}) → {tc['result'][:50]}")

# ── 测试 AgentRunner ──
print("\n" + "─" * 50)
print("测试 AgentRunner：链式注册 + 复杂任务")
print()

# 创建 Agent 并注册工具
agent = AgentRunner(max_iterations=5)

agent.add_tool(
    name="calculator",
    description="计算数学表达式。支持加减乘除、乘方、三角函数、对数等。遇到任何数学计算都应使用此工具。",
    parameters={
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "数学表达式，如 '2+3*4'、'sqrt(16)'、'sin(pi/2)'"
            }
        },
        "required": ["expression"]
    },
    func=lambda expression: calculator(expression),
).add_tool(
    name="get_current_time",
    description="获取当前日期时间或星期几。当用户问'今天几号''现在几点''星期几'时使用。",
    parameters={
        "type": "object",
        "properties": {
            "format_type": {
                "type": "string",
                "enum": ["datetime", "date", "time", "weekday"],
                "description": "返回格式"
            }
        },
        "required": ["format_type"]
    },
    func=lambda format_type="datetime": get_current_time(format_type),
)

# 测试多步推理
print("╔" + "═" * 50 + "╗")
print("║  综合测试：需要两步计算的数学问题")
print("╚" + "═" * 50 + "╝")

result = agent.run(
    "计算圆的面积，半径为 7.5 厘米。然后告诉我如果做 12 个这样的圆，总共需要多少面积的纸板？"
)

agent.print_summary()
print(f"\n  🎯 最终答案：\n{result['answer']}")

# 测试混合场景
print("\n\n╔" + "═" * 50 + "╗")
print("║  混合测试：需要计算器 + 时间查询")
print("╚" + "═" * 50 + "╝")

result2 = agent.run("今天是几月几号？从这个月开始到年底还有多少天？（假设每月30天）")

print(f"\n  🎯 最终答案：\n{result2['answer']}")

# ============================================================
# Day 15 总结
# ============================================================
print("\n" + "=" * 65)
print("Day 15 总结：你今天学到了什么")
print("=" * 65)
print("""
┌────────────────────────────────────────────────────────────────┐
│  1. Agent 的本质                                               │
│     Agent = LLM + 工具 + 循环                                   │
│     不是新技术，是 Function Calling + 控制流的组合              │
│                                                                │
│  2. Function Calling 机制                                       │
│     - 你定义工具（JSON Schema：名称 + 描述 + 参数）              │
│     - 模型决定要不要用、用哪个、传什么参数                      │
│     - 你执行工具，把结果返回给模型                              │
│     - 模型基于结果生成最终答案                                  │
│                                                                │
│  3. Agent 三步循环（面试必考）                                   │
│     Planning  → 分析问题，决定用什么工具                        │
│     Tool Use  → 调用工具，获取结果                              │
│     Reflection → 评估结果，决定是否还需要更多操作               │
│                                                                │
│  4. 关键工程实践                                                 │
│     - max_iterations=5：永远设上限，防止无限循环                │
│     - temperature=0.0：Agent 需要确定性，不要创造性              │
│     - 工具描述要写清楚：模型靠描述决定是否调用                   │
│     - 工具结果要简洁：太长会占满上下文                           │
│                                                                │
│  5. AgentRunner 类                                              │
│     - 可复用 Agent 引擎，后续每天都会用到                        │
│     - 链式注册工具：agent.add_tool(...).add_tool(...)           │
│     - 自动记录所有工具调用，便于调试                             │
└────────────────────────────────────────────────────────────────┘
""")

print("""
🔜 Day 16 预告：给 Agent 安装「眼睛」——网页搜索工具
  - 集成 Tavily Search API（让 Agent 能搜索实时信息）
  - 或者使用 DuckDuckGo（免费无需 API Key）
  - Agent + 搜索 + 时效性问题 = 质的飞跃
""")

print("Day 15 完成 ✅")
print(f"模型：{LLM_MODEL} | 工具数：{len(agent._tools)} | 最大推理步数：{agent.max_iterations}")
