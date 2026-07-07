"""
Day 10 - 向量嵌入（Embedding）深入 + Chroma 持久化存储
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Day 9 我们把文档加载并切割成了 chunk。
今天把这些 chunk → Embedding 向量 → 存入 Chroma（持久化），
跑通「文档 → 向量 → 检索」完整链路。

学完今天你会：
  ✅ 深入理解 Embedding：向量维度、相似度计算
  ✅ Chroma 持久化模式：数据存磁盘，重启不丢失
  ✅ 完整入库管线：加载 → 切割 → 向量化 → 存储
  ✅ 语义检索：搜索你的真实文档
  ✅ 封装一个可复用的 VectorStore 类
"""

import sys, os
sys.stdout.reconfigure(encoding='utf-8')

import numpy as np
import chromadb
from chromadb.config import Settings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader, PyPDFLoader

from config import client as llm_client, MODEL as LLM_MODEL

# ============================================================
# 实验 1：深入理解 Embedding —— 向量到底是什么？
# ============================================================
print("=" * 60)
print("实验 1：深入理解 Embedding")
print("=" * 60)
print("""
Embedding 的本质：
  把一段文字映射成一组固定维度的数字（向量）。
  语义相近的文字 → 向量在空间中距离近。
  语义不同的文字 → 向量在空间中距离远。

这相当于给每段文字找到了一个「坐标」——
  "Python 编程" 和 "写 Python 代码" 的坐标很接近
  "Python 编程" 和 "今天天气" 的坐标很远

关键概念：
  - 维度（dimension）：向量的长度。百炼 text-embedding-v2 是 1536 维
  - 每个维度没有人类可读的含义，但对模型来说编码了语义信息
  - 向量相似度的常用度量：余弦相似度（cosine similarity）
""")

# ── 1.1 准备一组测试文本 ──
print("─" * 40)
print("1.1 准备测试文本")
print("─" * 40)

test_texts = [
    "Python 是一门强大的编程语言",
    "Python 适合做数据分析和 AI 开发",
    "今天天气真好，适合出去散步",
    "Django 是一个 Python Web 框架",
    "机器学习需要大量的训练数据",
]

for i, t in enumerate(test_texts):
    print(f"  文本 {i+1}：{t}")

# ── 1.2 调用 Embedding API ──
print("\n─" * 10)
print("1.2 调用百炼 Embedding API")
print("─" * 40)

print(f"正在向量化 {len(test_texts)} 条文本...", end=" ", flush=True)
resp = llm_client.embeddings.create(
    model="text-embedding-v2",
    input=test_texts,
)
embeddings = [d.embedding for d in resp.data]

print("完成！")
print(f"  每条文本 → {len(embeddings[0])} 维向量")
print(f"  文本 1 的前 5 维：{[round(v, 4) for v in embeddings[0][:5]]}")
print(f"  文本 2 的前 5 维：{[round(v, 4) for v in embeddings[1][:5]]}")
print(f"  文本 3 的前 5 维：{[round(v, 4) for v in embeddings[2][:5]]}")

# ── 1.3 计算余弦相似度 ──
print("\n─" * 10)
print("1.3 计算余弦相似度 —— 核心概念")
print("─" * 40)
print("""
余弦相似度公式：similarity = cos(θ) = (A·B) / (|A| × |B|)

  值域：[-1, 1]
    1.0  = 方向完全一致（语义几乎相同）
    0.0  = 完全不相关（正交）
   -1.0  = 方向完全相反（语义对立）

  实践中 Embedding 向量的相似度通常在 0.3~0.9 之间。
""")

def cosine_similarity(a: list[float], b: list[float]) -> float:
    """计算两个向量的余弦相似度"""
    a_arr = np.array(a)
    b_arr = np.array(b)
    return float(np.dot(a_arr, b_arr) / (np.linalg.norm(a_arr) * np.linalg.norm(b_arr)))

