"""
Day 8 - RAG（检索增强生成）入门
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
今天的目标：理解 RAG 全流程，跑通第一个 RAG 示例

RAG 五步流程：
  1. Load    → 加载文档
  2. Split   → 切割成小块（chunk）
  3. Embed   → 每块转成向量（一串数字）
  4. Store   → 存入向量数据库
  5. Retrieve → 搜到相关内容 + 拼接原文 + 喂给 LLM 生成答案

为什么需要 RAG？
  LLM 的知识有截止日期，而且不知道你的私有文档内容。
  RAG 让你把任意文档"喂"给 LLM，让它基于你的文档回答。

学完今天你会：
  ✅ 理解 RAG 是什么、解决什么问题
  ✅ 理解 Embedding 向量的直观含义
  ✅ 语义搜索 vs 关键词搜索的区别
  ✅ 跑通一个完整的 RAG 示例
"""

import os, sys
sys.stdout.reconfigure(encoding='utf-8')

from config import client as llm_client, MODEL as LLM_MODEL
from openai import OpenAI
import numpy as np

# ============================================================
# 0. 先看架构图（你面试时要能画出来）
# ============================================================
print("=" * 65)
print("  RAG 架构全景图（面试必问，要能画出来）")
print("=" * 65)
print("""
  ┌─────────────────────────────────────────────────────┐
  │                    RAG 系统                          │
  │                                                     │
  │   离线阶段（文档入库）           在线阶段（用户提问）    │
  │  ┌──────────┐                  ┌──────────┐         │
  │  │ ① 加载    │                  │ 用户问题  │         │
  │  │  PDF/TXT  │                  └────┬─────┘         │
  │  └────┬─────┘                       │               │
  │       │                             ▼               │
  │       ▼                        ┌──────────┐         │
  │  ┌──────────┐                  │ ④ 向量化  │         │
  │  │ ② 切割    │                  │  问题    │         │
  │  │  chunk   │                  └────┬─────┘         │
  │  └────┬─────┘                       │               │
  │       │                             ▼               │
  │       ▼                        ┌──────────┐         │
  │  ┌──────────┐                  │ ⑤ 语义    │         │
  │  │ ③ 向量化  │                  │  检索    │         │
  │  │  Embed   │                  └────┬─────┘         │
  │  └────┬─────┘                       │               │
  │       │                             ▼               │
  │       ▼                        ┌──────────┐         │
  │  ┌──────────┐                  │ ⑥ 拼接    │         │
  │  │ 向量数据库 │──── 相似度 ────→│  上下文   │         │
  │  │ (Chroma) │     检索        └────┬─────┘         │
  │  └──────────┘                      │               │
  │                                    ▼               │
  │                               ┌──────────┐         │
  │                               │ ⑦ LLM    │         │
  │                               │  生成答案 │         │
  │                               └──────────┘         │
  └─────────────────────────────────────────────────────┘
""")

input("按 Enter 继续，开始看代码实现...")

# ============================================================
# 1. 准备"文档"（模拟你的私有知识库）
# ============================================================
print("\n" + "=" * 65)
print("  第 1 步：准备文档")
print("=" * 65)
print("""
真实场景中，文档来自你上传的 PDF/Word/TXT。
今天我们先在代码里直接定义几个文档段落，聚焦 RAG 流程本身。
""")

