"""
Day 12 - RAG 检索质量调优：chunk_size / overlap / 相似度阈值
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Day 11 我们跑通了 RAG 的核心闭环，但用的是固定参数（chunk_size=400,
overlap=60, min_similarity=0.2）。这些参数是拍脑袋定的，不一定最优。

今天的目标：用实验找出最适合你数据的参数组合。

学完今天你会：
  ✅ 理解 chunk_size 对检索质量的深层影响（信息密度 vs 语义聚焦）
  ✅ 掌握 overlap 的权衡（边界安全 vs 冗余）
  ✅ 学会用相似度阈值平衡精确率和召回率
  ✅ 建立检索质量评估方法（Hit@K、MRR、平均相似度）
  ✅ 掌握 RAG 参数调优的系统方法论

核心认知：
  ┌──────────────────────────────────────────────────────────────┐
  │  调参不是玄学 — 是建立「假设 → 实验 → 指标 → 结论」的闭环   │
  │  面试官问的不是你用了什么参数，而是你怎么找到这些参数的       │
  └──────────────────────────────────────────────────────────────┘
"""

import sys, os
sys.stdout.reconfigure(encoding='utf-8')

import time
import math
import json
import shutil
from typing import Optional

import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader, PyPDFLoader
import glob as glob_module

from config import client as llm_client, MODEL as LLM_MODEL


# ============================================================
# 实验 1：理解三个核心调优参数 — 它们各自控制什么？
# ============================================================
print("=" * 60)
print("实验 1：三个核心调优参数的直觉理解")
print("=" * 60)
print("""
┌─────────────────────────────────────────────────────────────────┐
│                     RAG 检索质量的三个旋钮                        │
├──────────────┬──────────────────────────────────────────────────┤
│ chunk_size   │ 每个文本块多大？（字符数）                         │
│              │ 太小 → 信息碎片化，缺少上下文，检索"只见树木"      │
│              │ 太大 → 语义被稀释，一个 chunk 包含多个主题          │
│              │ 典型范围：200-1000                                 │
├──────────────┼──────────────────────────────────────────────────┤
│ overlap      │ 相邻两个 chunk 之间重叠多少字符？                  │
│              │ 太小 → 关键信息恰好落在切割边界上，检索不到         │
│              │ 太大 → 数据冗余，知识库膨胀，检索结果重复           │
│              │ 典型为 chunk_size 的 10%-20%                       │
├──────────────┼──────────────────────────────────────────────────┤
│ 相似度阈值   │ 低于此值的结果直接丢弃                             │
│              │ 太高 → 召回率低，漏掉相关内容                       │
│              │ 太低 → 精确率低，引入噪音干扰 LLM                   │
│              │ 典型范围：0.2-0.5                                  │
└──────────────┴──────────────────────────────────────────────────┘

一句话总结：
  chunk_size 决定「每个检索单元携带多少信息」
  overlap 保证「边界信息不丢失」
  相似度阈值过滤「不相关的内容别来捣乱」

今天的实验设计：
  实验 2：固定 overlap，变 chunk_size → 找最优 size
  实验 3：固定 chunk_size，变 overlap → 找最优 overlap
  实验 4：变相似度阈值 → 找精确率/召回率平衡点
  实验 5：组合最优参数 → 与 Day 11 默认参数正面 PK
""")


# ============================================================
# 实验 2：chunk_size 对照实验
# ============================================================
print("=" * 60)
print("实验 2：chunk_size 对照实验 — 多大才算合适？")
print("=" * 60)
print("""
实验方法：
  1. 用不同的 chunk_size（200 / 400 / 600 / 800）分别建库
  2. overlap 统一设为 chunk_size 的 15%
  3. 用同一组测试问题去检索
  4. 对比检索结果的命中率、相似度、信息完整度

测试问题设计原则：
  - 事实型问题（答案直接在某段文本中）→ 测检索精准度
  - 概念型问题（需要完整理解一个概念）→ 测上下文完整度
  - 跨段问题（答案分散在多段中）→ 测覆盖度
""")


# ── 2.1 准备语料 ──
# 使用 data/ 目录下的文档 + 内置示例，确保有足够的内容做实验
def load_documents(directory: str = "data") -> list:
    """加载所有文档（不做切割）"""
    docs = []
    txt_files = glob_module.glob(f"{directory}/**/*.txt", recursive=True)
    for f in txt_files:
        try:
            loader = TextLoader(f, encoding="utf-8")
            docs.extend(loader.load())
        except Exception as e:
            print(f"  ⚠️ TXT 加载失败 {f}: {e}")

    pdf_files = glob_module.glob(f"{directory}/**/*.pdf", recursive=True)
    for f in pdf_files:
        try:
            loader = PyPDFLoader(f)
            docs.extend(loader.load())
        except Exception as e:
            print(f"  ⚠️ PDF 加载失败 {f}: {e}")

    return docs


