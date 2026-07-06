"""
Day 11 - RAG 核心闭环：语义检索 + 上下文拼接 + LLM 生成
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Day 8-10 我们分别搞定了 RAG 的概念、文档加载切割、Embedding + Chroma。
今天把最后一步「生成」串进来，跑通完整的 RAG 问答闭环。

学完今天你会：
  ✅ 掌握 RAG Prompt 的设计精髓
  ✅ 理解上下文窗口管理（token 预算分配）
  ✅ 实现带来源引用的 RAG 回答
  ✅ 对比 RAG 开启/关闭的回答差异
  ✅ 流式 RAG 回答（打字机效果 + 来源标注）
  ✅ 封装完整的 RAG 问答引擎
"""

import sys, os
sys.stdout.reconfigure(encoding='utf-8')

import time
import math
import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader, PyPDFLoader
import glob as glob_module

from config import client as llm_client, MODEL as LLM_MODEL

# ============================================================
# 实验 1：理解 RAG 的「生成」环节 —— 它到底在做什么？
# ============================================================
print("=" * 60)
print("实验 1：RAG 生成环节的本质")
print("=" * 60)
print("""
RAG 的五个步骤回顾：
  ① Load     → 加载文档
  ② Split    → 切割成 chunk
  ③ Embed    → 向量化
  ④ Store    → 存入 Chroma
  ⑤ Retrieve + Generate → 检索 + 生成 ← 今天是这个！

「生成」环节做什么？
  1. 用户提问 → Embedding → 向量检索 → 拿到 Top-K 相关 chunk
  2. 把检索到的 chunk 拼接成「上下文」
  3. 设计 RAG Prompt：系统指令 + 上下文 + 用户问题
  4. 调用 LLM，让它「基于上下文」回答
  5. 输出答案 + 标注引用了哪些来源

关键认知：
  ┌─────────────────────────────────────────────────────┐
  │  RAG 的核心不是「检索」，而是「用检索结果约束生成」 │
  │  让 LLM 只在你提供的资料范围内回答，减少幻觉       │
  └─────────────────────────────────────────────────────┘
""")


# ============================================================
# 实验 2：RAG Prompt 工程设计 —— 这是 RAG 质量的灵魂
# ============================================================
print("=" * 60)
print("实验 2：RAG Prompt 工程设计")
print("=" * 60)
print("""
RAG Prompt 不是简单地把检索结果塞进去。好的 RAG Prompt 需要：

  ① 角色设定：告诉 LLM 它是什么角色
  ② 行为约束：只能基于资料回答，不知道就说不知道
  ③ 上下文区：清晰标注哪些是参考资料
  ④ 问题区：用户的问题
  ⑤ 格式要求：怎么组织答案、要不要引用来源

下面对比三种 Prompt 模板的质量差异：
""")

# ── 2.1 三种 Prompt 模板对比 ──
print("─" * 40)
print("2.1 三种 RAG Prompt 模板对比")
print("─" * 40)

# 模拟检索结果
sample_contexts = [
    "RAG（检索增强生成）是 2026 年最核心的 AI 应用形态。它结合了信息检索和大语言模型生成两大能力。",
    "RAG 解决了 LLM 的两个根本问题：知识截止日期（不知道训练数据之后的事）和幻觉问题（没有依据时编造答案）。",
    "RAG 的五个步骤：Load（加载文档）→ Split（切割）→ Embed（向量化）→ Store（存储）→ Retrieve+Generate（检索+生成）。",
]

# 模板 A：简陋版（初学者常写的）
prompt_basic = f"""参考资料：
{' '.join(sample_contexts)}
问题：什么是 RAG？它为什么重要？
请回答。"""

print("""
  【模板 A — 简陋版】
  ─────────────────
  问题：
    - 没有角色设定，LLM 可能偏离资料
    - 没有约束，LLM 可能混合自己的知识和资料
    - 上下文和问题混在一起，边界模糊
    - 没有格式要求，输出质量不可控

  示例 Prompt：
""")
for line in prompt_basic.split("\n"):
    print(f"    {line}")

