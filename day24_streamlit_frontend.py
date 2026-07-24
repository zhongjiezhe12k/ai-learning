"""
Day 24-25 — Streamlit 前端 ↔ FastAPI 后端 前后端联通
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Day 22-23 我们搭建了 FastAPI 后端。今天用 Streamlit 写一个完整的前端，
通过 HTTP/SSE 调用后端，实现真正的「前后端分离」AI 应用。

学完今天你会：
  ✅ 理解前后端分离的 AI 应用架构
  ✅ Streamlit 调用 FastAPI REST API 的标准模式
  ✅ SSE 流式响应在前端的实时展示
  ✅ 会话管理从后端 API 驱动
  ✅ 拥有一个可演示的完整全栈 AI 应用

架构图：
  ┌─────────────────────┐     HTTP/SSE      ┌──────────────────────┐
  │  Streamlit 前端      │ ◄───────────────► │  FastAPI 后端         │
  │  (day24)            │                   │  (day23)             │
  │                     │                   │                      │
  │  💬 聊天界面         │  POST /chat       │  5 个 Tool            │
  │  📊 工具调用详情      │  POST /chat/stream│  Agent Loop           │
  │  🔄 会话管理         │  POST /session/*  │  Chroma 知识库        │
  │  📚 知识库搜索        │  POST /knowledge  │  B站搜索              │
  │  ⚙️ 设置面板         │  GET  /tools      │  限流 + 日志          │
  └─────────────────────┘                   └──────────────────────┘

启动方式：
  1. 先启动后端：uvicorn day23_api_refinement:app --port 8000
  2. 再启动前端：streamlit run day24_streamlit_frontend.py
"""

import streamlit as st
import requests
import json
import time
import sys

# ═══════════════════════════════════════════════════════════════
# 页面配置
# ═══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="🤖 AI Agent 全栈助手",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════
API_BASE = "http://localhost:8000"

# ═══════════════════════════════════════════════════════════════
# API 客户端模块
# ═══════════════════════════════════════════════════════════════

class APIClient:
    """FastAPI 后端的 Python 客户端"""

    def __init__(self, base_url: str = API_BASE):
        self.base = base_url.rstrip("/")

    def health(self) -> dict:
        """健康检查"""
        r = requests.get(f"{self.base}/", timeout=5)
        r.raise_for_status()
        return r.json()

    def list_tools(self) -> list:
        """获取工具列表"""
        r = requests.get(f"{self.base}/tools", timeout=5)
        return r.json()["tools"]

    def create_session(self) -> str:
        """创建会话"""
        r = requests.post(f"{self.base}/session/create", timeout=5)
        return r.json()["session_id"]

    def get_sessions(self) -> list:
        """获取活跃会话列表"""
        r = requests.get(f"{self.base}/session/list", timeout=5)
        return r.json()["sessions"]

    def get_session_history(self, session_id: str) -> dict:
        """获取会话历史"""
        r = requests.get(f"{self.base}/session/{session_id}", timeout=5)
        return r.json()

    def delete_session(self, session_id: str):
        """删除会话"""
        requests.delete(f"{self.base}/session/{session_id}", timeout=5)

    def chat(self, message: str, session_id: str = None,
             max_iterations: int = 6, tools: list[str] = None,
             temperature: float = 0.0) -> dict:
        """发送消息，返回完整结果"""
        payload = {
            "message": message,
            "max_iterations": max_iterations,
            "temperature": temperature,
        }
        if session_id:
            payload["session_id"] = session_id
        if tools:
            payload["tools"] = tools

        r = requests.post(f"{self.base}/chat", json=payload, timeout=120)
        r.raise_for_status()
        return r.json()

    def chat_stream(self, message: str, session_id: str = None,
                    max_iterations: int = 6, tools: list[str] = None):
        """流式发送消息，yield 每个事件"""
        payload = {
            "message": message,
            "max_iterations": max_iterations,
            "temperature": 0.0,
        }
        if session_id:
            payload["session_id"] = session_id
        if tools:
            payload["tools"] = tools

        r = requests.post(f"{self.base}/chat/stream", json=payload,
                         timeout=120, stream=True)
        for line in r.iter_lines():
            if line:
                line_str = line.decode("utf-8")
                if line_str.startswith("data: "):
                    yield json.loads(line_str[6:])

    def search_knowledge(self, query: str, n: int = 3) -> str:
        """直接搜索知识库"""
        r = requests.post(f"{self.base}/knowledge/search", json={
            "query": query, "n_results": n
        }, timeout=15)
        return r.json()["result"]

    def search_web(self, query: str, n: int = 5, sort: str = "relevance") -> str:
        """直接搜索网页"""
        r = requests.post(f"{self.base}/web/search", json={
            "query": query, "max_results": n, "sort": sort
        }, timeout=15)
        return r.json()["result"]