def split_documents(docs: list, chunk_size: int, overlap: int) -> list[dict]:
    """切割文档，返回统一的 dict 列表"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", "。", ".", "，", ",", " ", ""],
    )
    chunks = splitter.split_documents(docs)
    return [
        {"text": c.page_content, "source": c.metadata.get("source", "unknown"),
         "page": c.metadata.get("page")}
        for c in chunks
    ]


print("\n📥 加载文档...")
raw_docs = load_documents("data")

# 如果 data/ 下没有文档，使用内置语料
if not raw_docs:
    print("  ⚠️ data/ 目录无文档，使用内置测试语料\n")
    # 构造一个足够大的测试语料（模拟真实文档）
    _CORPUS = [
        # 第1篇：RAG 全流程详解
        "RAG（Retrieval-Augmented Generation，检索增强生成）是2026年最核心的AI应用形态。"
        "它将信息检索系统与大语言模型的生成能力相结合，有效解决了LLM的知识截止和幻觉问题。"
        "RAG的工作流程包含五个关键步骤：第一步Load加载文档，第二步Split文本切割，第三步Embed向量化，"
        "第四步Store存入向量数据库，第五步Retrieve检索加Generate生成。每个步骤的质量都会影响最终答案。",

        "在文档加载阶段，需要支持多种格式：TXT纯文本、PDF文档、Markdown文件、Word文档等。"
        "LangChain提供了丰富的DocumentLoader，如TextLoader、PyPDFLoader、UnstructuredMarkdownLoader。"
        "加载时要注意编码问题，UTF-8是最常用的编码格式，但某些中文文档可能使用GBK编码。",

        "文本切割是RAG中最容易被低估的环节。切割策略直接影响检索质量。"
        "常用的切割器有RecursiveCharacterTextSplitter（递归切割，优先按段落→句子→词语），"
        "以及SemanticChunker（语义切割，用Embedding相似度判断切割点）。"
        "实际项目中，RecursiveCharacterTextSplitter是最稳妥的默认选择。",

        "向量嵌入（Embedding）将文本转换成固定维度的数值向量。百炼的text-embedding-v2模型"
        "生成1536维向量。语义相近的文本在向量空间中距离更近。相似度度量常用余弦相似度（Cosine Similarity）"
        "或欧氏距离（L2 Distance）。Chroma默认使用L2距离，值越小表示越相似。",

        "Chroma是一个轻量级向量数据库，支持两种模式：内存模式（InMemoryClient，数据在内存中，"
        "程序退出即消失）和持久化模式（PersistentClient，数据存磁盘，重启不丢失）。"
        "对于生产环境，持久化是必须的。Chroma还支持元数据过滤，可以按来源、日期等条件筛选检索范围。",

        "RAG的Prompt设计是生成质量的灵魂。好的RAG Prompt包含五个要素：角色设定（告诉LLM它是谁）、"
        "行为约束（只能基于资料回答）、上下文区（清晰标注参考资料）、问题区（用户的问题）、"
        "格式要求（怎么组织答案）。三个级别：简陋版（无结构）、标准版（有约束）、严格版（可追溯引用）。",

        "RAG检索质量评估常用三个指标：Hit@K（正确答案是否出现在Top-K中）、"
        "MRR（Mean Reciprocal Rank，正确答案排名的倒数均值）、"
        "NDCG（Normalized Discounted Cumulative Gain，考虑排名位置的相关性得分）。"
        "实际项目中，Hit@3和MRR是最实用的两个指标。",

        # 第2篇：Prompt 工程深入
        "Prompt工程是设计和优化输入文本以引导大语言模型产生期望输出的技术。"
        "核心原则包括：清晰明确（Be Clear）、提供示例（Few-Shot）、指定格式（JSON/Markdown）、"
        "角色扮演（System Prompt）、思维链引导（Chain of Thought）。"
        "2026年的最佳实践是结构化System Prompt + Markdown格式的指令。",

        "System Prompt是对话中第一条消息，设定AI的行为准则和角色边界。"
        "好的System Prompt应该包含：角色定义、能力范围、行为约束、输出格式要求。"
        "例如：'你是一个严谨的技术文档助手，只基于提供的资料回答问题，不知道就说不知道。'",

        "Temperature参数控制LLM输出的随机性。0.0-0.3适合需要精确性和一致性的任务（代码生成、事实问答），"
        "0.5-0.8适合需要创造性的任务（对话、写作），1.0以上适合创意发散（头脑风暴、诗歌创作）。"
        "RAG问答推荐0.1-0.3，因为需要忠实于检索到的资料。",

        "Few-Shot Prompting是在Prompt中提供几个示例（输入-输出对），让LLM理解任务模式。"
        "对于结构化输出任务（如信息提取、分类），2-3个示例通常足够。"
        "示例的选择比数量更重要——选最具代表性和边界情况的例子。",

        "思维链（Chain of Thought, CoT）是让LLM在给出最终答案前先展示推理步骤。"
        "简单加一句'让我们一步步思考（Let's think step by step）'就能显著提升复杂推理的准确率。"
        "2026年的进阶用法是结构化CoT，将推理过程分成分析、比较、结论等阶段。",

        # 第3篇：AI Agent 架构
        "AI Agent是能够自主感知环境、使用工具、规划多步骤任务并反思执行结果的AI系统。"
        "核心循环是：Planning（规划）→ Tool Use（使用工具）→ Reflection（反思）→ 迭代。"
        "与普通LLM对话不同，Agent不是被动回答问题，而是主动分解任务并执行。",

        "Function Calling是LLM调用外部工具的标准机制。开发者定义函数名称、用途描述和参数Schema，"
        "LLM根据用户意图自主决定是否调用、调用哪个函数、传什么参数。"
        "百炼和DeepSeek都兼容OpenAI的Function Calling接口规范。",

        "Agent的工具类型包括：搜索工具（Tavily、DuckDuckGo、Google Search）、"
        "计算工具（Python REPL、Wolfram Alpha）、数据库工具（SQL查询）、"
        "文件工具（读写文件）、API工具（调用外部服务）。"
        "多工具Agent的关键挑战是工具选择和错误恢复。",

        "Agent开发中的常见问题和解决方案：循环不停（设max_iterations=5）、"
        "工具调用错误（加try-except和重试逻辑）、上下文溢出（及时摘要旧消息）、"
        "工具选择错误（在工具描述中明确适用场景）。永远为Agent设上限，这是生产环境的第一准则。",

        "ReAct（Reasoning + Acting）是Agent的主流范式：思考→行动→观察→思考→行动→..."
        "每次行动后观察结果，根据结果调整下一步计划。LangChain的AgentExecutor封装了这一模式。"
        "ReAct让Agent的行为可解释、可调试、可干预。",

        # 第4篇：Streamlit Web应用
        "Streamlit是纯Python的Web应用框架，让不懂前端的开发者也能构建AI应用界面。"
        "核心组件：st.title（标题）、st.text_input（文本输入）、st.text_area（多行文本）、"
        "st.button（按钮）、st.spinner（加载动画）、st.chat_message（对话气泡）、"
        "st.sidebar（侧边栏）、st.file_uploader（文件上传）。",

        "Streamlit的状态管理：st.session_state用于在多次交互间保持数据。"
        "例如保存对话历史、API Key、用户设置。关键方法：初始化（if 'key' not in st.session_state）、"
        "更新（st.session_state.key = value）、清除（del st.session_state.key）。",

        "Streamlit部署选项：Streamlit Cloud（免费，适合Demo）、HuggingFace Spaces（免费，"
        "支持Docker）、阿里云函数计算（国内稳定）、Railway（简单易用）。"
        "部署时需要requirements.txt固定依赖版本，避免环境差异导致的问题。",

        "Streamlit + RAG的典型架构：侧边栏（文档上传+参数设置）→ 主区域（聊天界面）→ "
        "后台（加载文档→切割→向量化→存Chroma→检索→生成→流式输出）。"
        "关键是处理好文件上传后的重新索引和会话状态的管理。",

        # 第5篇：API调用最佳实践
        "LLM API调用的健壮性设计包括三个层次：重试机制（应对网络波动和限流）、"
        "异常分类处理（4xx客户端错误 vs 5xx服务端错误）、降级策略（主模型不可用时切换备用模型）。"
        "Python中使用tenacity库实现指数退避重试：等待1s→2s→4s→8s，最多重试3次。",

        "流式输出（Stream=True）通过Server-Sent Events实现，LLM逐token返回结果。"
        "用户体验优势：首字延迟从5-10秒降至0.5秒以内。实现要点：遍历chunks时需要处理"
        "空delta（某些chunk的content为None或空字符串）和异常中断后的优雅恢复。",

        "API Key安全管理原则：使用环境变量（.env文件）+ .gitignore排除 + "
        ".env.example提供模板。永远不在代码中硬编码Key。生产环境使用密钥管理服务（如阿里云KMS）。"
        "定期轮换Key，设置用量告警，避免被滥用导致费用超标。",

        "Token计费和优化：中文通常1-2字符≈1 token，英文1单词≈1.3 token。"
        "省钱技巧：用更短的System Prompt、摘要历史对话而非保留全文、"
        "设置max_tokens限制输出长度。百炼qwen-plus的免费额度足够学习使用。",
    ]
    # 将语料拼接成一篇大文档，每条之间用双换行分隔
    full_text = "\n\n".join(_CORPUS)
    raw_docs = type("_Doc", (), {"page_content": full_text, "metadata": {"source": "day12_corpus"}})
    raw_docs = [raw_docs]
else:
    print(f"  ✅ 加载了 {len(raw_docs)} 个文档")


# ── 2.2 构建多组知识库 ──
print("\n🔧 构建对照实验知识库...")
print("   同一份语料 × 不同 chunk_size，观察检索质量差异\n")

CHUNK_SIZES = [200, 400, 600, 800]
OVERLAP_RATIO = 0.15  # overlap 统一为 chunk_size 的 15%

# 实验脚本使用内存模式（EphemeralClient），避免磁盘数据损坏导致报错
# 注意：chromadb.Client() 创建的是 EphemeralClient（新版 chromadb）
chroma_client = chromadb.Client()

# 为每个 chunk_size 构建独立的 collection
collections = {}
for cs in CHUNK_SIZES:
    overlap = int(cs * OVERLAP_RATIO)
    col_name = f"cs_{cs}_ol_{overlap}"
    print(f"  📦 构建 chunk_size={cs}, overlap={overlap} 的知识库...")

    chunks = split_documents(raw_docs, chunk_size=cs, overlap=overlap)
    print(f"     切割出 {len(chunks)} 个 chunk")

    col = chroma_client.create_collection(
        name=col_name,
        metadata={"chunk_size": str(cs), "overlap": str(overlap), "description": f"Day12 对照实验"},
    )

    # 批量向量化（控制 batch 大小避免 API 限流）
    BATCH_SIZE = 20
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        embeddings = []
        for c in batch:
            resp = llm_client.embeddings.create(model="text-embedding-v2", input=c["text"])
            embeddings.append(resp.data[0].embedding)

        for j, (chunk, emb) in enumerate(zip(batch, embeddings)):
            col.add(
                ids=[f"c_{i + j:04d}"],
                embeddings=[emb],
                documents=[chunk["text"]],
                metadatas=[{"source": os.path.basename(chunk["source"]), "page": chunk.get("page") or -1}],
            )

    collections[cs] = col
    print(f"     ✅ {col.count()} 条记录入库完成")

print(f"\n  📊 知识库总览：")
for cs, col in collections.items():
    print(f"    chunk_size={cs:>4} → {col.count():>4} chunks")


# ── 2.3 定义测试问题集 ──
# 每个问题标注了「正确答案」应该包含的关键词
TEST_QUERIES = [
    {
        "id": "Q1",
        "query": "RAG的五个步骤是什么？",
        "gold_keywords": ["Load", "Split", "Embed", "Store", "Retrieve", "Generate",
                          "加载", "切割", "向量化", "存储", "检索", "生成"],
        "type": "事实型",
        "description": "答案明确在文本中，测试精确检索能力",
    },
    {
        "id": "Q2",
        "query": "System Prompt应该包含哪些要素？",
        "gold_keywords": ["角色", "定义", "能力", "约束", "输出格式"],
        "type": "概念型",
        "description": "需要一个完整段落才能完整回答",
    },
    {
        "id": "Q3",
        "query": "Agent开发中如何防止循环不停的问题？",
        "gold_keywords": ["max_iterations", "上限", "5", "限制"],
        "type": "事实型",
        "description": "答案可能在一句话中，测试精准定位",
    },
    {
        "id": "Q4",
        "query": "Chroma持久化模式和内存模式有什么区别？什么场景用哪种？",
        "gold_keywords": ["持久化", "PersistentClient", "内存", "InMemoryClient", "磁盘", "重启"],
        "type": "概念型",
        "description": "答案需要跨段整合，测试覆盖度",
    },
    {
        "id": "Q5",
        "query": "LLM API调用失败时应该怎么处理？有哪些容错策略？",
        "gold_keywords": ["重试", "异常", "降级", "备用", "指数退避", "tenacity"],
        "type": "概念型",
        "description": "答案可能分散在多段，测试召回能力",
    },
    {
        "id": "Q6",
        "query": "Streamlit怎么管理用户会话状态？",
        "gold_keywords": ["session_state", "st.session_state"],
        "type": "事实型",
        "description": "答案有明确关键词，测试精准匹配",
    },
    {
        "id": "Q7",
        "query": "什么是Function Calling？它和普通API调用有什么区别？",
        "gold_keywords": ["Function Calling", "函数", "工具", "Schema", "参数", "LLM"],
        "type": "概念型",
        "description": "需要完整理解一个机制",
    },
    {
        "id": "Q8",
        "query": "NBA总决赛结果",
        "gold_keywords": [],  # 知识库中没有的内容
        "type": "干扰型",
        "description": "知识库中没有的信息，测试是否能正确返回低相似度",
    },
]


# ── 2.4 评估函数 ──
def evaluate_retrieval(col, queries: list[dict], top_k: int = 5,
                       min_similarity: float = 0.0) -> dict:
    """
    对一组查询评估检索质量。

    返回汇总指标：
      - hit_at_k:      正确答案出现在 top-k 中的比例
      - mrr:           Mean Reciprocal Rank（正确答案排名的倒数均值）
      - avg_similarity: top-1 结果的平均相似度
      - avg_top_sim:    top-k 结果的平均相似度
      - details:       每个查询的详细结果
    """
    details = []
    hits = []
    reciprocal_ranks = []
    top1_sims = []

    for q in queries:
        q_emb = llm_client.embeddings.create(
            model="text-embedding-v2", input=q["query"]
        ).data[0].embedding

        raw = col.query(query_embeddings=[q_emb], n_results=top_k)

        results = []
        for i, (doc, meta, dist) in enumerate(zip(
            raw["documents"][0], raw["metadatas"][0], raw["distances"][0]
        )):
            sim = 1.0 / (1.0 + dist)
            if sim >= min_similarity:
                results.append({
                    "rank": i + 1,
                    "text": doc,
                    "similarity": round(sim, 4),
                    "distance": round(dist, 4),
                })

        # 计算 Hit@K：是否有结果包含至少1个 gold_keyword
        hit = False
        best_rank = None
        if q["gold_keywords"]:
            for r in results:
                # 检查该结果是否匹配到关键词（至少匹配 1 个）
                matched = sum(1 for kw in q["gold_keywords"] if kw.lower() in r["text"].lower())
                if matched >= 1:
                    hit = True
                    if best_rank is None:
                        best_rank = r["rank"]
                    break  # 找到第一个匹配即可确认 hit

        hits.append(1 if hit else 0)
        rr = 1.0 / best_rank if best_rank else 0.0
        reciprocal_ranks.append(rr)
        if results:
            top1_sims.append(results[0]["similarity"])

        details.append({
            "query_id": q["id"],
            "query": q["query"],
            "type": q["type"],
            "results_count": len(results),
            "top_similarity": results[0]["similarity"] if results else 0,
            "hit": hit,
            "best_rank": best_rank,
            "top_results": results[:3],  # 只保留 top-3 供展示
        })

    return {
        "hit_at_k": round(sum(hits) / len(hits), 3) if hits else 0,
        "mrr": round(sum(reciprocal_ranks) / len(reciprocal_ranks), 4) if reciprocal_ranks else 0,
        "avg_top1_similarity": round(sum(top1_sims) / len(top1_sims), 4) if top1_sims else 0,
        "details": details,
    }


# ── 2.5 运行 chunk_size 对照实验 ──
print("\n" + "─" * 60)
print("2.5 chunk_size 对照实验结果")
print("─" * 60)
print(f"\n  📋 测试问题：{len(TEST_QUERIES)} 个（含 {sum(1 for q in TEST_QUERIES if q['type'] != '干扰型')} 个知识库内问题 + 1 个干扰问题）")
print(f"  📐 固定 overlap = chunk_size × {OVERLAP_RATIO}")
print()

cs_results = {}
for cs in CHUNK_SIZES:
    print(f"  ⏳ 评估 chunk_size={cs}...")
    result = evaluate_retrieval(collections[cs], TEST_QUERIES, top_k=5, min_similarity=0.0)
    cs_results[cs] = result

# ── 打印对比表 ──
print(f"\n  {'─'*70}")
print(f"  {'chunk_size':<14} {'chunks':>6} {'Hit@5':>8} {'MRR':>8} {'Top1相似度':>10}")
print(f"  {'─'*70}")
for cs in CHUNK_SIZES:
    r = cs_results[cs]
    print(f"  {cs:<14} {collections[cs].count():>6} {r['hit_at_k']:>8.1%} {r['mrr']:>8.4f} {r['avg_top1_similarity']:>10.4f}")

print(f"  {'─'*70}")

# 找出最优 chunk_size
best_cs = max(cs_results, key=lambda cs: cs_results[cs]["mrr"] + cs_results[cs]["hit_at_k"])
print(f"\n  🏆 最优 chunk_size = {best_cs}（Hit@5 + MRR 综合最优）")

# 打印每个问题的详细对比
print(f"\n  📊 逐题 Hit 对比：")
header = f"  {'问题':<6} {'类型':<6}"
for cs in CHUNK_SIZES:
    header += f" {'cs=' + str(cs):<10}"
print(header)
print(f"  {'─'*60}")
for i, q in enumerate(TEST_QUERIES):
    row = f"  {q['id']:<6} {q['type']:<6}"
    for cs in CHUNK_SIZES:
        detail = cs_results[cs]["details"][i]
        symbol = "✅" if detail["hit"] else "❌"
        row += f" {symbol} r={detail['best_rank'] or '-':<3}"
    print(row)

print(f"""
  📌 chunk_size 调优观察：
  ┌─────────────────────────────────────────────────────────────┐
  │ • size=200：切割太细，一个完整概念被拆散                     │
  │   检索可能命中"片段"但不是"完整答案"                         │
  │                                                             │
  │ • size=400：通常是 RAG 的最佳起点                            │
  │   大多数段落/概念能完整放入一个 chunk                         │
  │                                                             │
  │ • size=600-800：信息量大，但一个 chunk 可能覆盖多个主题       │
  │   语义会被稀释，"搜索信号"变弱                               │
  │                                                             │
  │ 🎯 经验法则：                                                │
  │   - 技术文档/FAQ：300-500                                    │
  │   - 学术论文/长篇：500-800                                   │
  │   - 对话/聊天记录：200-400                                   │
  │   - 没有银弹：用你的数据跑实验，让指标说话                   │
  └─────────────────────────────────────────────────────────────┘