# 构建相似度矩阵
print("\n  余弦相似度矩阵（5 条文本 × 5 条文本）：")
print(f"  {'':>6}", end="")
for i in range(len(test_texts)):
    print(f"{'文本'+str(i+1):>10}", end="")
print()

for i in range(len(test_texts)):
    print(f"  {'文本'+str(i+1):>6}", end="")
    for j in range(len(test_texts)):
        sim = cosine_similarity(embeddings[i], embeddings[j])
        print(f"{sim:>10.4f}", end="")
    print()

print("""
  📌 观察：
    - 文本1「Python 编程语言」和文本2「Python 数据分析」→ 相似度高（都关于 Python）
    - 文本1「Python 编程语言」和文本3「天气真好」→ 相似度低（完全不同话题）
    - 文本1「Python 编程语言」和文本4「Django Web 框架」→ 相似度中等（都关于编程）
    - 对角线上（自己和自己的相似度）= 1.0

  这就是语义搜索的数学基础！
""")


# ============================================================
# 实验 2：Chroma 两种模式 —— 内存 vs 持久化
# ============================================================
print("=" * 60)
print("实验 2：Chroma 两种模式对比")
print("=" * 60)
print("""
Chroma 支持两种存储模式：

  内存模式（Day 8 用过的）：
    client = chromadb.Client()
    → 数据只在内存中，程序结束就没了
    → 适合：学习、调试、临时实验

  持久化模式（今天重点）：
    client = chromadb.PersistentClient(path="./chroma_db")
    → 数据存到磁盘，重启后依然在
    → 适合：实际项目、生产环境
    → 底层使用 SQLite3 存储元数据 + 文件系统存储向量
""")

# ── 2.1 演示持久化存储 ──
print("─" * 40)
print("2.1 创建持久化 Chroma 并存入数据")
print("─" * 40)

CHROMA_PATH = "./chroma_db"

# 只清理实验 2 用到的 demo collection，不动其他数据
# ❌ 不要 shutil.rmtree(CHROMA_PATH) —— 那样会把后面实验的知识库也删掉！
persistent_client_temp = chromadb.PersistentClient(path=CHROMA_PATH)
try:
    persistent_client_temp.delete_collection("demo_kb")
    print(f"  已清理旧的 demo_kb collection（不影响其他数据）")
except:
    pass  # 第一次运行没有这个 collection，忽略错误
del persistent_client_temp

# 创建持久化客户端
persistent_client = chromadb.PersistentClient(path=CHROMA_PATH)
print(f"  持久化数据库路径：{os.path.abspath(CHROMA_PATH)}")

# 创建 collection
try:
    persistent_client.delete_collection("demo_kb")
except:
    pass

collection = persistent_client.create_collection(
    name="demo_kb",
    metadata={
        "description": "Demo 知识库 - Day 10",
        "embedding_model": "text-embedding-v2",
        "created_by": "day10_embedding_chroma.py",
    },
)

# 存入测试数据
print("\n  存入 5 条文本到持久化 Chroma...")
for i, (text, emb) in enumerate(zip(test_texts, embeddings)):
    collection.add(
        ids=[f"text_{i+1}"],
        embeddings=[emb],
        documents=[text],
        metadatas=[{"index": i, "category": "demo"}],
    )

print(f"  ✅ 已存入 {collection.count()} 条记录")
print(f"  Collection 名称：{collection.name}")

# ── 2.2 验证持久化：关闭再打开 ──
print("\n─" * 10)
print("2.2 验证持久化 —— 关闭客户端再重新打开")
print("─" * 40)

# 模拟"程序重启"：关闭当前客户端，创建新的
# 注意：Python 的 chromadb 没有显式的 close()，我们直接创建新客户端来模拟
del persistent_client  # 释放旧的客户端引用

# 重新打开
reopened_client = chromadb.PersistentClient(path=CHROMA_PATH)
reopened_collection = reopened_client.get_collection("demo_kb")

print(f"  重新打开后，Collection 中仍有 {reopened_collection.count()} 条记录")
print(f"  数据没有丢失！这就是持久化存储的价值。")