# 模板 B：标准版（工程可用）
prompt_standard = """你是一个专业的技术问答助手。请严格根据以下参考资料回答问题。

【参考资料】
---
[资料1] RAG（检索增强生成）是 2026 年最核心的 AI 应用形态。它结合了信息检索和大语言模型生成两大能力。
[资料2] RAG 解决了 LLM 的两个根本问题：知识截止日期（不知道训练数据之后的事）和幻觉问题（没有依据时编造答案）。
[资料3] RAG 的五个步骤：Load（加载文档）→ Split（切割）→ Embed（向量化）→ Store（存储）→ Retrieve+Generate（检索+生成）。
---

【问题】什么是 RAG？它为什么重要？

【要求】
- 基于参考资料回答，不要引入外部知识
- 如果资料不足，请明确指出
- 中文回答，结构清晰"""

print("""
  【模板 B — 标准版】
  ─────────────────
  改进点：
    ✅ 有角色设定（专业的技术问答助手）
    ✅ 明确约束（严格根据参考资料）
    ✅ 上下文用分隔符标记，编号清晰
    ✅ 有格式和行为要求

  示例 Prompt：
""")
for line in prompt_standard.split("\n"):
    print(f"    {line}")

# 模板 C：进阶版（生产级）
prompt_advanced = """# 系统指令
你是一个严谨的 AI 知识库助手。你的回答必须可追溯、有依据。

# 核心规则
1. **仅基于参考资料**：只使用下方「参考资料」中提供的信息
2. **诚实面对未知**：如果资料不足以回答问题，直接说明「知识库中没有相关信息」
3. **必须引用来源**：每个关键信息点都要标注来自哪份资料（如 [资料1]）
4. **不可编造**：即使你知道答案，如果资料里没有，也不能说

# 参考资料
────────────────────────────────────────
[资料1]（来源：ai_knowledge_base.txt）
RAG（检索增强生成）是 2026 年最核心的 AI 应用形态。它结合了信息检索和大语言模型生成两
大能力。

[资料2]（来源：ai_knowledge_base.txt）
RAG 解决了 LLM 的两个根本问题：知识截止日期（不知道训练数据之后的事）和幻觉问题（没有
依据时编造答案）。

[资料3]（来源：ai_knowledge_base.txt）
RAG 的五个步骤：Load（加载文档）→ Split（切割）→ Embed（向量化）→ Store（存储）→
Retrieve+Generate（检索+生成）。
────────────────────────────────────────

# 用户问题
什么是 RAG？它为什么重要？

# 回答格式
请用以下结构组织回答：
## 定义
（用 1-2 句话定义 RAG）
## 为什么重要
（列出核心价值点，每条标注来源）
## 工作流程
（简述五个步骤）
## 参考资料
（列出实际使用的资料编号）"""

print("""
  【模板 C — 进阶版（生产级）】
  ────────────────────────────
  改进点：
    ✅ Markdown 格式的系统指令，结构分明
    ✅ 核心规则用加粗突出
    ✅ 每条资料标注来源文件
    ✅ 规定输出格式（定义→重要性→流程→参考）
    ✅ 要求引用标注，可追溯

  这才是面试官想看到的 RAG Prompt 设计能力。
""")


# ============================================================
# 实验 3：构建知识库（复用 Day 10 的成果）
# ============================================================
print("=" * 60)
print("实验 3：准备知识库")
print("=" * 60)