""")


# ============================================================
# 实验 3：overlap 对照实验
# ============================================================
print("=" * 60)
print("实验 3：overlap 对照实验 — 边界安全 vs 冗余")
print("=" * 60)

# 使用实验 2 找到的最优 chunk_size
OPTIMAL_CS = best_cs
print(f"  📐 固定 chunk_size = {OPTIMAL_CS}（来自实验 2 的最优值）\n")

OVERLAP_VALUES = [0, 50, 100, 150]

overlap_collections = {}
for ov in OVERLAP_VALUES:
    col_name = f"cs_{OPTIMAL_CS}_ol_{ov}"
    print(f"  📦 构建 chunk_size={OPTIMAL_CS}, overlap={ov} 的知识库...")

    # 清理旧 collection
    try:
        chroma_client.delete_collection(col_name)
    except Exception:
        pass

    chunks = split_documents(raw_docs, chunk_size=OPTIMAL_CS, overlap=ov)
    print(f"     切割出 {len(chunks)} 个 chunk（overlap={ov}）")

    col = chroma_client.create_collection(
        name=col_name,
        metadata={"chunk_size": str(OPTIMAL_CS), "overlap": str(ov)},
    )

    BATCH_SIZE = 20
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        embeddings = []
        for c in batch:
            resp = llm_client.embeddings.create(model="text-embedding-v2", input=c["text"])
            embeddings.append(resp.data[0].embedding)

        for j, (chunk, emb) in enumerate(zip(batch, embeddings)):
            col.add(
                ids=[f"c_{i + j:04d}"],
                embeddings=[emb],
                documents=[chunk["text"]],
                metadatas=[{"source": os.path.basename(chunk["source"]), "page": chunk.get("page") or -1}],
            )

    overlap_collections[ov] = col
    print(f"     ✅ {col.count()} 条记录入库完成")

# 评估
print(f"\n{'─'*70}")
print(f"  {'overlap':<10} {'chunks':>6} {'Hit@5':>8} {'MRR':>8} {'Top1相似度':>10}")
print(f"  {'─'*70}")

ov_results = {}
for ov in OVERLAP_VALUES:
    result = evaluate_retrieval(overlap_collections[ov], TEST_QUERIES, top_k=5)
    ov_results[ov] = result
    print(f"  {ov:<10} {overlap_collections[ov].count():>6} {result['hit_at_k']:>8.1%} {result['mrr']:>8.4f} {result['avg_top1_similarity']:>10.4f}")

print(f"  {'─'*70}")

# 特殊观察：overlap=0 vs overlap=50 的边界情况
print(f"""
  📌 overlap 调优观察：
  ┌─────────────────────────────────────────────────────────────┐
  │ • overlap=0：无重叠                                           │
  │   优点：存储最小，无冗余                                       │
  │   风险：关键信息恰好落在 chunk 边界上 → 两个 chunk 都不完整     │
  │                                                               │
  │ • overlap=chunk_size × 10-20%：工程最佳实践                    │
  │   在存储开销和检索质量之间取得平衡                               │
  │                                                               │
  │ • overlap 过大的代价：                                         │
  │   1. 存储膨胀（每个 chunk 有 30%+ 的内容是重复的）               │
  │   2. 检索结果重复（同一个信息出现在多个 chunk 中）               │
  │   3. LLM 上下文浪费（重复信息占用宝贵的 token 预算）             │
  │                                                               │
  │ 🎯 经验法则：overlap ≈ chunk_size × 10%~15%                    │
  │   例如 chunk_size=400 → overlap=40~60                          │
  └─────────────────────────────────────────────────────────────┘