documents = [
    {
        "title": "Python 协程原理",
        "content": """
Python 的协程（coroutine）是通过 async/await 语法实现的。
协程的核心是事件循环（event loop），它在一个线程内调度多个协程任务。
与线程不同，协程的切换是协作式的——只有在遇到 await 时才会让出执行权。
Python 3.11+ 对 asyncio 做了大量优化，Task 的创建速度提升了 3 倍。
使用 asyncio.gather() 可以并发运行多个协程，但要注意：如果其中一个抛出异常，
默认会传播给其他协程。建议使用 return_exceptions=True 参数。
        """.strip(),
    },
    {
        "title": "Django ORM 查询优化",
        "content": """
Django ORM 最常见的性能问题是 N+1 查询。
当你遍历一个 QuerySet 并访问外键字段时，Django 会对每条记录额外执行一次查询。
解决方案是使用 select_related()（用于 ForeignKey）和 prefetch_related()（用于 ManyToMany）。
select_related 使用 SQL JOIN，一次查询拿到所有数据；prefetch_related 使用两次查询 + Python 拼接。
Django 4.2+ 引入了异步 ORM，但大多数项目仍在使用同步版本。
使用 django-debug-toolbar 可以直观地看到每条请求执行了多少 SQL 查询。
        """.strip(),
    },
    {
        "title": "Docker 容器化部署",
        "content": """
Docker 通过容器（container）将应用和依赖打包在一起，确保在任何环境运行一致。
核心概念：Dockerfile（构建镜像的配方）、Image（镜像，只读模板）、Container（容器，运行实例）。
docker-compose 可以编排多个容器，比如 web + db + redis 一起启动。
常用的最佳实践：多阶段构建（multi-stage build）减小镜像体积、使用 .dockerignore 排除无关文件、
不要在镜像里硬编码密钥（用环境变量或 secrets）。
阿里云容器镜像服务（ACR）可以托管私有 Docker 镜像，国内拉取速度比 Docker Hub 快很多。
        """.strip(),
    },
    {
        "title": "RESTful API 设计规范",
        "content": """
好的 API 设计遵循 REST 原则：资源用 URL 表示，操作用 HTTP 方法表示。
GET /users/  → 获取用户列表（用查询参数做筛选和分页）
POST /users/ → 创建用户（请求体放 JSON）
PUT /users/{id}/ → 全量更新用户
PATCH /users/{id}/ → 部分更新用户
DELETE /users/{id}/ → 删除用户
关于分页：推荐使用基于游标（cursor）的分页而非 offset，因为在数据频繁变化时 offset 会重复或遗漏。
返回格式统一用 JSON，错误时返回合适的 HTTP 状态码（400/401/403/404/500）。
        """.strip(),
    },
    {
        "title": "Git 工作流与协作",
        "content": """
Git Flow 是经典的 Git 分支管理策略：
- main 分支：生产环境代码，只接受 merge 不接受直接 commit
- develop 分支：开发主线，feature 分支从这里拉出、merge 回来
- feature/xxx 分支：新功能开发
- hotfix/xxx 分支：紧急修复，从 main 拉出，合并回 main 和 develop
日常开发中更常用的是 GitHub Flow（更简单）：main + feature 分支 + Pull Request。
提交信息（commit message）推荐 Conventional Commits 规范：
feat: 新功能 / fix: 修 bug / docs: 文档 / refactor: 重构 / test: 测试
        """.strip(),
    },
]

print(f"准备了 {len(documents)} 篇文档：")
for i, doc in enumerate(documents, 1):
    print(f"  {i}. 《{doc['title']}》({len(doc['content'])} 字)")

input("\n按 Enter 进入第 2 步：文档切割...")

# ============================================================
# 2. 文档切割（Chunking）
# ============================================================
print("\n" + "=" * 65)
print("  第 2 步：文档切割（Chunking）")
print("=" * 65)
print("""
为什么要把文档切成小块？
  1. LLM 的上下文窗口有限（qwen-plus 约 131K token，但塞太满回答质量会下降）
  2. Embedding 模型通常只处理 512~8192 token 的文本
  3. 小块检索更精准——你不会因为一句话匹配就返回整本书

切割的核心参数：
  chunk_size  = 每个块最多多少字符
  chunk_overlap = 相邻两块之间重叠多少字符（防止一句话被拦腰切断）
""")

from langchain_text_splitters import RecursiveCharacterTextSplitter

# 创建切割器
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=200,       # 每块最多 200 字符
    chunk_overlap=40,     # 相邻块重叠 40 字符
    separators=["\n\n", "\n", "。", ".", "，", ",", " ", ""],  # 优先在段落边界切
)

# 把所有文档内容拼接起来（每篇加标题），然后切割
all_chunks = []
for doc in documents:
    full_text = f"【{doc['title']}】\n{doc['content']}"
    chunks = text_splitter.split_text(full_text)
    all_chunks.extend(chunks)
    print(f"\n  《{doc['title']}》→ 切成 {len(chunks)} 块：")
    for j, chunk in enumerate(chunks):
        print(f"    块{j+1}: [{len(chunk)}字] \"{chunk[:60]}...\"")

print(f"\n  📊 总计：{len(documents)} 篇文档 → {len(all_chunks)} 个 chunk")

input("\n按 Enter 进入第 3 步：向量化（Embedding）...")

# ============================================================
# 3. 向量嵌入（Embedding）—— 文字 → 数字
# ============================================================
print("\n" + "=" * 65)
print("  第 3 步：向量嵌入（Embedding）")
print("=" * 65)
print("""
Embedding 是什么？
  把一段文字转换成一组数字（向量），语义相近的文字，向量也相近。

举个直观例子（这 3 句话的向量在空间中会很接近）：
  "Python 是一门编程语言" → [0.12, -0.34, 0.56, ...]
  "Python 是很好的入门语言" → [0.15, -0.30, 0.52, ...]
  "今天天气不错"           → [0.89, 0.72, -0.11, ...]  ← 和前两句完全不同

百炼 text-embedding-v2 把每段文字映射成 1536 维的向量。
""")