# 复用 Day 9 文档加载
def load_and_split_directory(
    directory: str,
    chunk_size: int = 400,
    chunk_overlap: int = 50,
) -> list[dict]:
    """加载目录下所有文档，切割成 chunk"""
    all_documents = []

    txt_files = glob_module.glob(f"{directory}/**/*.txt", recursive=True)
    for f in txt_files:
        try:
            loader = TextLoader(f, encoding="utf-8")
            all_documents.extend(loader.load())
        except Exception as e:
            print(f"  ⚠️ TXT 加载失败 {f}: {e}")

    pdf_files = glob_module.glob(f"{directory}/**/*.pdf", recursive=True)
    for f in pdf_files:
        try:
            loader = PyPDFLoader(f)
            all_documents.extend(loader.load())
        except Exception as e:
            print(f"  ⚠️ PDF 加载失败 {f}: {e}")

    if not all_documents:
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", ".", "，", ",", " ", ""],
    )
    all_chunks = splitter.split_documents(all_documents)
    return [
        {"text": c.page_content, "source": c.metadata.get("source", "unknown"), "page": c.metadata.get("page")}
        for c in all_chunks
    ]


# 初始化 Chroma + 入库
CHROMA_PATH = "./chroma_db/day11_kb"
import shutil
if os.path.exists(CHROMA_PATH):
    shutil.rmtree(CHROMA_PATH)

chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = chroma_client.create_collection(
    name="rag_demo",
    metadata={"description": "Day 11 RAG 完整闭环", "chunk_size": "400", "embedding_model": "text-embedding-v2"},
)

print("\n📥 加载 data/ 目录...")
chunks = load_and_split_directory("data", chunk_size=400, chunk_overlap=60)

if not chunks:
    sample_docs = [
        {"text": "RAG 是检索增强生成的缩写，结合了信息检索和 LLM 生成两大能力，是 2026 年最核心的 AI 应用形态。", "source": "sample", "page": None},
        {"text": "LLM 的核心能力是预测下一个 token。Token 是处理文本的最小单位，中文通常 1-2 字符 = 1 token。", "source": "sample", "page": None},
        {"text": "Prompt 工程是设计输入文本以引导 LLM 产生期望输出的技术。System Prompt 是最有效的控制手段。", "source": "sample", "page": None},
        {"text": "Temperature 控制输出的随机性。0.0-0.3 适合代码生成，0.5-0.8 适合对话，1.0-1.5 适合创意写作。", "source": "sample", "page": None},
        {"text": "AI Agent 是能自主使用工具、规划多步骤任务、反思执行结果的 AI 系统。核心循环：Planning → Tool Use → Reflection。", "source": "sample", "page": None},
        {"text": "Function Calling 是 LLM 调用外部工具的标准方式。定义函数名称、描述和参数 schema，LLM 自主决定调用。", "source": "sample", "page": None},
        {"text": "Streamlit 是纯 Python 的 Web 应用框架，零前端基础构建 AI 应用界面。核心组件：title、text_area、button、spinner 等。", "source": "sample", "page": None},
    ]
    chunks = sample_docs
    print(f"  ⚠️ 未找到文档，使用内置示例 ({len(chunks)} 条)")

print(f"  ✅ 共 {len(chunks)} 个 chunk\n")

# 批量向量化
BATCH_SIZE = 20
all_embeddings = []
for i in range(0, len(chunks), BATCH_SIZE):
    batch = chunks[i : i + BATCH_SIZE]
    resp = llm_client.embeddings.create(model="text-embedding-v2", input=[c["text"] for c in batch])
    all_embeddings.extend([d.embedding for d in resp.data])
    print(f"  向量化进度：{min(i + BATCH_SIZE, len(chunks))}/{len(chunks)}")

# 存入 Chroma
for i, (chunk, emb) in enumerate(zip(chunks, all_embeddings)):
    collection.add(
        ids=[f"c_{i:04d}"],
        embeddings=[emb],
        documents=[chunk["text"]],
        metadatas=[{"source": os.path.basename(chunk["source"]), "page": chunk["page"] or -1}],
    )

print(f"\n  📊 知识库就绪：{collection.count()} 条记录\n")