""")

# 找出最优 overlap
best_ov = max(ov_results, key=lambda ov: ov_results[ov]["mrr"] + ov_results[ov]["hit_at_k"])
print(f"  🏆 最优 overlap = {best_ov}（在 chunk_size={OPTIMAL_CS} 下）")


# ============================================================
# 实验 4：相似度阈值实验 — 精确率 vs 召回率的权衡
# ============================================================
print("\n" + "=" * 60)
print("实验 4：相似度阈值实验 — 精确率 vs 召回率")
print("=" * 60)
print("""
相似度阈值 = 一道"质量滤网"

  阈值设太高（如 0.7）：只保留高度确定的结果 → 高精确率，低召回率
  阈值设太低（如 0.1）：几乎什么结果都保留 → 高召回率，低精确率
  不设阈值（0.0）：全部保留，由 LLM 自己判断

关键问题：在你的数据上，最优阈值是多少？
""")

SIM_THRESHOLDS = [0.0, 0.2, 0.3, 0.4, 0.5]

# 使用最优参数组合
print(f"  📐 使用最优参数：chunk_size={OPTIMAL_CS}, overlap={best_ov}")
best_col = overlap_collections[best_ov]

print(f"\n{'─'*75}")
print(f"  {'阈值':<8} {'平均结果数':>10} {'Hit@5':>8} {'MRR':>8} {'Top1相似度':>10}")
print(f"  {'─'*75}")

threshold_results = {}
for th in SIM_THRESHOLDS:
    result = evaluate_retrieval(best_col, TEST_QUERIES, top_k=5, min_similarity=th)
    threshold_results[th] = result
    avg_count = sum(d["results_count"] for d in result["details"]) / len(result["details"])
    print(f"  {th:<8.1f} {avg_count:>10.1f} {result['hit_at_k']:>8.1%} {result['mrr']:>8.4f} {result['avg_top1_similarity']:>10.4f}")

print(f"  {'─'*75}")

# 观察干扰问题的表现
noise_q = TEST_QUERIES[-1]  # "NBA总决赛结果"
print(f"\n  🎯 干扰问题在各阈值下的表现（\"{noise_q['query']}\"）：")
print(f"  {'阈值':<8} {'结果数':>6} {'Top-1 相似度':>12}")
for th in SIM_THRESHOLDS:
    result = evaluate_retrieval(best_col, [noise_q], top_k=3, min_similarity=th)
    detail = result["details"][0]
    print(f"  {th:<8.1f} {detail['results_count']:>6} {detail['top_similarity']:>12.4f}")

print(f"""
  📌 相似度阈值调优观察：
  ┌─────────────────────────────────────────────────────────────┐
  │ • 阈值=0.0：不过滤，噪音也可能进入上下文                     │
  │   → 适合：知识库内容高度相关、没有干扰信息的场景             │
  │                                                             │
  │ • 阈值=0.2-0.3：工程最佳实践                                 │
  │   → 过滤掉明显不相关的 chunk，保留"可能相关"的内容           │
  │                                                             │
  │ • 阈值=0.4+：严格模式                                        │
  │   → 适合：对答案准确性要求极高的场景（医疗、法律）            │
  │   → 代价：可能漏掉"措辞不同但语义相关"的内容                 │
  │                                                             │
  │ 🎯 经验法则：从 0.2 开始，根据「答案相关性」人工判断来微调   │
  │   如果 LLM 频繁回答"知识库中没有"→ 降低阈值                  │
  │   如果 LLM 引用明显不相关的资料 → 提高阈值                   │
  └─────────────────────────────────────────────────────────────┘