# 取一条数据验证
sample = reopened_collection.get(ids=["text_1"])
print(f"\n  取出 text_1 验证：{sample['documents'][0][:50]}...")

print("""
  📌 持久化 vs 内存模式：
    - 持久化：适合实际项目，重启后数据还在
    - 内存模式：适合学习和临时实验，速度稍快
    - Chroma 目前不能在同一个进程中同时使用两种模式
""")


# ============================================================
# 实验 3：完整入库管线 —— 文档 → 向量 → Chroma
# ============================================================
print("=" * 60)
print("实验 3：完整入库管线")
print("=" * 60)
print("""
前一天我们写了 load_and_split_directory() 函数。
今天把它和 Embedding + Chroma 串起来，形成完整的入库管线：

  文档目录 → 加载 → 切割 → Embedding → Chroma 持久化
""")

# 复用 Day 9 的文档加载逻辑
import glob as glob_module

def load_and_split_directory(
    directory: str,
    chunk_size: int = 400,
    chunk_overlap: int = 50,
) -> list:
    """加载目录下所有支持的文档，切割成 chunk（来自 Day 9）"""
    all_documents = []

    # 加载 TXT
    txt_files = glob_module.glob(f"{directory}/**/*.txt", recursive=True)
    for f in txt_files:
        try:
            loader = TextLoader(f, encoding="utf-8")
            all_documents.extend(loader.load())
        except Exception as e:
            print(f"  ⚠️ TXT 加载失败 {f}: {e}")

    # 加载 PDF
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

    result = []
    for chunk in all_chunks:
        result.append({
            "text": chunk.page_content,
            "source": chunk.metadata.get("source", "unknown"),
            "page": chunk.metadata.get("page", None),
        })
    return result


print("\n  正在加载 data/ 目录...")
chunks = load_and_split_directory("data", chunk_size=300, chunk_overlap=40)

if not chunks:
    print("  ⚠️ data/ 目录下没有找到文档，使用内置示例文本。")
    # 使用内置文本作为后备
    sample_docs = [
        {"text": "Python 是解释型、面向对象的高级编程语言，由 Guido van Rossum 于 1991 年发布。", "source": "sample", "page": None},
        {"text": "Django 是一个高级 Python Web 框架，遵循 MTV（Model-Template-View）架构模式。", "source": "sample", "page": None},
        {"text": "RAG（检索增强生成）是 2026 年最核心的 AI 应用形态，结合了检索和生成两大能力。", "source": "sample", "page": None},
        {"text": "Embedding 将文本映射为固定维度的向量，语义相近的文本向量距离也相近。", "source": "sample", "page": None},
    ]
    chunks = sample_docs

print(f"  ✅ 加载完成：{len(chunks)} 个 chunk\n")

# 打印 chunk 统计
sources = {}
for c in chunks:
    basename = os.path.basename(c["source"])
    sources[basename] = sources.get(basename, 0) + 1
print("  来源分布：")
for src, count in sources.items():
    print(f"    {src}: {count} 个 chunk")

total_chars = sum(len(c["text"]) for c in chunks)
print(f"\n  总字符数：{total_chars}，平均每块：{total_chars/len(chunks):.0f} 字")

# ── 3.1 批量 Embedding ──
print("\n─" * 10)
print("3.1 批量向量化所有 chunk")
print("─" * 40)

BATCH_SIZE = 20  # 百炼 API 单次上限 25 条
all_embeddings = []

print(f"  共 {len(chunks)} 个 chunk，分 { (len(chunks) + BATCH_SIZE - 1) // BATCH_SIZE } 批处理...")

for i in range(0, len(chunks), BATCH_SIZE):
    batch = chunks[i : i + BATCH_SIZE]
    batch_texts = [c["text"] for c in batch]

    resp = llm_client.embeddings.create(
        model="text-embedding-v2",
        input=batch_texts,
    )
    all_embeddings.extend([d.embedding for d in resp.data])

    progress = min(i + BATCH_SIZE, len(chunks))
    print(f"    进度：{progress}/{len(chunks)}")

