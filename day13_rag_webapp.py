"""
Day 13 - 私有文档 AI 问答系统（Streamlit Web 版）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⭐ Week 2 核心产出：上传文档 → AI 问答 → 原文溯源

Day 8-12 我们在命令行跑通了 RAG 全流程 + 检索调优。
今天把它做成一个真正可用的 Web 应用 — 这是你简历上能展示的项目。

启动方式：
  streamlit run day13_rag_webapp.py

学完今天你会：
  ✅ 掌握 Streamlit 聊天界面的设计模式
  ✅ 实现文件上传 → 自动入库的完整管线
  ✅ 流式 RAG 回答 + 原文溯源展示
  ✅ 可调参数的知识库管理面板
  ✅ 拥有一个可以部署的完整 AI 应用

架构总览：
  ┌─────────────┐    ┌──────────────┐    ┌───────────┐
  │  文件上传    │ → │  Chroma 向量库 │ ← │ LLM 生成  │
  │  PDF/TXT    │    │  (持久化存储)  │    │ (流式输出) │
  └─────────────┘    └──────────────┘    └───────────┘
        ↑                   ↑                   ↑
        │                   │                   │
  ┌─────┴───────────────────┴───────────────────┴─────┐
  │              Streamlit Web UI                      │
  │  侧边栏：文档管理 + 参数控制                        │
  │  主区域：对话界面 + 原文溯源                        │
  └────────────────────────────────────────────────────┘
"""

import sys, os
import tempfile
import time
import hashlib

import streamlit as st
import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader, PyPDFLoader
import glob as glob_module

from config import client as llm_client, MODEL as LLM_MODEL

# ============================================================
# 0. 页面配置
# ============================================================
st.set_page_config(
    page_title="📚 私有文档 AI 问答",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# 1. 初始化 Session State（Streamlit 的状态记忆）
# ============================================================
# 每次 rerun 时，session_state 之外的一切都会被重置。
# 所以持久化对象（Chroma client / 聊天记录 / 已处理文件）必须放在这里。

if "chroma_client" not in st.session_state:
    st.session_state.chroma_client = chromadb.PersistentClient(
        path="./chroma_db/day13_webapp"
    )

if "collection" not in st.session_state:
    # 尝试加载已有 collection
    try:
        st.session_state.collection = st.session_state.chroma_client.get_collection("rag_webapp")
    except Exception:
        st.session_state.collection = None

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []  # [{"role": "user"/"assistant", "content": ..., "sources": [...]}]

if "processed_files" not in st.session_state:
    st.session_state.processed_files = []  # 已入库的文件名列表

if "kb_ready" not in st.session_state:
    st.session_state.kb_ready = st.session_state.collection is not None and st.session_state.collection.count() > 0


# ============================================================
# 2. 核心引擎函数（复用 Day 11 + Day 12 的精华）
# ============================================================

def load_and_split_files(uploaded_files, chunk_size: int, overlap: int,
                         progress_callback=None) -> list[dict]:
    """
    加载上传的文件（PDF/TXT），切割成 chunk。

    参数：
      uploaded_files    : Streamlit UploadedFile 对象列表
      chunk_size        : 切割大小
      overlap           : 重叠字符数
      progress_callback : 可选的进度回调

    返回：
      [{"text": str, "source": str, "page": int}, ...]
    """
    all_docs = []
    total_files = len(uploaded_files)

    for idx, uf in enumerate(uploaded_files):
        if progress_callback:
            progress_callback(f"读取中：{uf.name}")

        # 将上传的文件保存到临时目录（LangChain 的 loader 需要文件路径）
        suffix = os.path.splitext(uf.name)[1].lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uf.getvalue())
            tmp_path = tmp.name

        try:
            if suffix == ".pdf":
                loader = PyPDFLoader(tmp_path)
            elif suffix == ".txt":
                loader = TextLoader(tmp_path, encoding="utf-8")
            else:
                # 尝试用 TextLoader 兜底
                loader = TextLoader(tmp_path, encoding="utf-8")

            loaded = loader.load()
            # 标记来源文件名
            for doc in loaded:
                doc.metadata["source"] = uf.name
            all_docs.extend(loaded)

        except Exception as e:
            st.warning(f"⚠️ 无法加载 {uf.name}：{e}")
        finally:
            # 清理临时文件
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

        if progress_callback:
            progress_callback(f"已完成 {idx + 1}/{total_files}")

    if not all_docs:
        return []

    # 切割
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", "。", ".", "，", ",", " ", ""],
    )
    chunks = splitter.split_documents(all_docs)

    return [
        {
            "text": c.page_content,
            "source": c.metadata.get("source", "unknown"),
            "page": c.metadata.get("page"),
        }
        for c in chunks
    ]


