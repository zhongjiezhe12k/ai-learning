"""
Day 19 - Agent 可视化监控台（Streamlit 版）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Day 15-18 我们在命令行跑通了 Agent 的完整能力。
今天把 Agent 的每一步「思考→调用→结果」变成可视化界面。

启动方式：
  streamlit run day19_agent_visual.py

学完今天你会：
  ✅ 掌握 Streamlit 聊天界面的 Agent 集成模式
  ✅ 实现 Agent 推理过程的可视化（每轮、每次工具调用）
  ✅ 理解 Session State 在 AI 应用中的作用
  ✅ 拥有一个可演示的 Agent Dashboard
  ✅ 学会如何让 AI 应用「透明化」——用户能看到 AI 在做什么

核心认知：
  ┌──────────────────────────────────────────────────────────────┐
  │  好的 AI 产品不只是「给出答案」，而是让用户「看到过程」          │
  │  可视化 Agent 推理 = 建立用户信任 + 方便调试 + 更好的 UX        │
  └──────────────────────────────────────────────────────────────┘
"""

import sys, json, math, io as _io, time as _time
import datetime as _dt
import streamlit as st

from config import client as llm_client, MODEL as LLM_MODEL

# ═══════════════════════════════════════════════════════════════
# 页面配置
# ═══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="🤖 Agent 可视化监控台",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════════════════════════
# Session State 初始化
# ═══════════════════════════════════════════════════════════════
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []  # [{"role":"user"/"assistant", "content":"...", "tool_calls":[...], "stats":{}}]

if "total_questions" not in st.session_state:
    st.session_state.total_questions = 0

if "total_tool_calls" not in st.session_state:
    st.session_state.total_tool_calls = 0


# ═══════════════════════════════════════════════════════════════
# 工具定义（同 Day 18，精简版）
# ═══════════════════════════════════════════════════════════════

# ── Tool 1: Calculator ──
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

# ── Tool 2: get_current_time ──
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

# ── Tool 3: web_search（B站搜索 + 时间戳校验）──
import requests

SEARCH_HEADERS = {
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
        resp = requests.get(url, headers=SEARCH_HEADERS, timeout=8)

        # 检查 HTTP 状态码
        if resp.status_code != 200:
            return f"搜索失败：HTTP {resp.status_code}（B站API暂时不可用）"

        # 检查响应是否为空
        raw_text = resp.text.strip()
        if not raw_text:
            return f"搜索失败：B站返回空响应（可能触发了反爬机制，请稍后重试）"

        # 安全解析 JSON
        try:
            data = resp.json()
        except Exception:
            preview = raw_text[:200].replace("\n", " ")
            return f"搜索失败：B站返回非JSON数据（{preview}...）"

        # 检查 B站 API 自身的错误码
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

# ── Tool 4: python_repl ──
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
                "description": "计算数学表达式。用于精确计算。支持 +-*/、sqrt、sin/cos、log、pi 等。",
                "parameters": {
                    "type": "object",
                    "properties": {"expression": {"type": "string", "description": "数学表达式"}},
                    "required": ["expression"]
                }
            }
        },
        "func": lambda expression: calculator(expression),
        "icon": "🔢",
        "color": "#f59e0b",  # amber
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
        "icon": "🕐",
        "color": "#8b5cf6",  # purple
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
                        "query": {"type": "string", "description": "搜索关键词"},
                        "max_results": {"type": "integer", "description": "返回条数，默认5"},
                        "sort": {
                            "type": "string",
                            "enum": ["relevance", "newest"],
                            "description": "排序：relevance=综合, newest=最新。时效性问题必须用newest！"
                        }
                    },
                    "required": ["query"]
                }
            }
        },
        "func": lambda query, max_results=5, sort="relevance": web_search(query, max_results, sort == "newest"),
        "icon": "🔍",
        "color": "#3b82f6",  # blue
    },
    "python_repl": {
        "schema": {
            "type": "function",
            "function": {
                "name": "python_repl",
                "description": "执行Python代码。用于数据处理、统计分析。已预装 math/json/statistics 等。用 print() 输出。",
                "parameters": {
                    "type": "object",
                    "properties": {"code": {"type": "string", "description": "Python代码"}},
                    "required": ["code"]
                }
            }
        },
        "func": lambda code: python_repl(code),
        "icon": "🐍",
        "color": "#22c55e",  # green
    },
}


# ═══════════════════════════════════════════════════════════════
# Agent 循环（采集每一步数据用于可视化）
# ═══════════════════════════════════════════════════════════════