print(f"\n  ✅ 向量化完成！{len(all_embeddings)} 个向量，每个 {len(all_embeddings[0])} 维")

# ── 3.2 存入 Chroma ──
print("\n─" * 10)
print("3.2 存入 Chroma 持久化数据库")
print("─" * 40)

# 创建知识库 collection（用已打开的客户端）
try:
    reopened_client.delete_collection("knowledge_base")
except:
    pass

kb_collection = reopened_client.create_collection(
    name="knowledge_base",
    metadata={
        "description": "AI 学习知识库",
        "chunk_size": "300",
        "chunk_overlap": "40",
        "embedding_model": "text-embedding-v2",
    },
)

# 逐条存入
print(f"  正在存入 {len(chunks)} 条记录...")
for i, (chunk, emb) in enumerate(zip(chunks, all_embeddings)):
    kb_collection.add(
        ids=[f"chunk_{i:04d}"],
        embeddings=[emb],
        documents=[chunk["text"]],
        metadatas=[{
            "source": os.path.basename(chunk["source"]),
            "page": chunk["page"] if chunk["page"] is not None else -1,
            "char_count": len(chunk["text"]),
        }],
    )

# 计算磁盘占用
def get_dir_size(path: str) -> float:
    """计算目录大小（MB）"""
    total = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.exists(fp):
                total += os.path.getsize(fp)
    return total / (1024 * 1024)

print(f"  ✅ 全部存入！Collection 共有 {kb_collection.count()} 条记录")
print(f"  数据库路径：{os.path.abspath(CHROMA_PATH)}")
print(f"  磁盘占用：{get_dir_size(CHROMA_PATH):.1f} MB")


# ============================================================
# 实验 4：语义检索 —— 在真实文档上搜索
# ============================================================
print("\n" + "=" * 60)
print("实验 4：语义检索 —— 在你的知识库中搜索")
print("=" * 60)
print("""
现在你的知识库已经就绪。来试试语义搜索的效果。

检索过程：
  1. 用户问题 → Embedding API → 问题向量
  2. 问题向量 → Chroma 相似度搜索 → Top-K 相关 chunk
  3. 返回 chunk 文本 + 元数据 + 相似度分数
""")

def search_knowledge_base(
    query: str,
    collection,
    n_results: int = 5,
) -> list[dict]:
    """
    在知识库中搜索与 query 最相关的 chunk。

    返回：[{"text": ..., "source": ..., "page": ..., "similarity": ...}, ...]
    """
    # 1. 向量化问题
    q_emb = llm_client.embeddings.create(
        model="text-embedding-v2",
        input=query,
    ).data[0].embedding

    # 2. Chroma 检索
    results = collection.query(
        query_embeddings=[q_emb],
        n_results=n_results,
    )

    # 3. 整理结果
    search_results = []
    for doc, meta, distance in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        search_results.append({
            "text": doc,
            "source": meta.get("source", "unknown"),
            "page": meta.get("page", -1),
            "similarity": round(1 - distance, 4),  # L2 距离 → 相似度
        })

    return search_results


# 测试搜索
test_queries = [
    "什么是 RAG？它解决什么问题？",
    "如何写好 Prompt？",
    "Streamlit 有哪些常用组件？",
    "API 调用出错了怎么处理？",
]

for query in test_queries:
    print(f"\n{'─' * 50}")
    print(f"🔍 搜索：{query}")
    print(f"{'─' * 50}")

    results = search_knowledge_base(query, kb_collection, n_results=3)

    for j, r in enumerate(results):
        source_info = f"📄 {r['source']}"
        if r["page"] >= 0:
            source_info += f" (第{r['page']+1}页)"
        print(f"  #{j+1} [相似度: {r['similarity']:.3f}] {source_info}")
        # 高亮包含关键词的片段（简单实现：显示前 100 字符）
        preview = r["text"].replace("\n", " ")[:100]
        print(f"     \"{preview}...\"")

    if results and results[0]["similarity"] < 0.5:
        print(f"  ⚠️ 最高相似度仅 {results[0]['similarity']:.3f}，知识库可能没有直接相关内容。")