# ============================================================
# 实验 4：完整 RAG 引擎 —— 这才是面试要写的代码
# ============================================================
print("=" * 60)
print("实验 4：完整 RAG 引擎 —— 可复用、有引用、能对比")
print("=" * 60)

class RAGEngine:
    """
    RAG 问答引擎 —— Day 11 核心产出

    设计原则：
      1. 检索和生成解耦（可以单独调试检索质量）
      2. 支持多轮 Prompt 策略（可切换模板）
      3. 必须返回来源引用（可追溯 = 可信赖）
      4. 支持流式和非流式两种输出
      5. 内置对比功能（RAG vs 纯 LLM）

    用法：
      engine = RAGEngine(collection)
      answer, sources = engine.ask("什么是 RAG？")
      engine.compare("什么是 RAG？")  # 对比 RAG 开启/关闭
    """

    def __init__(self, collection, model: str = None):
        """
        参数：
          collection : Chroma collection 对象
          model      : LLM 模型名，默认用全局配置
        """
        self.collection = collection
        self.model = model or LLM_MODEL
        self._search_cache = {}  # 用于调试检索质量

    # ── 检索 ────────────────────────────────────────────
    def retrieve(self, query: str, top_k: int = 5, min_similarity: float = 0.0) -> list[dict]:
        """
        语义检索：查询 → 向量化 → Chroma 搜索

        Chroma 默认使用 L2 距离（欧氏距离），值越小越相似。
        我们用 1/(1+distance) 把距离映射到 (0, 1] 的相似度，方便理解和过滤。

        返回：[{"text", "source", "page", "similarity", "distance", "index"}, ...]
        """
        q_emb = llm_client.embeddings.create(
            model="text-embedding-v2", input=query
        ).data[0].embedding

        raw = self.collection.query(query_embeddings=[q_emb], n_results=top_k)

        results = []
        for i, (doc, meta, dist) in enumerate(zip(
            raw["documents"][0], raw["metadatas"][0], raw["distances"][0]
        )):
            # L2 距离 → 相似度映射（0=完全不相关, 1=完全相同）
            # 距离为 0 时相似度=1；距离越大相似度越趋近 0
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

        self._search_cache[query] = results
        return results

    # ── 上下文拼接 ──────────────────────────────────────
    def _build_context(self, sources: list[dict]) -> str:
        """
        把检索到的 chunk 拼接成结构化的上下文。

        策略：
          - 每条资料编号 [资料1] [资料2] ...
          - 标注来源文件和页码
          - 用分隔符包裹，和用户问题在视觉上隔离
        """
        parts = []
        for s in sources:
            header = f"[资料{s['index']}]（来源：{s['source']}"
            if s["page"] >= 0:
                header += f"，第{s['page']+1}页"
            header += f"，相似度：{s['similarity']:.2f}）"
            parts.append(f"{header}\n{s['text']}")

        return "\n\n".join(parts)

    # ── Prompt 构建 ─────────────────────────────────────
    def _build_prompt(
        self,
        question: str,
        context: str,
        template: str = "standard",
    ) -> tuple[str, str]:
        """
        根据模板类型构建 System Prompt 和 User Prompt。

        template 可选：
          "basic"    - 简陋版（对比用）
          "standard" - 标准版（推荐日常使用）
          "strict"   - 严格版（回答 + 必须引用格式）
        """
        if template == "basic":
            system = "你是一个有帮助的助手。"
            user = f"参考资料：\n{context}\n\n问题：{question}\n请根据资料回答。"
            return system, user

        elif template == "strict":
            system = (
                "你是一个严谨的知识库问答助手。你的回答必须基于提供的资料，"
                "不能使用外部知识。如果资料不足以回答问题，必须明确说明。"
                "每个关键信息点用 [资料N] 标注来源。"
            )
            user = (
                f"【参考资料】\n---\n{context}\n---\n\n"
                f"【问题】{question}\n\n"
                f"【回答要求】\n"
                f"1. 仅基于上述资料回答\n"
                f"2. 引用时标注 [资料N]\n"
                f"3. 如果资料不充分，说明「知识库中没有相关信息」\n"
                f"4. 中文回答，条理清晰"
            )
            return system, user

        else:  # standard（默认）
            system = (
                "你是一个专业的 AI 知识库助手。请严格根据提供的参考资料回答问题。"
                "资料中没有的信息，请如实说明「知识库中暂无相关记录」。"
                "回答时请引用资料编号。"
            )
            user = (
                f"【参考资料】\n"
                f"{'─' * 50}\n"
                f"{context}\n"
                f"{'─' * 50}\n\n"
                f"【用户问题】{question}\n\n"
                f"请基于以上资料给出准确、有条理的回答。重要信息需标注来源编号。"
            )
            return system, user

    # ── LLM 生成（非流式）───────────────────────────────
    def generate(
        self,
        question: str,
        sources: list[dict],
        template: str = "standard",
        temperature: float = 0.3,
    ) -> str:
        """基于检索结果调用 LLM 生成答案"""
        if not sources:
            return "⚠️ 未检索到相关内容，无法生成 RAG 回答。"

        context = self._build_context(sources)
        system, user = self._build_prompt(question, context, template)

        r = llm_client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
        )
        return r.choices[0].message.content

    # ── 一站式 RAG 问答 ────────────────────────────────
    def ask(
        self,
        question: str,
        top_k: int = 5,
        template: str = "standard",
        temperature: float = 0.3,
    ) -> tuple[str, list[dict]]:
        """
        RAG 问答一站式接口

        参数：
          question    : 用户问题
          top_k       : 检索多少段资料
          template    : Prompt 模板（basic/standard/strict）
          temperature : LLM 温度

        返回：
          (答案文本, [引用来源列表])
        """
        sources = self.retrieve(question, top_k=top_k, min_similarity=0.2)
        answer = self.generate(question, sources, template=template, temperature=temperature)
        return answer, sources

    # ── 流式 RAG 问答 ──────────────────────────────────
    def ask_stream(self, question: str, top_k: int = 5, template: str = "standard"):
        """
        RAG 流式问答 —— 打字机效果输出

        先展示检索结果，再流式输出 LLM 生成的答案。
        返回生成器，逐 token yield。
        """
        # 1. 检索
        sources = self.retrieve(question, top_k=top_k, min_similarity=0.2)
        yield ("search_done", sources)

        if not sources:
            yield ("token", "⚠️ 未检索到相关内容，无法生成 RAG 回答。")
            yield ("done", [])
            return

        # 2. 构建 Prompt
        context = self._build_context(sources)
        system, user = self._build_prompt(question, context, template)

        # 3. 流式生成
        stream = llm_client.chat.completions.create(
            model=self.model,
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

        yield ("done", sources)

    # ── RAG vs 非 RAG 对比 ─────────────────────────────
    def compare(self, question: str, top_k: int = 5) -> dict:
        """
        对比 RAG 和非 RAG 的回答差异 —— 展示 RAG 的价值

        返回：{"rag_answer": ..., "rag_sources": ..., "direct_answer": ...}
        """
        print(f"\n{'='*50}")
        print(f"🆚 RAG vs 非 RAG 对比实验")
        print(f"{'='*50}")
        print(f"  问题：{question}\n")

        # RAG 回答
        print("  🔍 [RAG 模式] 检索中...")
        t0 = time.time()
        rag_answer, rag_sources = self.ask(question, top_k=top_k)
        rag_time = time.time() - t0

        # 纯 LLM 回答
        print("  🤖 [非 RAG 模式] 直接问 LLM...")
        t0 = time.time()
        r = llm_client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一个有帮助的AI助手。"},
                {"role": "user", "content": question},
            ],
            temperature=0.5,
        )
        direct_answer = r.choices[0].message.content
        direct_time = time.time() - t0

        print(f"\n  ⏱️  RAG 耗时: {rag_time:.1f}s | 非 RAG 耗时: {direct_time:.1f}s")

        return {
            "rag_answer": rag_answer,
            "rag_sources": rag_sources,
            "direct_answer": direct_answer,
            "rag_time": rag_time,
            "direct_time": direct_time,
        }

    # ── 统计信息 ────────────────────────────────────────
    def stats(self) -> dict:
        """知识库统计"""
        count = self.collection.count()
        if count == 0:
            return {"total": 0, "sources": {}}

        all_data = self.collection.get()
        sources = {}
        for meta in all_data["metadatas"]:
            src = meta.get("source", "unknown")
            sources[src] = sources.get(src, 0) + 1
        return {"total": count, "sources": sources}