# ═══════════════════════════════════════════════════════════════
# Session State 初始化
# ═══════════════════════════════════════════════════════════════
if "api" not in st.session_state:
    st.session_state.api = APIClient()

if "session_id" not in st.session_state:
    st.session_state.session_id = None

if "messages" not in st.session_state:
    st.session_state.messages = []  # [{role, content, tool_calls, elapsed_ms}]

if "backend_ok" not in st.session_state:
    st.session_state.backend_ok = False

if "tools_available" not in st.session_state:
    st.session_state.tools_available = []

if "total_questions" not in st.session_state:
    st.session_state.total_questions = 0

if "total_tool_calls" not in st.session_state:
    st.session_state.total_tool_calls = 0

api = st.session_state.api

# ═══════════════════════════════════════════════════════════════
# 侧边栏
# ═══════════════════════════════════════════════════════════════

with st.sidebar:
    st.title("🤖 AI Agent 全栈助手")
    st.caption("Day 24-25 · 前后端联通")

    # ── 后端状态 ──
    st.subheader("🔌 后端连接")
    if st.button("🔄 检测后端"):
        try:
            info = api.health()
            st.session_state.backend_ok = True
            st.session_state.tools_available = api.list_tools()
            st.success(f"✅ 已连接 — {info['model']}")
        except Exception as e:
            st.session_state.backend_ok = False
            st.error(f"❌ 无法连接后端：{e}")
    else:
        if st.session_state.backend_ok:
            st.success("✅ 后端在线")
        else:
            st.warning("⚠️ 点击检测后端")

    st.divider()

    # ── 会话管理 ──
    st.subheader("💬 会话")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("✨ 新建会话", use_container_width=True):
            try:
                sid = api.create_session()
                st.session_state.session_id = sid
                st.session_state.messages = []
                st.rerun()
            except Exception as e:
                st.error(f"创建失败：{e}")
    with col2:
        if st.button("🗑️ 清空对话", use_container_width=True):
            if st.session_state.session_id:
                try:
                    api.delete_session(st.session_state.session_id)
                except Exception:
                    pass
            st.session_state.session_id = None
            st.session_state.messages = []
            st.rerun()

    if st.session_state.session_id:
        st.info(f"📌 当前会话：`{st.session_state.session_id}`")

    # 历史会话列表
    try:
        sessions = api.get_sessions()
        if sessions:
            st.caption(f"活跃会话：{len(sessions)} 个")
    except Exception:
        pass

    st.divider()

    # ── 工具选择 ──
    st.subheader("🔧 启用工具")
    tools_available = st.session_state.tools_available
    tool_names = [t["id"] for t in tools_available] if tools_available else [
        "knowledge_base_search", "web_search", "python_repl", "calculator", "get_current_time"
    ]
    tool_icons = {"knowledge_base_search": "📚", "web_search": "🔍", "python_repl": "🐍", "calculator": "🔢", "get_current_time": "🕐"}

    enabled_tools = []
    for t in tool_names:
        icon = tool_icons.get(t, "🔧")
        if st.checkbox(f"{icon} {t}", value=True, key=f"tool_{t}"):
            enabled_tools.append(t)

    st.divider()

    # ── 设置 ──
    st.subheader("⚙️ 参数")
    max_iter = st.slider("最大推理步数", 1, 15, 6)
    use_stream = st.checkbox("⚡ 流式输出", value=True)

    st.divider()

    # ── 统计 ──
    st.subheader("📊 统计")
    st.metric("问题数", st.session_state.total_questions)
    st.metric("工具调用", st.session_state.total_tool_calls)

    st.divider()
    st.caption("📡 后端：Day 23 FastAPI")
    st.caption("🎨 前端：Day 24-25 Streamlit")