# ============================================================
# 实验 5：封装可复用的 VectorStore 类
# ============================================================
print("\n" + "=" * 60)
print("实验 5：封装 VectorStore 类 —— 可复用的知识库引擎")
print("=" * 60)
print("""
把入库 + 检索封装成一个类，方便在其他项目里复用。
这就是你的「向量数据库操作层」。
""")

class VectorStore:
    """
    向量知识库引擎

    用法：
      store = VectorStore("./my_db")
      store.ingest_directory("data/", chunk_size=400)
      results = store.search("什么是 RAG？")
      answer = store.ask("什么是 RAG？")
    """

    def __init__(self, db_path: str, collection_name: str = "knowledge_base"):
        """
        初始化向量数据库

        参数：
          db_path         : Chroma 持久化路径
          collection_name : Collection 名称
        """
        self.db_path = db_path
        self.collection_name = collection_name

        # 确保目录存在
        os.makedirs(db_path, exist_ok=True)

        # 创建客户端
        self.client = chromadb.PersistentClient(path=db_path)

        # 获取或创建 collection
        try:
            self.collection = self.client.get_collection(collection_name)
            print(f"  📂 已加载现有知识库：{collection_name} ({self.collection.count()} 条记录)")
        except:
            self.collection = self.client.create_collection(
                name=collection_name,
                metadata={"description": "AI 知识库"},
            )
            print(f"  🆕 已创建新知识库：{collection_name}")

    def ingest_directory(
        self,
        directory: str,
        chunk_size: int = 400,
        chunk_overlap: int = 50,
        clear_existing: bool = False,
    ) -> int:
        """
        导入整个目录的文档到知识库

        参数：
          directory     : 文档目录路径
          chunk_size    : chunk 最大字符数
          chunk_overlap : chunk 重叠字符数
          clear_existing: 是否先清空已有数据

        返回：存入的 chunk 数量
        """
        if clear_existing:
            count_before = self.collection.count()
            # Chroma 没有直接清空的方法，需要删除再重建
            self.client.delete_collection(self.collection_name)
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "AI 知识库"},
            )
            print(f"  🗑️  已清空 {count_before} 条旧记录")
        elif self.collection.count() > 0:
            print(f"  ⏭️  知识库已有 {self.collection.count()} 条记录，跳过入库。")
            print(f"      如需强制重新入库，请使用 clear_existing=True")
            return 0

        # 1. 加载 + 切割
        chunks = load_and_split_directory(directory, chunk_size, chunk_overlap)
        if not chunks:
            print("  ⚠️ 未找到任何文档")
            return 0

        print(f"  📄 加载了 {len(chunks)} 个 chunk，正在向量化...")

        # 2. 批量 Embedding
        embeddings = []
        for i in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[i : i + BATCH_SIZE]
            batch_texts = [c["text"] for c in batch]
            resp = llm_client.embeddings.create(
                model="text-embedding-v2",
                input=batch_texts,
            )
            embeddings.extend([d.embedding for d in resp.data])

        # 3. 存入 Chroma
        # 计算起始 ID（如果不清空，追加到已有记录后面）
        start_id = 0 if clear_existing else self.collection.count()

        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            self.collection.add(
                ids=[f"chunk_{start_id + i:06d}"],
                embeddings=[emb],
                documents=[chunk["text"]],
                metadatas=[{
                    "source": os.path.basename(chunk["source"]),
                    "page": chunk["page"] if chunk["page"] is not None else -1,
                    "char_count": len(chunk["text"]),
                }],
            )

        print(f"  ✅ 入库完成！知识库总计 {self.collection.count()} 条记录")
        return len(chunks)

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float = -999.0,
    ) -> list[dict]:
        """
        语义搜索（基于 Chroma L2 距离）

        注意：Chroma 默认返回 L2 欧氏距离，不是余弦相似度。
        1536 维向量的 L2 距离通常在 0.3~2.5 之间：
          - 高度相关：distance ≈ 0.3~0.6  → similarity ≈ 0.4~0.7
          - 中度相关：distance ≈ 0.6~1.0  → similarity ≈ 0.0~0.4
          - 弱相关：  distance ≈ 1.0~1.5  → similarity ≈ -0.5~0.0
          - 不相关：  distance ≈ 1.5~2.5  → similarity ≈ -1.5~-0.5

        所以不要用 0.0 作为阈值，会误杀弱相关但仍有用的结果。

        参数：
          query          : 搜索文本
          top_k          : 返回最相似的 K 条
          min_similarity : 最低相似度阈值（L2-based，默认不过滤）

        返回：
          [{"text", "source", "page", "similarity"}, ...]
        """
        q_emb = llm_client.embeddings.create(
            model="text-embedding-v2",
            input=query,
        ).data[0].embedding

        results = self.collection.query(
            query_embeddings=[q_emb],
            n_results=top_k,
        )

        search_results = []
        for doc, meta, distance in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            similarity = 1 - distance
            if similarity >= min_similarity:
                search_results.append({
                    "text": doc,
                    "source": meta.get("source", "unknown"),
                    "page": meta.get("page", -1),
                    "similarity": round(similarity, 4),
                })

        return search_results

    def ask(
        self,
        question: str,
        top_k: int = 5,
        temperature: float = 0.3,
    ) -> tuple[str, list[dict]]:
        """
        RAG 问答：检索相关内容 → 拼接成 Prompt → LLM 生成答案

        参数：
          question    : 用户问题
          top_k       : 检索多少段相关资料
          temperature : LLM 温度参数

        返回：
          (答案文本, [引用的来源列表])
        """
        # 1. 检索
        sources = self.search(question, top_k=top_k)

        if not sources:
            return "抱歉，在知识库中没有找到相关内容。", []

        # 2. 拼接上下文
        context = "\n\n---\n\n".join([
            f"[来源：{s['source']}] {s['text']}" for s in sources
        ])

        # 3. 构造 RAG Prompt
        prompt = f"""请根据以下资料回答问题。如果资料中没有相关信息，请如实说明。

【参考资料】
{context}

【问题】
{question}

【回答要求】
- 基于上述参考资料回答
- 引用资料中的具体信息
- 中文回答，结构清晰
- 如果资料不足以回答，请明确指出"""

        # 4. 调用 LLM
        r = llm_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "你是一个严谨的AI助手，只根据提供的资料回答问题。"},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
        )

        return r.choices[0].message.content, sources

    def get_stats(self) -> dict:
        """获取知识库统计信息"""
        count = self.collection.count()
        if count == 0:
            return {"total_chunks": 0, "sources": {}, "total_chars": 0}

        # 获取全部元数据（小知识库适用，大数据集用 sample）
        all_data = self.collection.get()
        sources = {}
        total_chars = 0
        for meta, doc in zip(all_data["metadatas"], all_data["documents"]):
            src = meta.get("source", "unknown")
            sources[src] = sources.get(src, 0) + 1
            total_chars += len(doc)

        return {
            "total_chunks": count,
            "sources": sources,
            "total_chars": total_chars,
        }