""")


# ============================================================
# 实验 5：最优参数 vs Day 11 默认参数 —— 正面 PK
# ============================================================
print("=" * 60)
print("实验 5：Day 12 最优参数 vs Day 11 默认参数")
print("=" * 60)

DAY11_CHUNK_SIZE = 400
DAY11_OVERLAP = 60

print(f"""
  🥊 参数对比：

    Day 11（拍脑袋）          Day 12（实验驱动）
    ─────────────────         ──────────────────
    chunk_size = 400          chunk_size = {OPTIMAL_CS}
    overlap    = 60           overlap    = {best_ov}
    评估方法   = 无           评估方法   = Hit@5 + MRR

""")

# 用同一个查询词做对比
comparison_queries = [
    ("RAG五个步骤", "什么是RAG？它的工作流程有哪些步骤？"),
    ("Agent循环问题", "Agent开发中如果循环不停怎么办？"),
    ("System Prompt设计", "一个好的System Prompt应该怎么写？"),
]

print(f"  📋 用 3 个核心问题做直接对比（基于知识库生成 RAG 回答）：\n")

# 简易 RAG 问答函数（复用 Day 11 的 Prompt 模板）
def rag_ask(col, question: str, top_k: int = 4) -> str:
    """简化的 RAG 问答"""
    q_emb = llm_client.embeddings.create(
        model="text-embedding-v2", input=question
    ).data[0].embedding
    raw = col.query(query_embeddings=[q_emb], n_results=top_k)

    # 拼接上下文
    context_parts = []
    for i, (doc, meta, dist) in enumerate(zip(
        raw["documents"][0], raw["metadatas"][0], raw["distances"][0]
    )):
        sim = 1.0 / (1.0 + dist)
        if sim >= 0.2:
            context_parts.append(f"[资料{i+1}]（相似度{sim:.3f}）\n{doc}")

    if not context_parts:
        return "⚠️ 未检索到相关内容"

    context = "\n\n".join(context_parts)

    system = (
        "你是一个严谨的知识库助手。请严格基于提供的参考资料回答问题，"
        "引用时标注资料编号。资料中没有的信息请说明。"
    )
    user = (
        f"【参考资料】\n{context}\n\n"
        f"【问题】{question}\n\n"
        f"请基于资料给出准确回答，关键信息标注来源编号。"
    )

    r = llm_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.3,
    )
    return r.choices[0].message.content


# 构建 Day 11 参数的知识库
try:
    chroma_client.delete_collection("day11_baseline")
except Exception:
    pass

day11_col = chroma_client.create_collection(
    name="day11_baseline",
    metadata={"chunk_size": str(DAY11_CHUNK_SIZE), "overlap": str(DAY11_OVERLAP)},
)
day11_chunks = split_documents(raw_docs, chunk_size=DAY11_CHUNK_SIZE, overlap=DAY11_OVERLAP)
print(f"  📦 Day 11 知识库：{len(day11_chunks)} chunks (cs={DAY11_CHUNK_SIZE}, ov={DAY11_OVERLAP})")
print(f"  📦 Day 12 知识库：{best_col.count()} chunks (cs={OPTIMAL_CS}, ov={best_ov})\n")

# 向量化 Day 11 库
for i in range(0, len(day11_chunks), 20):
    batch = day11_chunks[i : i + 20]
    embeddings = []
    for c in batch:
        resp = llm_client.embeddings.create(model="text-embedding-v2", input=c["text"])
        embeddings.append(resp.data[0].embedding)
    for j, (chunk, emb) in enumerate(zip(batch, embeddings)):
        day11_col.add(ids=[f"c_{i + j:04d}"], embeddings=[emb], documents=[chunk["text"]],
                       metadatas=[{"source": os.path.basename(chunk["source"]), "page": chunk.get("page") or -1}])

# 逐题对比
for label, question in comparison_queries:
    print(f"  {'─'*60}")
    print(f"  🎯 {label}")
    print(f"     问题：{question}\n")

    # Day 11 检索
    print(f"     🔍 Day 11 检索结果：")
    q_emb = llm_client.embeddings.create(model="text-embedding-v2", input=question).data[0].embedding
    for col_label, col_obj in [("Day 11", day11_col), ("Day 12", best_col)]:
        raw = col_obj.query(query_embeddings=[q_emb], n_results=3)
        print(f"       [{col_label}] top-3 相似度：", end=" ")
        sims = [f"{1.0/(1.0+d):.3f}" for d in raw["distances"][0]]
        print(", ".join(sims))

    print()

    # RAG 回答对比
    print(f"     📝 Day 11 参数回答：")
    ans11 = rag_ask(day11_col, question)
    for line in ans11.split("\n")[:5]:  # 只展示前5行
        print(f"       {line}")
    if len(ans11.split("\n")) > 5:
        print(f"       ...（截断）")

    print(f"\n     📝 Day 12 最优参数回答：")
    ans12 = rag_ask(best_col, question)
    for line in ans12.split("\n")[:5]:
        print(f"       {line}")
    if len(ans12.split("\n")) > 5:
        print(f"       ...（截断）")
    print()


# ============================================================
# 实验 6：调优方法论总结 — 面试官想听什么
# ============================================================
print("=" * 60)
print("实验 6：RAG 检索调优方法论")
print("=" * 60)
print("""
┌─────────────────────────────────────────────────────────────────┐
│               RAG 检索调优的系统方法论                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Step 1：建立评估基准（Benchmark）                                │
│    - 准备 10-20 个覆盖各种类型的测试问题                          │
│    - 标注每个问题的「理想答案」或「关键词」                        │
│    - 包含干扰问题（知识库中没有答案的）                            │
│                                                                 │
│  Step 2：单一变量实验                                            │
│    - 固定其他参数，只变一个                                       │
│    - chunk_size：测 200/400/600/800                              │
│    - overlap：测 0/10%/20%/30% of chunk_size                    │
│    - 相似度阈值：测 0.0/0.2/0.3/0.4/0.5                          │
│    - top_k：测 3/5/7/10                                         │
│                                                                 │
│  Step 3：多维指标评估                                            │
│    - Hit@K：正确答案是否在结果中（最直观）                        │
│    - MRR：正确答案排名越高越好（考虑排序质量）                     │
│    - 平均相似度：检索结果的质量置信度                             │
│                                                                 │
│  Step 4：组合最优参数                                            │
│    - 把各维度最优值组合                                           │
│    - 与基线参数做 A/B 对比                                        │
│    - 用实际 RAG 回答质量做最终验证（而不只看检索指标）            │
│                                                                 │
│  Step 5：持续迭代                                                │
│    - 新文档加入后重新评估                                         │
│    - 收集用户反馈（赞/踩），标记差答案的检索结果                   │
│    - 不同类型文档可能需要不同参数                                 │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  🎤 面试话术：                                                   │
│                                                                 │
│  "我们建立了一套系统的评估方法：准备覆盖事实型、概念型和           │
│   干扰型的测试问题集，用 Hit@K 和 MRR 做定量指标。                │
│   通过单一变量对照实验找到最优参数组合，再和基线做 A/B 对比。     │
│   最终 chunk_size 选 X，overlap 选 Y，在测试集上 Hit@5 达到 Z%，  │
│   比默认参数提升了 W%。"                                          │
│                                                                 │
│  这比你只说"我用了 chunk_size=400"有力 10 倍。                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
""")


# ============================================================
# 实验 7：进阶技巧 — 混合检索 + 重排序（概念预览）
# ============================================================
print("=" * 60)
print("实验 7：进阶调优方向（Preview——Day 15+ 会深入）")
print("=" * 60)
print("""
调完基础参数后，还有三个进阶方向可以进一步提升检索质量：

  ① 混合检索（Hybrid Search）
     ─────────────────────────
     语义检索（Embedding）的盲区：对专有名词、数字、代码等不敏感。
     关键词检索（BM25）的盲区：同义词、改写、跨语言。
     → 最佳方案：同时跑两种检索，融合排序
     → 技术栈：BM25（rank_bm25）+ Embedding + RRF（Reciprocal Rank Fusion）

  ② 重排序（Re-ranking）
     ────────────────────
     先用 Embedding 粗召回 Top-20（快），再用更精准的模型精排 Top-5（准）。
     → 两阶段检索：粗排（高召回）+ 精排（高精确）
     → 技术栈：Cohere Rerank / bge-reranker / Cross-Encoder

  ③ 查询重写（Query Rewriting）
     ──────────────────────────
     用户的输入可能很口语化、不完整、指代不明。
     → 用 LLM 先改写/扩展用户问题，再拿去检索
     → 例子："上次那个怎么配？" → "Streamlit session_state 如何配置？"

  ④ 元数据过滤（Metadata Filtering）
     ────────────────────────────
     按时间、来源、类型等元数据缩小检索范围。
     → "只搜索 2026 年 7 月的文档"→ 先过滤再检索，精准度大幅提升
     → Chroma 原生支持 where 条件过滤

  这些是 Day 15+ Agent 部分会深入的内容。今天先建立参数调优的底层能力。