# ── 初始化引擎 ──
print("\n🔧 初始化 RAG 引擎...")
engine = RAGEngine(collection)
stats = engine.stats()
print(f"  ✅ 知识库：{stats['total']} 条记录，来源：{list(stats['sources'].keys())}\n")


# ============================================================
# 实验 5：RAG 问答实测 —— 三大场景
# ============================================================
print("=" * 60)
print("实验 5：RAG 问答实测")
print("=" * 60)

test_cases = [
    # 场景 1：知识库中有明确答案
    {
        "name": "场景1：知识库覆盖的问题",
        "question": "什么是 RAG？有哪些步骤？",
        "expected": "应该从知识库中检索到 RAG 的定义和五个步骤",
    },
    # 场景 2：知识库中只有部分相关
    {
        "name": "场景2：部分相关的问题",
        "question": "Streamlit 和 LangChain 分别适合做什么？如何配合使用？",
        "expected": "知识库有 Streamlit 信息，LangChain 配合的部分可能需要 LLM 补充",
    },
    # 场景 3：知识库中没有的信息
    {
        "name": "场景3：知识库外的问题",
        "question": "2026 年 NBA 总决赛冠军是谁？",
        "expected": "知识库中无此信息，RAG 应该诚实说明",
    },
]

for tc in test_cases:
    print(f"\n{'─'*50}")
    print(f"📋 {tc['name']}")
    print(f"   问题：{tc['question']}")
    print(f"   期望：{tc['expected']}")
    print(f"{'─'*50}")

    # 先看检索结果
    sources = engine.retrieve(tc["question"], top_k=3)
    print(f"\n  🔍 检索到 {len(sources)} 条相关资料：")
    for s in sources:
        preview = s["text"].replace("\n", " ")[:80]
        print(f"    [{s['index']}] 相似度 {s['similarity']:.3f} | {s['source']}")
        print(f"        \"{preview}...\"")

    # RAG 回答
    answer, _ = engine.ask(tc["question"], top_k=3)
    print(f"\n  📝 RAG 回答：")
    for line in answer.split("\n"):
        print(f"    {line}")

    print()