# ── 测试 VectorStore ──
print("\n─" * 10)
print("测试 VectorStore 类")
print("─" * 40)
print()

# 用独立路径避免和前面的实验冲突
store = VectorStore("./chroma_db/vs_test", "test_kb")

print("\n📥 导入文档...")
# 首次运行会入库，再次运行会跳过（因为数据已存在）
added = store.ingest_directory("data", chunk_size=300, chunk_overlap=40, clear_existing=False)

print("\n📊 知识库统计：")
stats = store.get_stats()
print(f"  总 chunk 数：{stats['total_chunks']}")
print(f"  总字符数：{stats['total_chars']}")
print(f"  来源分布：")
for src, cnt in stats["sources"].items():
    print(f"    {src}: {cnt} chunks")

print("\n🔍 搜索测试：")
results = store.search("什么是 Token？", top_k=3)
for j, r in enumerate(results):
    print(f"  #{j+1} [{r['similarity']:.3f}] {r['source']}")
    print(f"     {r['text'][:80]}...")

print("\n💬 RAG 问答测试：")
answer, sources = store.ask("Embedding 是什么？它有什么用？")
print(f"  📝 {answer}")
print(f"  📎 引用了 {len(sources)} 段资料")


# ============================================================
# 实验 6：交互式 RAG 问答
# ============================================================
print("\n" + "=" * 60)
print("实验 6：交互式 RAG 问答 —— 你的私有知识库")
print("=" * 60)
print("""
知识库已就绪！你可以基于 data/ 目录下的文档提问。

  知识库包含：
    - AI 应用开发知识库（TXT）：LLM 基础 / Prompt 工程 / RAG / Agent
    - AI 入门指南（PDF）

  试试问：
    "什么是 RAG？"
    "怎么优化 API 调用的稳定性？"
    "Streamlit 适合做什么？"
    "Token 是什么？Temperature 怎么调？"

  输入 quit / q / 退出 结束对话。
""")