# 调用百炼 Embedding API
print(f"正在向量化 {len(all_chunks)} 个 chunk...", end=" ", flush=True)

# 百炼 Embedding API 单次最多处理 25 条，我们分批次
embeddings_list = []
BATCH_SIZE = 20

for i in range(0, len(all_chunks), BATCH_SIZE):
    batch = all_chunks[i : i + BATCH_SIZE]
    resp = llm_client.embeddings.create(
        model="text-embedding-v2",
        input=batch,
    )
    embeddings_list.extend([d.embedding for d in resp.data])

print("完成！")
print(f"  每个 chunk 现在是一个 {len(embeddings_list[0])} 维向量")
print(f"  示例（前 5 维）：{embeddings_list[0][:5]}")

input("\n按 Enter 进入第 4 步：存入向量数据库...")

# ============================================================
# 4. 存入向量数据库（Chroma）
# ============================================================
print("\n" + "=" * 65)
print("  第 4 步：存入向量数据库（Chroma）")
print("=" * 65)
print("""
Chroma 是一个轻量级向量数据库，专为 RAG 设计。
它把「文本 + 向量 + 元数据」存到一起，支持语义搜索。

Chroma 支持两种模式：
  - 内存模式：重启就没了，适合学习和调试
  - 持久化模式：存到磁盘，重启还在，适合实际使用
今天用内存模式，Day 10 会升级到持久化。
""")

import chromadb

# 创建 Chroma 客户端（内存模式）
chroma_client = chromadb.Client()

# 删除旧 collection（如果有的话，方便重复运行）
try:
    chroma_client.delete_collection("my_knowledge_base")
except:
    pass

# 创建 collection（类似数据库里的"表"）
collection = chroma_client.create_collection(
    name="my_knowledge_base",
    metadata={"description": "我的私有知识库"},
)

# 把 chunk 存进去
for i, (chunk, embedding) in enumerate(zip(all_chunks, embeddings_list)):
    collection.add(
        ids=[f"chunk_{i}"],
        embeddings=[embedding],
        documents=[chunk],
        metadatas=[{"index": i, "length": len(chunk)}],
    )

print(f"已存入 {collection.count()} 条记录到向量数据库")
print(f"Collection 名称：{collection.name}")

input("\n按 Enter 进入第 5 步：语义检索...")

# ============================================================
# 5. 语义检索（Semantic Search）
# ============================================================
print("\n" + "=" * 65)
print("  第 5 步：语义检索 —— 找到最相关的内容")
print("=" * 65)
print("""
检索过程：
  1. 把用户问题也转成向量
  2. 在向量数据库中找最相似的 top-K 个 chunk
  3. 返回这些 chunk 的原文

这就是「语义搜索」——不是匹配关键词，而是匹配含义。
"怎么让 Django 查询更快" 和 "ORM 性能优化" 关键词完全不同，
但它们的向量距离很近，因为语义相似。
""")

# 测试几个问题，看看检索效果
test_questions = [
    "Django 查询太慢了怎么办？",
    "协程和线程有什么区别？",
    "Docker 怎么减小镜像体积？",
]

for question in test_questions:
    print(f"\n{'─' * 50}")
    print(f"🔍 问题：{question}")

    # 把问题转成向量
    q_embedding = llm_client.embeddings.create(
        model="text-embedding-v2",
        input=question,
    ).data[0].embedding

    # 在 Chroma 中搜索
    results = collection.query(
        query_embeddings=[q_embedding],
        n_results=2,  # 返回最相似的 2 个 chunk
    )

    # 展示结果
    for j, (doc, distance) in enumerate(zip(
        results["documents"][0],
        results["distances"][0],
    )):
        similarity = 1 - distance  # Chroma 返回的是 L2 距离，转成相似度
        print(f"  #{j+1} (相似度: {similarity:.3f})：{doc[:80]}...")

input("\n按 Enter 进入最后一步：RAG  vs 直接问 LLM 对比...")


# ============================================================
# 6. RAG vs 直接 LLM  —— 关键对比实验
# ============================================================
print("\n" + "=" * 65)
print("  第 6 步：RAG vs 直接问 LLM —— 关键对比")
print("=" * 65)
print("""
同一个问题，两种方式回答：

  方式 A（直接问 LLM）：
    用户问题 → LLM → 答案（基于 LLM 自己的知识）

  方式 B（RAG）：
    用户问题 → 向量检索 → 找到相关文档 → 拼接成 Prompt → LLM → 答案
                                            ↑
                               "请根据以下资料回答..."
""")

def ask_llm_directly(question: str) -> str:
    """方式 A：直接问 LLM（无 RAG）"""
    r = llm_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": "你是一个编程助手，用中文回答，不超过 3 句话。"},
            {"role": "user", "content": question},
        ],
        temperature=0.3,
    )
    return r.choices[0].message.content