""")


# ============================================================
# 实验 8：你的调优参数备忘
# ============================================================
print("=" * 60)
print("实验 8：你的调优参数备忘")
print("=" * 60)

print(f"""
  ╔════════════════════════════════════════════════════════════╗
  ║           🎯 Day 12 最优参数（基于你的数据）               ║
  ╠════════════════════════════════════════════════════════════╣
  ║                                                            ║
  ║   chunk_size       = {OPTIMAL_CS:<5}                                  ║
  ║   overlap          = {best_ov:<5}                                  ║
  ║   相似度阈值        = 0.2   （推荐起始值）                   ║
  ║   top_k            = 5     （检索数量）                     ║
  ║                                                            ║
  ║   评估指标：                                                ║
  ║   Hit@5  = {cs_results[OPTIMAL_CS]['hit_at_k']:.1%}                                     ║
  ║   MRR    = {cs_results[OPTIMAL_CS]['mrr']:.4f}                                     ║
  ║   知识库 = {best_col.count()} chunks                                  ║
  ║                                                            ║
  ╠════════════════════════════════════════════════════════════╣
  ║                                                            ║
  ║  📋 调优口诀：                                              ║
  ║  ① chunk_size：让每个 chunk 表达一个完整概念                ║
  ║  ② overlap：10-15% 保边界安全，不做冗余                     ║
  ║  ③ 相似度阈值：从 0.2 出发，观察答案质量微调                ║
  ║  ④ 永远用数据说话：跑实验、看指标、做 A/B 对比              ║
  ║                                                            ║
  ╚════════════════════════════════════════════════════════════╝