def build_knowledge_base(chunks: list[dict], progress_callback=None) -> chromadb.Collection:
    """
    将 chunk 向量化并存入 Chroma。

    返回 Chroma collection 对象。
    """
    # 清空旧 collection
    try:
        st.session_state.chroma_client.delete_collection("rag_webapp")
    except Exception:
        pass

    col = st.session_state.chroma_client.create_collection(
        name="rag_webapp",
        metadata={
            "description": "Day 13 RAG Web 问答系统",
            "created_at": time.strftime("%Y-%m-%d %H:%M"),
        },
    )

    if not chunks:
        return col

    # 分批向量化（避免 API 限流）
    batch_size = 20
    total_batches = (len(chunks) + batch_size - 1) // batch_size
    for batch_idx in range(0, len(chunks), batch_size):
        batch = chunks[batch_idx : batch_idx + batch_size]
        current_batch_num = batch_idx // batch_size + 1

        if progress_callback:
            progress_callback(
                f"向量化中... ({batch_idx + 1}-{min(batch_idx + batch_size, len(chunks))}/{len(chunks)})",
                current_batch_num / total_batches,
            )

        # 批量获取 embedding
        embeddings = []
        for c in batch:
            resp = llm_client.embeddings.create(model="text-embedding-v2", input=c["text"])
            embeddings.append(resp.data[0].embedding)

        # 批量入库
        for j, (chunk, emb) in enumerate(zip(batch, embeddings)):
            col.add(
                ids=[f"c_{batch_idx + j:05d}"],
                embeddings=[emb],
                documents=[chunk["text"]],
                metadatas=[{
                    "source": os.path.basename(chunk["source"]),
                    "page": chunk.get("page") or -1,
                }],
            )

    return col


def retrieve(query: str, col, top_k: int = 5, min_similarity: float = 0.2) -> list[dict]:
    """语义检索（复用 Day 11 的核心逻辑）"""
    if col is None or col.count() == 0:
        return []

    q_emb = llm_client.embeddings.create(
        model="text-embedding-v2", input=query
    ).data[0].embedding

    raw = col.query(query_embeddings=[q_emb], n_results=min(top_k, col.count()))

    results = []
    for i, (doc, meta, dist) in enumerate(zip(
        raw["documents"][0], raw["metadatas"][0], raw["distances"][0]
    )):
        sim = round(1.0 / (1.0 + dist), 4)
        if sim >= min_similarity:
            results.append({
                "text": doc,
                "source": meta.get("source", "unknown"),
                "page": meta.get("page", -1),
                "similarity": sim,
                "distance": round(dist, 4),
                "index": i + 1,
            })
    return results


def build_rag_prompt(question: str, sources: list[dict]) -> tuple[str, str]:
    """
    构建 RAG Prompt（标准版，复用 Day 11 的设计）。

    返回：(system_prompt, user_prompt)
    """
    # 拼接上下文
    context_parts = []
    for s in sources:
        header = f"[资料{s['index']}]（来源：{s['source']}"
        if s["page"] >= 0:
            header += f"，第{s['page'] + 1}页"
        header += f"，相似度：{s['similarity']:.2f}）"
        context_parts.append(f"{header}\n{s['text']}")
    context = "\n\n".join(context_parts)

    system = (
        "你是一个严谨的 AI 知识库助手。请严格根据提供的参考资料回答问题。"
        "资料中没有的信息，请如实说明「知识库中暂无相关记录」。"
        "回答时请引用资料编号（如 [资料1]）。"
    )
    user = (
        f"【参考资料】\n{'─' * 50}\n{context}\n{'─' * 50}\n\n"
        f"【用户问题】{question}\n\n"
        f"请基于以上资料给出准确、有条理的回答。重要信息需标注来源编号。"
    )
    return system, user


def stream_rag_answer(question: str, sources: list[dict]):
    """
    RAG 流式生成器 —— 逐 token yield 给 Streamlit。

    yield 格式：(event_type, data)
      - ("token", "文字片段")
      - ("done", None)
    """
    if not sources:
        yield ("token", "⚠️ 未检索到相关内容。请先上传文档或调整相似度阈值。")
        yield ("done", None)
        return

    system, user = build_rag_prompt(question, sources)

    stream = llm_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.3,
        stream=True,
    )

    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield ("token", chunk.choices[0].delta.content)

    yield ("done", None)