# ═══════════════════════════════════════════════════════════════
# 主区域
# ═══════════════════════════════════════════════════════════════

st.title("🤖 AI Agent 全栈助手")
st.caption("知识库 + 搜索 + Python 执行 — 5 工具智能编排")

# ── Tab 切换 ──
tab_chat, tab_knowledge, tab_search = st.tabs(["💬 智能对话", "📚 知识库搜索", "🔍 网页搜索"])

# ═══════════════════════════════════════════
# Tab 1: 智能对话
# ═══════════════════════════════════════════
with tab_chat:
    # 渲染历史消息
    for i, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

            # 工具调用详情
            if msg.get("tool_calls"):
                with st.expander(f"🔧 工具调用（{len(msg['tool_calls'])} 次）", expanded=False):
                    for tc in msg["tool_calls"]:
                        cols = st.columns([1, 3, 1])
                        icon = tool_icons.get(tc["tool"], "🔧")
                        cols[0].metric("轮次", f"R{tc['round']}")
                        cols[1].code(f"{icon} {tc['tool']}({json.dumps(tc['args'], ensure_ascii=False)})", language="json")
                        cols[2].metric("耗时", f"{tc.get('elapsed_ms', 0):.0f}ms")

            if msg.get("elapsed_ms"):
                st.caption(f"⏱️ {msg['elapsed_ms']:.0f}ms")

    # 输入框
    if prompt := st.chat_input("输入你的问题..."):
        if not st.session_state.backend_ok:
            st.error("请先在侧边栏检测后端连接")
            st.stop()

        # 添加用户消息
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 调用后端
        with st.chat_message("assistant"):
            if use_stream:
                # ── 流式模式 ──
                tool_placeholder = st.empty()
                answer_placeholder = st.empty()
                status_placeholder = st.empty()

                tool_events = []
                final_answer = ""

                try:
                    for event in api.chat_stream(
                        prompt,
                        session_id=st.session_state.session_id,
                        max_iterations=max_iter,
                        tools=enabled_tools,
                    ):
                        etype = event["type"]
                        edata = event["data"]

                        if etype == "tool_call":
                            icon = tool_icons.get(edata["tool"], "🔧")
                            tool_events.append(edata)
                            with tool_placeholder.container():
                                st.info(f"{icon} **{edata['tool']}** — Round {edata['round']}")
                                st.code(
                                    f"参数: {json.dumps(edata['args'], ensure_ascii=False)}\n"
                                    f"结果: {edata['result'][:300]}",
                                    language="text"
                                )

                        elif etype == "answer":
                            final_answer = edata["answer"]
                            answer_placeholder.markdown(final_answer)
                            status_placeholder.success(
                                f"✅ {edata['iterations']} 轮完成 · "
                                f"{len(tool_events)} 次工具调用 · "
                                f"{edata.get('total_elapsed_ms', 0):.0f}ms"
                            )

                        elif etype == "done":
                            pass

                        elif etype == "error":
                            st.error(edata["message"])
                except Exception as e:
                    st.error(f"请求失败：{e}")
                    final_answer = f"错误：{str(e)}"

                # 保存到 session
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": final_answer,
                    "tool_calls": tool_events,
                })

            else:
                # ── 非流式模式 ──
                with st.spinner("Agent 思考中..."):
                    try:
                        result = api.chat(
                            prompt,
                            session_id=st.session_state.session_id,
                            max_iterations=max_iter,
                            tools=enabled_tools,
                        )
                        st.markdown(result["answer"])

                        if result["tool_calls"]:
                            with st.expander(f"🔧 工具调用（{len(result['tool_calls'])} 次）"):
                                for tc in result["tool_calls"]:
                                    icon = tool_icons.get(tc["tool"], "🔧")
                                    st.info(f"{icon} **{tc['tool']}** — Round {tc['round']}")
                                    st.code(
                                        f"参数: {json.dumps(tc['args'], ensure_ascii=False)}\n"
                                        f"结果: {tc['result'][:300]}",
                                        language="text"
                                    )

                        st.success(
                            f"✅ {result['iterations']} 轮 · "
                            f"{len(result['tool_calls'])} 次调用 · "
                            f"{result['total_elapsed_ms']:.0f}ms"
                        )

                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": result["answer"],
                            "tool_calls": result["tool_calls"],
                            "elapsed_ms": result["total_elapsed_ms"],
                        })

                    except Exception as e:
                        st.error(f"请求失败：{e}")

        # 首次交互自动创建会话
        if st.session_state.session_id is None:
            try:
                st.session_state.session_id = api.create_session()
            except Exception:
                pass

        st.session_state.total_questions += 1
        st.session_state.total_tool_calls += len(
            st.session_state.messages[-1].get("tool_calls", [])
        )