while True:
    try:
        q = input("\n🙋 你的问题：").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n再见！")
        break

    if not q:
        continue
    if q.lower() in ("quit", "q", "退出", "exit"):
        print("再见！")
        break

    # 先展示检索结果
    print("🔍 检索相关段落...")
    results = store.search(q, top_k=3)

    if not results:
        print("  ⚠️ 未找到相关内容，尝试直接问 LLM...")
        r = llm_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": q}],
            temperature=0.5,
        )
        print(f"\n📝 {r.choices[0].message.content}")
        print("\n  (以上回答来自 LLM 通用知识，非知识库内容)")
        continue

    for j, result in enumerate(results):
        print(f"  #{j+1} [{result['similarity']:.3f}] 📄 {result['source']}")

    # RAG 回答
    print("\n💭 基于检索结果生成回答...")
    answer, sources = store.ask(q, top_k=3)
    print(f"\n📝 {answer}")
    print(f"\n  📎 基于 {len(sources)} 段资料生成")


# ============================================================
# Day 10 总结
# ============================================================
print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    📝 Day 10 总结                            ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  今天你学到了 Chroma 持久化 + Embedding 深入理解：            ║
║                                                              ║
║  ① Embedding 本质：文字 → 高维向量（1536 维）                 ║
║  ② 余弦相似度：衡量两段文字语义接近程度的数学工具              ║
║  ③ Chroma PersistentClient：数据存磁盘，重启不丢失            ║
║  ④ 完整入库管线：加载 → 切割 → Embedding → Chroma             ║
║  ⑤ 可复用的 VectorStore 类：ingest() + search() + ask()       ║
║                                                              ║
║  🔑 三个关键认知：                                            ║
║  1. Embedding = 语义的数字化表示（相似文本 → 相近向量）        ║
║  2. 余弦相似度 = RAG 检索的数学基础                           ║
║  3. 持久化 Chroma = 真正的"知识库"（不是每次重建）             ║
║                                                              ║
║  🎯 你现在的能力：                                            ║
║  - 能把任意文档目录变成可搜索的向量知识库                      ║
║  - 理解 Embedding 是什么、怎么用、相似度怎么算                 ║
║  - 用 VectorStore 类一行代码完成文档入库 + 语义搜索            ║
║                                                              ║
║  🔜 Day 11 预告：RAG 核心闭环                                  ║
║  语义检索 + 拼接上下文 + LLM 生成 → 完整的 RAG 问答系统        ║
║  用 Streamlit 做一个「上传文档 → 提问 → 回答 + 原文溯源」    ║
╚══════════════════════════════════════════════════════════════╝
""")