# ============================================================
# 3. 侧边栏：文档管理 + 参数控制 + 知识库状态
# ============================================================
with st.sidebar:
    st.title("📚 知识库管理")

    # ── 3.1 文档上传区 ──
    st.subheader("📁 上传文档")
    uploaded_files = st.file_uploader(
        "支持 PDF / TXT 格式",
        type=["pdf", "txt"],
        accept_multiple_files=True,
        help="可以选择多个文件同时上传。知识库内容会保留在磁盘（重启不丢失）。",
        key="file_uploader",
    )

    # ── 3.2 参数设置 ──
    st.subheader("⚙️ 切割参数")
    st.caption("来自 Day 12 的研究结论：chunk_size=400, overlap=60 是最佳起点")

    col_a, col_b = st.columns(2)
    with col_a:
        chunk_size = st.slider(
            "chunk_size", min_value=100, max_value=1000,
            value=400, step=50,
            help="每个文本块的大小（字符数）。太小丢失上下文，太大语义稀释。"
        )
    with col_b:
        overlap = st.slider(
            "overlap", min_value=0, max_value=200,
            value=60, step=10,
            help="相邻块的重叠量。10-15% 的 chunk_size 为最佳。"
        )

    st.caption("检索参数")
    col_c, col_d = st.columns(2)
    with col_c:
        top_k = st.slider(
            "top_k", min_value=1, max_value=10,
            value=5, step=1,
            help="每次检索返回的资料数量。建议 3-7。"
        )
    with col_d:
        min_similarity = st.slider(
            "相似度阈值", min_value=0.0, max_value=0.8,
            value=0.2, step=0.05,
            help="低于此相似度的结果会被过滤。越高越精确，越低越全。"
        )

    # ── 3.3 操作按钮 ──
    st.divider()

    process_btn = st.button(
        "🚀 处理文档并建库",
        type="primary",
        use_container_width=True,
        disabled=not uploaded_files,
        help="加载上传的文件 → 切割 → 向量化 → 存入 Chroma",
    )

    col_clear1, col_clear2 = st.columns(2)
    with col_clear1:
        clear_chat_btn = st.button("🗑️ 清空对话", use_container_width=True)
    with col_clear2:
        reset_kb_btn = st.button("🔄 重置知识库", use_container_width=True)

    # ── 3.4 知识库状态面板 ──
    st.divider()
    st.subheader("📊 知识库状态")

    if st.session_state.kb_ready and st.session_state.collection:
        col = st.session_state.collection
        count = col.count()
        st.success(f"✅ 就绪 — {count} 个 chunks")

        # 统计来源文件
        try:
            all_meta = col.get()
            sources = {}
            for meta in all_meta["metadatas"]:
                src = meta.get("source", "unknown")
                sources[src] = sources.get(src, 0) + 1
            for src, cnt in sources.items():
                st.caption(f"  📄 {src}（{cnt} chunks）")
        except Exception:
            pass
    else:
        st.info("ℹ️ 尚未建库 — 请上传文档并点击「处理文档并建库」")

    st.divider()
    st.caption("💡 Day 13 · Week 2 核心产出 · 私有文档 AI 问答系统")

# ============================================================
# 4. 文档处理逻辑（按钮触发）
# ============================================================
if process_btn and uploaded_files:
    with st.sidebar:
        status_area = st.empty()

    # 使用主区域的 spinner 显示进度
    with st.spinner("🔧 正在处理文档..."):
        status_msg = st.empty()

        def update_status(msg: str, progress: float = None):
            status_msg.text(f"  {msg}")

        # Step 1: 加载 + 切割
        update_status("📖 读取并切割文档...")
        chunks = load_and_split_files(
            uploaded_files, chunk_size, overlap,
            progress_callback=update_status,
        )

        if not chunks:
            st.error("❌ 未能从文档中提取到内容，请检查文件格式。")
            st.stop()

        update_status(f"📄 切割完成：{len(chunks)} 个 chunks")

        # Step 2: 向量化 + 入库
        progress_bar = st.progress(0.0)

        def update_progress(msg: str, pct: float = None):
            status_msg.text(f"  {msg}")
            if pct is not None:
                progress_bar.progress(pct)

        collection = build_knowledge_base(chunks, progress_callback=update_progress)
        progress_bar.progress(1.0)

        # Step 3: 更新 session state
        st.session_state.collection = collection
        st.session_state.kb_ready = True
        st.session_state.processed_files = [f.name for f in uploaded_files]

        # 清空旧对话（知识库变了，之前的回答已无意义）
        st.session_state.chat_history = []

        status_msg.text(f"  ✅ 知识库构建完成！{collection.count()} 个 chunks 已入库。")
        progress_bar.empty()

    st.success(f"✅ 知识库就绪 — {collection.count()} 个文本块，来自 {len(uploaded_files)} 个文件")
    st.rerun()

# 清空对话
if clear_chat_btn:
    st.session_state.chat_history = []
    st.rerun()

# 重置知识库
if reset_kb_btn:
    try:
        st.session_state.chroma_client.delete_collection("rag_webapp")
    except Exception:
        pass
    st.session_state.collection = None
    st.session_state.kb_ready = False
    st.session_state.chat_history = []
    st.session_state.processed_files = []
    st.rerun()