def run_agent_detailed(user_query: str, system_prompt: str,
                       max_iterations: int, enabled_tools: list[str]) -> dict:
    """
    运行 Agent 并采集每一步的详细数据。

    返回：
      {
        "answer": str,
        "iterations": int,
        "tool_calls": [
          {"round": 1, "tool": "web_search", "args": {...}, "result": "..."},
          ...
        ],
        "rounds": [
          {"round": 1, "finish_reason": "tool_calls", "tool_calls": [...], "thinking": "..."},
          ...
        ],
        "stats": {"tools_used": {...}, "total_calls": int}
      }
    """
    tool_schemas = [ALL_TOOLS[n]["schema"] for n in enabled_tools if n in ALL_TOOLS]

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query},
    ]

    all_tool_calls = []
    rounds_detail = []
    iterations = 0
    finish_reason = ""

    while iterations < max_iterations:
        iterations += 1

        response = llm_client.chat.completions.create(
            model=LLM_MODEL, messages=messages,
            tools=tool_schemas if tool_schemas else None,
            temperature=0.0,
        )

        msg = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        round_info = {
            "round": iterations,
            "finish_reason": finish_reason,
            "tool_calls": [],
            "thinking": msg.content or "",
        }

        if finish_reason == "stop":
            round_info["answer"] = msg.content or ""
            rounds_detail.append(round_info)
            break

        elif msg.tool_calls:
            # 序列化 tool_calls
            serialized = []
            for tc in msg.tool_calls:
                serialized.append({
                    "id": tc.id, "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                })
            messages.append({
                "role": "assistant", "content": msg.content or "", "tool_calls": serialized,
            })

            # 执行每个工具
            for tc in msg.tool_calls:
                name = tc.function.name
                args = json.loads(tc.function.arguments)
                result = ALL_TOOLS[name]["func"](**args)

                call_record = {"round": iterations, "tool": name, "args": args, "result": result}
                all_tool_calls.append(call_record)
                round_info["tool_calls"].append(call_record)

                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

            rounds_detail.append(round_info)
        else:
            break

    if iterations >= max_iterations and finish_reason not in ("stop", ""):
        answer = f"⚠️ Agent 已达到最大推理步数（{max_iterations}），强制停止。"
    else:
        answer = rounds_detail[-1].get("answer", "") if rounds_detail else ""

    # 统计
    tools_used = {}
    for tc in all_tool_calls:
        tools_used[tc["tool"]] = tools_used.get(tc["tool"], 0) + 1

    return {
        "answer": answer,
        "iterations": iterations,
        "tool_calls": all_tool_calls,
        "rounds": rounds_detail,
        "stats": {
            "tools_used": tools_used,
            "total_calls": len(all_tool_calls),
            "max_iterations": max_iterations,
        },
    }


# ═══════════════════════════════════════════════════════════════
# 可视化辅助函数
# ═══════════════════════════════════════════════════════════════

def render_tool_call_card(tc: dict):
    """渲染单个工具调用卡片（颜色编码 + 可展开详情）"""
    tool_name = tc["tool"]
    meta = ALL_TOOLS.get(tool_name, {})
    icon = meta.get("icon", "🔧")
    color = meta.get("color", "#6b7280")

    with st.expander(f"{icon} **{tool_name}** — Round {tc['round']}", expanded=False):
        # 参数区
        st.markdown("**📥 参数：**")
        if tool_name == "python_repl":
            code = tc["args"].get("code", "")
            st.code(code, language="python")
        elif tool_name == "web_search":
            st.info(f"🔍 {tc['args'].get('query', '')}")
        else:
            st.json(tc["args"])

        # 结果区
        st.markdown("**📤 结果：**")
        result = tc["result"]
        if tool_name == "web_search":
            # 搜索结果分条显示
            for line in result.split("\n\n")[:5]:
                if line.strip():
                    st.caption(line.strip()[:200])
        elif tool_name == "python_repl":
            if len(result) > 500:
                st.text(result[:500] + "\n... (截断)")
            else:
                st.text(result)
        else:
            st.success(result)


def render_agent_chain(rounds: list[dict]):
    """渲染 Agent 推理链条 —— 用横向流程图展示"""
    if not rounds:
        return

    st.markdown("### 🧠 Agent 推理链条")

    # 用 columns 模拟流程图
    total_steps = sum(len(r.get("tool_calls", [])) for r in rounds)
    if total_steps == 0:
        st.caption("（Agent 直接回答，未使用工具）")
        return

    # 构建步骤列表
    steps_html = '<div style="display:flex;align-items:center;flex-wrap:wrap;gap:4px;padding:12px 0;font-size:14px;">'

    for r in rounds:
        # Round 标记
        steps_html += (
            f'<div style="background:#1e293b;color:#94a3b8;padding:4px 10px;'
            f'border-radius:12px;font-weight:bold;margin:0 2px;">R{r["round"]}</div>'
        )
        for tc in r.get("tool_calls", []):
            meta = ALL_TOOLS.get(tc["tool"], {})
            icon = meta.get("icon", "🔧")
            bg = meta.get("color", "#6b7280")
            label = tc["tool"]
            # 箭头 + 工具卡片
            steps_html += (
                f'<div style="color:#64748b;font-size:18px;">→</div>'
                f'<div style="background:{bg}22;border:1px solid {bg};color:{bg};'
                f'padding:4px 10px;border-radius:8px;white-space:nowrap;">'
                f'{icon} {label}</div>'
            )

    # 结束标记
    if rounds[-1].get("finish_reason") == "stop":
        steps_html += (
            f'<div style="color:#64748b;font-size:18px;">→</div>'
            f'<div style="background:#22c55e22;border:1px solid #22c55e;color:#22c55e;'
            f'padding:4px 10px;border-radius:8px;">✅ 完成</div>'
        )

    steps_html += '</div>'
    st.markdown(steps_html, unsafe_allow_html=True)


def render_stats_bar(stats: dict, elapsed: float):
    """渲染统计信息栏"""
    cols = st.columns(5)
    with cols[0]:
        st.metric("⏱️ 耗时", f"{elapsed:.1f}s")
    with cols[1]:
        st.metric("🔄 推理轮次", stats.get("max_iterations", 0))
    with cols[2]:
        st.metric("🔧 工具调用", stats.get("total_calls", 0))
    with cols[3]:
        tools_str = ", ".join(f"{k}:{v}" for k, v in stats.get("tools_used", {}).items())
        st.metric("📊 工具分布", tools_str if tools_str else "无")
    with cols[4]:
        st.metric("🤖 模型", LLM_MODEL)


# ═══════════════════════════════════════════════════════════════
# 侧边栏：配置
# ═══════════════════════════════════════════════════════════════

with st.sidebar:
    st.title("⚙️ Agent 配置")

    st.markdown("---")

    # 工具选择
    st.subheader("🔧 启用工具")
    enabled_tools = []
    for name, meta in ALL_TOOLS.items():
        if st.checkbox(
            f"{meta['icon']} {name}",
            value=True,
            help=meta["schema"]["function"]["description"],
        ):
            enabled_tools.append(name)

    st.markdown("---")

    # 推理参数
    st.subheader("🎛️ 推理参数")
    max_iterations = st.slider(
        "最大推理步数",
        min_value=1, max_value=10, value=6,
        help="限制 Agent 最多调用多少次工具。值越大 Agent 越「执着」，但耗时越长。",
    )

    st.markdown("---")

    # System Prompt
    st.subheader("📋 System Prompt")
    prompt_preset = st.selectbox(
        "预设",
        ["默认（通用助手）", "Plan-then-Execute（先规划再执行）", "简洁模式", "自定义"],
    )

    if prompt_preset == "默认（通用助手）":
        system_prompt = (
            f"当前日期：{CURRENT_DATE} {CURRENT_WEEKDAY}\n"
            f"你是一个具备多种工具的智能助手。\n"
            f"规则：\n"
            f"1. 需要精确计算 → calculator\n"
            f"2. 需要实时信息 → web_search（时效性问题必须 sort='newest'）\n"
            f"3. 需要数据处理/统计分析 → python_repl\n"
            f"4. 需要日期时间 → get_current_time\n"
            f"5. 复杂任务先规划再执行，按合理顺序调用工具\n"
            f"6. 简单问题直接回答，不要调用工具\n"
            f"7. ⚠️ 时效性原则：每条结果都有 📅 发布时间，以最新视频为准，旧视频(>3个月)的信息可能过时"
        )
    elif prompt_preset == "Plan-then-Execute（先规划再执行）":
        system_prompt = (
            f"当前日期：{CURRENT_DATE} {CURRENT_WEEKDAY}\n"
            f"你是一个会「先规划再执行」的智能助手。\n\n"
            f"## 工作流程（重要！）\n"
            f"对于需要多个工具的任务，你必须：\n"
            f"1. 先输出【执行计划】，列出每一步要做什么、用什么工具\n"
            f"2. 然后按计划逐步调用工具\n"
            f"3. 完成后对照计划检查是否有遗漏\n\n"
            f"## 可用工具\n"
            f"- calculator: 计算数学表达式\n"
            f"- get_current_time: 获取时间日期\n"
            f"- web_search: 搜索互联网\n"
            f"- python_repl: 执行Python代码\n\n"
            f"## 规则\n"
            f"简单问题不需要计划，直接回答。复杂任务必须先写计划。"
        )
    elif prompt_preset == "简洁模式":
        system_prompt = (
            f"当前日期：{CURRENT_DATE}\n"
            f"你是一个简洁的助手。能用工具解决的问题就用工具，回答尽量简短。"
        )
    else:
        system_prompt = st.text_area(
            "自定义 System Prompt",
            value=f"当前日期：{CURRENT_DATE} {CURRENT_WEEKDAY}\n你是一个智能助手。",
            height=200,
        )

    st.markdown("---")

    # 统计
    st.subheader("📈 会话统计")
    st.caption(f"已提问：{st.session_state.total_questions} 次")
    st.caption(f"累计工具调用：{st.session_state.total_tool_calls} 次")

    if st.button("🧹 清空对话历史", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.total_questions = 0
        st.session_state.total_tool_calls = 0
        st.rerun()

    st.markdown("---")
    st.caption(f"模型：{LLM_MODEL}")
    st.caption("Day 19 — Agent 可视化监控台")


# ═══════════════════════════════════════════════════════════════
# 主区域
# ═══════════════════════════════════════════════════════════════

st.title("🤖 AI Agent 可视化监控台")
st.caption("看到 Agent 的每一步思考 —— 从「黑盒」到「白盒」")

# ── 历史对话展示 ──
for msg_idx, msg in enumerate(st.session_state.chat_history):
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.write(msg["content"])
    else:
        with st.chat_message("assistant"):
            # 显示答案
            st.markdown(msg["content"])

            # 显示统计栏
            if msg.get("stats"):
                st.markdown("---")
                render_stats_bar(msg["stats"], msg.get("elapsed", 0))

            # 显示推理链条
            if msg.get("rounds"):
                st.markdown("---")
                render_agent_chain(msg["rounds"])

            # 显示每个工具调用的详细卡片
            if msg.get("tool_calls"):
                st.markdown("---")
                st.markdown("### 📋 工具调用详情")
                for tc in msg["tool_calls"]:
                    render_tool_call_card(tc)

# ── 输入区 ──
st.markdown("---")
user_input = st.chat_input(
    "输入你的问题，观察 Agent 如何一步步思考...",
    key="chat_input",
)

if user_input:
    if not enabled_tools:
        st.warning("⚠️ 请至少在侧边栏启用一个工具")
    else:
        # 记录用户消息
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        # 运行 Agent
        with st.spinner("🤔 Agent 正在思考..."):
            t_start = _time.time()
            result = run_agent_detailed(
                user_query=user_input,
                system_prompt=system_prompt,
                max_iterations=max_iterations,
                enabled_tools=enabled_tools,
            )
            elapsed = _time.time() - t_start

        # 记录回答
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": result["answer"],
            "tool_calls": result["tool_calls"],
            "rounds": result["rounds"],
            "stats": result["stats"],
            "elapsed": elapsed,
        })

        st.session_state.total_questions += 1
        st.session_state.total_tool_calls += result["stats"]["total_calls"]

        st.rerun()


# ═══════════════════════════════════════════════════════════════
# 底部说明
# ═══════════════════════════════════════════════════════════════

if not st.session_state.chat_history:
    st.markdown("---")
    st.info("""
    👋 **欢迎使用 Agent 可视化监控台！**

    这是 Day 19 的学习成果 —— 你能看到 Agent 的每一步推理过程：
    - 🧠 **推理链条**：Agent 在每一轮做了什么决定
    - 🔧 **工具调用**：每次工具调用的参数和返回结果
    - 📊 **统计面板**：耗时、轮次、工具使用分布

    **试试这些问题：**
    - "帮我算一下 12345 × 67890 等于多少？"
    - "搜索2026年最火的AI工具"
    - "用Python计算斐波那契数列前20项，并观察相邻两项比值"
    - "现在是几月几号？今年还剩多少天？"
    """)