# ============================================================
# 实验 6：RAG vs 非 RAG 对比 —— 证明 RAG 的价值
# ============================================================
print("=" * 60)
print("实验 6：RAG vs 纯 LLM 对比")
print("=" * 60)
print("""
这是 RAG 最有说服力的展示方式。同一个问题，分别用：
  - 纯 LLM（不提供资料）
  - RAG（检索知识库后回答）

对比两者的回答质量、可追溯性、幻觉程度。
""")

comparison_questions = [
    "RAG 系统包含哪些步骤？每个步骤做什么？",
    "如何设计一个好的 System Prompt？",
]

for q in comparison_questions:
    result = engine.compare(q, top_k=4)

    print(f"\n{'─'*50}")
    print(f"📝 非 RAG 回答（纯 LLM 知识）：")
    print(f"{'─'*50}")
    for line in result["direct_answer"].split("\n"):
        print(f"  {line}")

    print(f"\n{'─'*50}")
    print(f"📝 RAG 回答（基于知识库）：")
    print(f"{'─'*50}")
    for line in result["rag_answer"].split("\n"):
        print(f"  {line}")
    print(f"\n  📎 基于 {len(result['rag_sources'])} 段知识库资料")

    print(f"\n  ⚡ 性能：RAG {result['rag_time']:.1f}s vs 非RAG {result['direct_time']:.1f}s")