# ═══════════════════════════════════════════
# Tab 2: 知识库搜索
# ═══════════════════════════════════════════
with tab_knowledge:
    st.subheader("📚 直接搜索知识库")
    st.caption("不经过 Agent，直接查询 Chroma 向量数据库")

    kb_query = st.text_input("搜索内容", placeholder="输入关键词...", key="kb_query")
    kb_n = st.slider("返回条数", 1, 10, 3, key="kb_n")

    if st.button("🔍 搜索知识库", use_container_width=True):
        if not st.session_state.backend_ok:
            st.error("请先检测后端连接")
        elif kb_query:
            with st.spinner("检索中..."):
                try:
                    result = api.search_knowledge(kb_query, kb_n)
                    st.markdown(result)
                except Exception as e:
                    st.error(f"搜索失败：{e}")

# ═══════════════════════════════════════════
# Tab 3: 网页搜索
# ═══════════════════════════════════════════
with tab_search:
    st.subheader("🔍 直接搜索网页")
    st.caption("不经过 Agent，直接搜索 B站")

    web_query = st.text_input("搜索内容", placeholder="输入关键词...", key="web_query")
    col1, col2 = st.columns([3, 1])
    with col1:
        web_n = st.slider("返回条数", 1, 10, 5, key="web_n")
    with col2:
        web_sort = st.selectbox("排序", ["relevance", "newest"], format_func=lambda x: "综合" if x == "relevance" else "最新")

    if st.button("🔍 搜索网页", use_container_width=True):
        if not st.session_state.backend_ok:
            st.error("请先检测后端连接")
        elif web_query:
            with st.spinner("搜索中..."):
                try:
                    result = api.search_web(web_query, web_n, web_sort)
                    st.markdown(result)
                except Exception as e:
                    st.error(f"搜索失败：{e}")

# ═══════════════════════════════════════════
# 启动提示
# ═══════════════════════════════════════════
if not st.session_state.backend_ok:
    st.info("""
    👈 **开始之前**：请确保后端已启动，然后在侧边栏点击「检测后端」。

    ```bash
    # 终端 1：启动后端
    uvicorn day23_api_refinement:app --port 8000

    # 终端 2：启动前端
    streamlit run day24_streamlit_frontend.py
    ```
    """)