# ============================================================
# 5. 主区域：对话界面
# ============================================================
st.title("📚 私有文档 AI 问答系统")
st.caption("上传你的文档 → AI 基于文档内容回答 → 每个回答都有原文溯源")

# ── 5.1 渲染历史消息 ──
for msg in st.session_state.chat_history:
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.markdown(msg["content"])
    else:
        with st.chat_message("assistant"):
            st.markdown(msg["content"])
            # 展示引用来源
            if msg.get("sources"):
                with st.expander(f"📎 查看引用来源（{len(msg['sources'])} 条）"):
                    for s in msg["sources"]:
                        st.markdown(
                            f"**[资料{s['index']}] 相似度 {s['similarity']:.3f}** | "
                            f"来源：`{s['source']}`"
                            + (f" | 第{s['page'] + 1}页" if s.get("page", -1) >= 0 else "")
                        )
                        st.text(s["text"][:500])  # 截断过长文本
                        if len(s["text"]) > 500:
                            st.caption("...（文本过长已截断）")
                        st.divider()

# ── 5.2 聊天输入 ──
# 首页提示
if not st.session_state.chat_history:
    if not st.session_state.kb_ready:
        st.info(
            """
            👋 **欢迎使用私有文档 AI 问答系统！**

            **快速开始：**
            1. 在左侧上传 PDF 或 TXT 文档
            2. 调整参数（或直接使用默认值）
            3. 点击「处理文档并建库」
            4. 在下方的输入框中提问

            💡 **试试这些：**
            - 总结文档的主要内容
            - 文档中关于 XXX 是怎么说的？
            - 对比两个概念的区别
            - 提取文档中的关键数据

            📌 **提醒：** 知识库保存在本地磁盘，下次打开页面无需重新上传。点击「重置知识库」可清空。
            """
        )
    else:
        st.info(
            f"""
            ✅ 知识库就绪，包含 **{st.session_state.collection.count()}** 个文本块。

            在下方输入框中提问，AI 将基于你的文档内容回答。每个回答都会标注引用来源。
            """
        )

# 聊天输入框（固定在底部）
question = st.chat_input(
    "输入你的问题（基于已上传的文档）...",
    disabled=not st.session_state.kb_ready,
)

# ── 5.3 处理用户提问 ──
if question:
    # 添加用户消息到历史
    st.session_state.chat_history.append({
        "role": "user",
        "content": question,
    })

    # 渲染用户消息
    with st.chat_message("user"):
        st.markdown(question)

    # RAG 检索 + 流式生成
    with st.chat_message("assistant"):
        # Step 1: 检索
        with st.spinner("🔍 检索中..."):
            sources = retrieve(
                question, st.session_state.collection,
                top_k=top_k, min_similarity=min_similarity,
            )

        # 显示检索概况
        if sources:
            sim_summary = f"检索到 {len(sources)} 条资料（相似度 {sources[0]['similarity']:.3f} ~ {sources[-1]['similarity']:.3f}）"
        else:
            sim_summary = "未检索到相关内容"

        # Step 2: 流式生成答案
        answer_placeholder = st.empty()
        full_answer = ""

        for event_type, data in stream_rag_answer(question, sources):
            if event_type == "token":
                full_answer += data
                # 构建展示内容：检索摘要 + 回答正文
                display = f"🔍 *{sim_summary}*\n\n{full_answer}"
                answer_placeholder.markdown(display)
            elif event_type == "done":
                pass

        # 最终渲染
        final_display = f"🔍 *{sim_summary}*\n\n{full_answer}"
        answer_placeholder.markdown(final_display)

        # 展示引用来源
        if sources:
            with st.expander(f"📎 查看引用来源（{len(sources)} 条资料）", expanded=False):
                for s in sources:
                    st.markdown(
                        f"**■ [资料{s['index']}] 相似度 {s['similarity']:.3f}** "
                        f"| 📄 `{s['source']}`"
                        + (f" | 📍 第{s['page'] + 1}页" if s.get("page", -1) >= 0 else "")
                    )
                    # 高亮显示匹配文本
                    st.text(s["text"])
                    st.divider()

    # 保存助手消息到历史
    st.session_state.chat_history.append({
        "role": "assistant",
        "content": full_answer,
        "sources": sources,
    })


# ============================================================
# 6. 底部状态栏
# ============================================================
st.divider()
col_status1, col_status2, col_status3 = st.columns(3)
with col_status1:
    kb_status = "🟢 知识库就绪" if st.session_state.kb_ready else "⚪ 知识库未初始化"
    st.caption(kb_status)
with col_status2:
    st.caption(f"💬 对话轮次：{len([m for m in st.session_state.chat_history if m['role'] == 'user'])}")
with col_status3:
    st.caption(f"🧠 模型：{LLM_MODEL} | Embedding: text-embedding-v2")