def ask_with_rag(question: str, collection, n_results: int = 3) -> tuple[str, list[str]]:
    """
    方式 B：RAG 增强回答

    返回：(回答, [检索到的上下文])
    """
    # Step 1: 向量化问题
    q_embedding = llm_client.embeddings.create(
        model="text-embedding-v2",
        input=question,
    ).data[0].embedding

    # Step 2: 语义检索
    results = collection.query(
        query_embeddings=[q_embedding],
        n_results=n_results,
    )
    retrieved_docs = results["documents"][0]

    # Step 3: 拼接上下文
    context = "\n\n---\n\n".join(retrieved_docs)

    # Step 4: 构造 RAG Prompt
    rag_prompt = f"""请根据以下资料回答问题。如果资料中没有相关信息，请如实说明。

【资料】
{context}

【问题】
{question}

【回答要求】
- 基于上述资料回答
- 如果资料包含了相关答案，请引用
- 中文回答，简洁有力"""

    # Step 5: 调用 LLM
    r = llm_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": "你是一个严谨的助手，只根据提供的资料回答问题。"},
            {"role": "user", "content": rag_prompt},
        ],
        temperature=0.3,
    )
    return r.choices[0].message.content, retrieved_docs


# ── 开始对比实验 ──
test_question = "如何优化 Django 的数据库查询性能？"

print(f"\n{'=' * 65}")
print(f"测试问题：{test_question}")
print(f"{'=' * 65}")

# 方式 A
print("\n📦 方式 A：直接问 LLM（没有 RAG）")
print("─" * 40)
answer_direct = ask_llm_directly(test_question)
print(f"{answer_direct}")

# 方式 B
print("\n🔍 方式 B：RAG 增强（先检索知识库，再回答）")
print("─" * 40)
answer_rag, sources = ask_with_rag(test_question, collection)
print(f"{answer_rag}")

print("\n  检索到的上下文来源：")
for i, src in enumerate(sources, 1):
    print(f"    来源{i}：{src[:100]}...")

print(f"""
{'=' * 65}
  📌 关键对比
{'=' * 65}

  方式 A（直接 LLM）：
    → 基于 LLM 的通用知识，答案泛泛而谈
    → 可能给出不适用于你项目的"通用建议"

  方式 B（RAG）：
    → 基于你的私有文档回答，精准具体
    → 提到了 Django ORM 的 select_related/prefetch_related
    → 这些内容来自你的知识库，LLM 不可能凭空知道

  这就是 RAG 的价值：让 LLM 基于「你的资料」回答。
""")

# ============================================================
# 7. 交互式问答（你在知识库上随便问）
# ============================================================
print("=" * 65)
print("  🎯 交互式 RAG 问答 —— 试试你的知识库！")
print("=" * 65)
print("""
  知识库包含 5 篇文档：
    1. Python 协程原理
    2. Django ORM 查询优化
    3. Docker 容器化部署
    4. RESTful API 设计规范
    5. Git 工作流与协作

  试试问一些相关问题，输入 quit 退出。
""")

while True:
    try:
        q = input("\n🙋 你的问题：").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n再见！")
        break

    if not q:
        continue
    if q.lower() in ("quit", "退出", "q"):
        print("再见！")
        break

    print("🔍 检索中...", end=" ", flush=True)
    answer, sources = ask_with_rag(q, collection)
    print("完成！\n")
    print(f"📝 {answer}")
    print(f"\n   (基于 {len(sources)} 段相关资料)")


# ============================================================
# Day 8 总结
# ============================================================
print("""
╔══════════════════════════════════════════════════════════════╗
║                      📝 Day 8 总结                           ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  今天你学到了 RAG 的五个核心步骤：                              ║
║                                                              ║
║  ① Load    → 加载文档（今天是内存文档，Day 9 用 PDF）          ║
║  ② Split   → 切割成 chunk（LangChain RecursiveTextSplitter）  ║
║  ③ Embed   → 向量化（百炼 text-embedding-v2，1536 维）        ║
║  ④ Store   → 存入 Chroma 向量数据库                          ║
║  ⑤ Retrieve → 语义检索 + 拼接上下文 + LLM 生成               ║
║                                                              ║
║  🔑 三个关键认知：                                            ║
║  1. Embedding = 把文字变成可比较的向量                         ║
║  2. 语义搜索 ≠ 关键词搜索（"查询慢"="性能优化"）               ║
║  3. RAG = LLM 的"参考资料库"（不是替代 LLM，是增强它）         ║
║                                                              ║
║  🔜 Day 9 预告：用 LangChain 加载真实 PDF/TXT 文档            ║
╚══════════════════════════════════════════════════════════════╝
""")