# ============================================================
# 实验 7：流式 RAG 输出 —— 用户体验升级
# ============================================================
print("\n" + "=" * 60)
print("实验 7：流式 RAG 输出")
print("=" * 60)
print("""
流式 RAG 的体验：
  1. 先把检索到的来源展示出来（瞬间响应）
  2. LLM 生成的答案逐字出现在屏幕上（打字机效果）
  3. 用户等待时间感知大幅缩短
""")

demo_question = "Token 和 Temperature 是什么？怎么设置？"

print(f"\n  演示问题：{demo_question}")
print(f"\n  🔍 检索结果：")

for event_type, data in engine.ask_stream(demo_question, top_k=3):
    if event_type == "search_done":
        sources = data
        for s in sources:
            print(f"    [{s['index']}] 相似度 {s['similarity']:.3f} | {s['source']}")
        print(f"\n  📝 生成中：", end="", flush=True)

    elif event_type == "token":
        print(data, end="", flush=True)

    elif event_type == "done":
        sources = data
        if sources:
            print(f"\n\n  📎 本次回答基于 {len(sources)} 段知识库资料")
        print()


# ============================================================
# 实验 8：Prompt 模板对比 —— 同一个问题，不同 Prompt 质量
# ============================================================
print("=" * 60)
print("实验 8：Prompt 模板质量对比")
print("=" * 60)
print("""
同一个问题，用三种 Prompt 模板分别回答，直观看到设计差异。
""")

template_test_q = "AI Agent 的核心循环是什么？它怎么调用外部工具？"

for tmpl in ["basic", "standard", "strict"]:
    template_names = {"basic": "简陋版", "standard": "标准版", "strict": "严格版"}
    print(f"\n{'─'*40}")
    print(f"📋 模板：{template_names[tmpl]}（{tmpl}）")
    print(f"{'─'*40}")

    answer, sources = engine.ask(template_test_q, top_k=3, template=tmpl)
    for line in answer.split("\n"):
        print(f"  {line}")
    print()

print("""
  📌 观察：
    - 简陋版：可能混合外部知识，不加引用
    - 标准版：基于资料回答，结构较好
    - 严格版：每个信息点标注来源，诚实面对未知

  面试官如果让你设计 RAG Prompt，直接选「严格版」的思路。
""")


# ============================================================
# 实验 9：交互式 RAG 对话 —— 你自己的 ChatGPT + 知识库
# ============================================================
print("=" * 60)
print("实验 9：交互式 RAG 对话")
print("=" * 60)
print("""
你的私有知识库问答系统已就绪！

  知识库内容：
    - AI 应用开发知识库：LLM / Prompt / RAG / Agent / Streamlit / 部署
    - AI 入门指南（PDF）

  试试这些：
    🎯 "什么是 RAG？怎么实现？"
    🎯 "Prompt 工程的核心技巧有哪些？"
    🎯 "Streamlit 有哪些常用组件？"
    🎯 "API 调用出错怎么处理？"
    🎯 "Agent 和普通 LLM 有什么区别？"
    🎯 "如何部署一个 AI 应用？"

  特殊命令：
    :compare <问题>  → 对比 RAG vs 纯 LLM
    :search <关键词> → 只看检索结果
    quit / q / 退出  → 结束
""")