""")


# ============================================================
# Day 12 总结
# ============================================================
print(f"""
╔══════════════════════════════════════════════════════════════════╗
║                      📝 Day 12 总结                              ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  今天你用实验驱动的方式，系统性地调优了 RAG 检索质量：            ║
║                                                                  ║
║  ① chunk_size 对照实验（{CHUNK_SIZES[0]}/{CHUNK_SIZES[1]}/{CHUNK_SIZES[2]}/{CHUNK_SIZES[3]}）→ 最优 = {OPTIMAL_CS}                         ║
║  ② overlap 对照实验（{OVERLAP_VALUES[0]}/{OVERLAP_VALUES[1]}/{OVERLAP_VALUES[2]}/{OVERLAP_VALUES[3]}）  → 最优 = {best_ov}                         ║
║  ③ 相似度阈值实验（{', '.join(str(t) for t in SIM_THRESHOLDS)}）→ 推荐 = 0.2                       ║
║  ④ 最优参数 vs Day 11 基线 A/B 对比                               ║
║  ⑤ 建立了 Hit@K + MRR 的评估体系                                  ║
║                                                                  ║
║  🔑 三个关键认知：                                                ║
║  1. RAG 调参不是玄学 — 是建立「假设→实验→指标→结论」的闭环       ║
║  2. 没有万能参数 — 不同类型文档的最优参数不同                     ║
║  3. 评估方法是核心能力 — 面试官想听的是你怎么找到参数的           ║
║                                                                  ║
║  🎯 你现在的能力：                                                ║
║  - 能对 RAG 检索做系统性的参数调优                                ║
║  - 能用 Hit@K / MRR 量化评估检索质量                              ║
║  - 能设计对照实验来验证优化效果                                    ║
║  - 能说出 chunk_size/overlap/相似度阈值的最优选择依据             ║
║                                                                  ║
║  🔜 Day 13 预告：用 Streamlit 把 RAG 做成 Web 界面               ║
║  上传文档 → 提问 → 流式回答 + 原文溯源                            ║
║  ⭐ 完成 Week 2 的核心产出：私有文档问答系统                       ║
║                                                                  ║
║  📊 学习进度：Week 2 ████████████░ 86%                            ║
║  已完成：Day 1─12 / 30    今天：RAG 检索质量调优 ✅               ║
╚══════════════════════════════════════════════════════════════════╝
""")