while True:
    try:
        raw = input("\n🙋 你的问题：").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n👋 再见！")
        break

    if not raw:
        continue
    if raw.lower() in ("quit", "q", "退出", "exit"):
        print("👋 再见！")
        break

    # 特殊命令：对比模式
    if raw.startswith(":compare"):
        q = raw[len(":compare"):].strip()
        if not q:
            q = "什么是 RAG？"
        engine.compare(q, top_k=4)
        continue

    # 特殊命令：仅检索
    if raw.startswith(":search"):
        q = raw[len(":search"):].strip()
        if not q:
            print("  ⚠️ 请输入搜索关键词")
            continue
        results = engine.retrieve(q, top_k=5)
        if not results:
            print("  ⚠️ 未找到相关内容")
        else:
            print(f"\n  🔍 {len(results)} 条结果：")
            for r in results:
                print(f"  [{r['index']}] 相似度 {r['similarity']:.3f} | {r['source']}")
                print(f"      {r['text'][:100]}...")
        continue

    # 正常 RAG 问答（流式）
    print(f"\n🔍 检索中...")
    for event_type, data in engine.ask_stream(raw, top_k=4):
        if event_type == "search_done":
            if not data:
                print("  ⚠️ 未找到相关内容，直接问 LLM...")
                r = llm_client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=[
                        {"role": "system", "content": "你是一个有帮助的AI助手。"},
                        {"role": "user", "content": raw},
                    ],
                    temperature=0.5,
                )
                print(f"\n📝 {r.choices[0].message.content}")
                print("\n  (以上回答来自 LLM 通用知识，不在知识库中)")
                break

            sources = data
            print(f"  找到 {len(sources)} 条相关资料：")
            for s in sources:
                print(f"    [{s['index']}] 相似度 {s['similarity']:.3f} | {s['source']}")

            if sources[0]["similarity"] < 0.4:
                print(f"  ⚠️ 最佳匹配相似度仅 {sources[0]['similarity']:.3f}，结果可能不准确")

            print(f"\n📝 生成中：", end="", flush=True)

        elif event_type == "token":
            print(data, end="", flush=True)

        elif event_type == "done":
            print(f"\n\n  📎 本次回答基于 {len(data)} 段知识库资料")
            print()


# ============================================================
# Day 11 总结
# ============================================================
print(f"""
╔══════════════════════════════════════════════════════════════════╗
║                      📝 Day 11 总结                              ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  今天你跑通了 RAG 的完整闭环：                                    ║
║                                                                  ║
║  ① RAG Prompt 工程 —— 简陋版 → 标准版 → 严格版                   ║
║  ② 上下文拼接策略 —— 编号 + 来源标注 + 分隔符                     ║
║  ③ RAGEngine 类 —— 检索/生成/流式/对比，四大功能                  ║
║  ④ 流式 RAG 输出 —— 打字机效果 + 来源即时展示                     ║
║  ⑤ RAG vs 非 RAG 对比 —— 直观展示 RAG 的价值                     ║
║                                                                  ║
║  🔑 三个关键认知：                                                ║
║  1. RAG 的灵魂不在检索，在于「用检索结果约束 LLM 生成」            ║
║  2. Prompt 模板设计是 RAG 质量的倍增器（模板 C > B >> A）         ║
║  3. 来源引用让 AI 回答从「黑箱」变成「可追溯」—— 这是信任的基础  ║
║                                                                  ║
║  🎯 你现在的能力：                                                ║
║  - 能写出面试官认可的 RAG Prompt 模板                             ║
║  - 实现了完整 RAG 引擎（检索 + 生成 + 流式 + 对比）               ║
║  - 理解 RAG 比纯 LLM 好在哪里（能说出 3 个理由）                  ║
║  - 拥有可复用的 RAGEngine 类                                     ║
║                                                                  ║
║  🔜 Day 12 预告：RAG 检索质量调优                                 ║
║  调整 chunk_size / overlap / 相似度阈值                           ║
║  对比不同参数下的检索命中率和答案质量                              ║
║  建立检索质量的评估方法                                            ║
║                                                                  ║
║  📊 学习进度：Week 2 ████████░░ 67%                               ║
║  已完成：Day 1─11 / 30    今天：RAG 核心闭环 ✅                    ║
╚══════════════════════════════════════════════════════════════════╝
""")
