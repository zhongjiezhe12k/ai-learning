"""
Day 9 - 文档加载 & 文本切割实战
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Day 8 用了内存中的假文档。今天用「真文档」—— PDF + TXT，
并深入理解文本切割的各种策略。

学完今天你会：
  ✅ 用 LangChain 加载 PDF、TXT 文件
  ✅ 理解不同切割器的适用场景
  ✅ 调 chunk_size 和 chunk_overlap 看效果
  ✅ 写出一个可复用的文档处理函数
"""

import sys, os
sys.stdout.reconfigure(encoding='utf-8')

from langchain_community.document_loaders import (
    TextLoader,
    PyPDFLoader,
    DirectoryLoader,
)
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    CharacterTextSplitter,
)

# ============================================================
# 实验 1：加载 TXT 文件
# ============================================================
print("=" * 60)
print("实验 1：加载 TXT 文件")
print("=" * 60)

txt_path = "data/ai_knowledge_base.txt"
if os.path.exists(txt_path):
    loader = TextLoader(txt_path, encoding="utf-8")
    txt_docs = loader.load()

    print(f"\n文件：{txt_path}")
    print(f"加载了 {len(txt_docs)} 个 Document 对象")
    print(f"总字符数：{len(txt_docs[0].page_content)}")
    print(f"元数据：{txt_docs[0].metadata}")
    print(f"\n前 200 字符预览：")
    print(txt_docs[0].page_content[:200])
    print("\n📌 TextLoader 最简单，加载 TXT 文件返回一个 Document。")
else:
    print(f"文件不存在：{txt_path}")
    txt_docs = []


# ============================================================
# 实验 2：加载 PDF 文件
# ============================================================
print("\n" + "=" * 60)
print("实验 2：加载 PDF 文件")
print("=" * 60)

pdf_path = "data/sample_ai_guide.pdf"
if os.path.exists(pdf_path):
    loader = PyPDFLoader(pdf_path)
    pdf_docs = loader.load()

    print(f"\n文件：{pdf_path}")
    print(f"加载了 {len(pdf_docs)} 个 Document 对象（每页一个）")
    print(f"总字符数：{sum(len(d.page_content) for d in pdf_docs)}")

    for i, doc in enumerate(pdf_docs):
        content = doc.page_content.strip()
        print(f"\n  第 {i+1} 页 ({len(content)} 字符)：{content[:100]}...")

    print("""
📌 PyPDFLoader：
   - 每页 PDF 返回一个独立的 Document 对象
   - PDF 中的图片、表格无法提取（需要 OCR 或专用工具）
   - 部分 PDF 可能提取出乱码（扫描件、加密文件）
""")
else:
    print(f"文件不存在：{pdf_path}（PDF 加载演示跳过）")
    pdf_docs = []


# ============================================================
# 实验 3：DirectoryLoader —— 批量加载整个目录
# ============================================================
print("=" * 60)
print("实验 3：批量加载目录（DirectoryLoader）")
print("=" * 60)

data_dir = "data"
if os.path.isdir(data_dir):
    # 加载目录下所有 TXT 文件
    txt_loader = DirectoryLoader(
        data_dir,
        glob="**/*.txt",        # 匹配所有 txt 文件
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
        show_progress=False,
    )
    all_txt_docs = txt_loader.load()

    print(f"\n目录 {data_dir}/ 下有 {len(all_txt_docs)} 个 txt 文档")

    # 加载目录下所有 PDF 文件
    pdf_loader = DirectoryLoader(
        data_dir,
        glob="**/*.pdf",
        loader_cls=PyPDFLoader,
        show_progress=False,
    )
    all_pdf_docs = pdf_loader.load()
    print(f"目录 {data_dir}/ 下有 {len(all_pdf_docs)} 页 PDF（每页算一个 Document）")

    # 合并所有文档
    all_docs = all_txt_docs + all_pdf_docs
    total_chars = sum(len(d.page_content) for d in all_docs)
    print(f"\n📊 合计：{len(all_docs)} 个 Document，{total_chars} 个字符")

    print("""
📌 DirectoryLoader：
   - glob 参数用通配符过滤文件（**/*.txt 匹配所有子目录下的 txt）
   - 可以同时加载多种文件类型
   - 适合构建「知识库导入」功能
""")
else:
    all_docs = txt_docs + pdf_docs


# ============================================================
# 实验 4：文本切割 —— 三种切割器对比
# ============================================================
print("=" * 60)
print("实验 4：三种文本切割器对比")
print("=" * 60)
print("""
切割是 RAG 最关键的一步。切得好不好直接影响检索质量。

三种常见切割器：
  1. CharacterTextSplitter      → 按固定字符数切，最简单
  2. RecursiveCharacterTextSplitter → 按优先级分隔符切，最常用 ⭐
  3. MarkdownHeaderTextSplitter → 按标题层级切，适合结构化文档
""")

# 用同一个示例文本，看三种切割器的效果
sample_text = """# 第一章：Python 基础

Python 是一门解释型、面向对象的高级编程语言。
它由 Guido van Rossum 于 1991 年发布。

## 1.1 变量和类型

Python 是动态类型语言，变量不需要声明类型。
常见数据类型：int、float、str、list、tuple、dict。

## 1.2 函数定义

使用 def 关键字定义函数：
def greet(name):
    return f"Hello, {name}!"

## 1.3 面向对象

Python 支持类和继承。
class Animal:
    def __init__(self, name):
        self.name = name"""

print("\n示例文本：")
print(sample_text[:150] + "...")
print()

# ── 4.1 CharacterTextSplitter ──
print("─" * 40)
print("4.1 CharacterTextSplitter（按固定字符数切）")
print("─" * 40)

char_splitter = CharacterTextSplitter(
    chunk_size=100,
    chunk_overlap=0,
    separator="",   # 不关心分隔符，就是每 100 个字符切一刀
)
char_chunks = char_splitter.split_text(sample_text)
for i, chunk in enumerate(char_chunks):
    print(f"  块{i+1} ({len(chunk)}字)：{chunk[:60]}...")
print(f"\n  ⚠️ 问题：在第 2 块，一句话被拦腰切断：'常见数据类型' 本来是一句完整的话。")

# ── 4.2 RecursiveCharacterTextSplitter ──
print("\n─" * 40)
print("4.2 RecursiveCharacterTextSplitter（推荐 ⭐）")
print("─" * 40)

recursive_splitter = RecursiveCharacterTextSplitter(
    chunk_size=120,
    chunk_overlap=20,
    separators=["\n\n", "\n", "## ", "# ", "。", ".", "，", ",", " ", ""],
    # 优先级：先尝试用段落分隔，再试句子分隔，最后才用空格
)
recursive_chunks = recursive_splitter.split_text(sample_text)
for i, chunk in enumerate(recursive_chunks):
    print(f"  块{i+1} ({len(chunk)}字)：{chunk[:80]}...")
print(f"\n  ✅ 切割点在 ## 标题处，保持了内容的完整性。")

# ── 4.3 两种切割器核心区别 ──
print("\n─" * 40)
print("4.3 三种切割器的选择指南")
print("─" * 40)
print("""
  CharacterTextSplitter:
    → 简单粗暴，固定字符数切一刀
    → 适合：纯文本流，对结构不敏感的文档
    → 不适合：有标题层级的结构化文档

  RecursiveCharacterTextSplitter（推荐）:
    → 按优先级找最合适的切割点
    → 先尝试段落分隔符 "\\n\\n"，不行再用句子分隔符 "。"
    → 适合：几乎所有场景，最通用 ⭐

  MarkdownHeaderTextSplitter:
    → 按 # / ## / ### 标题层级切分
    → 适合：技术文档、Wiki、API 文档
    → 每个 chunk 自带标题路径（如「第一章 > 1.1 变量和类型」）
""")


# ============================================================
# 实验 5：chunk_size 和 chunk_overlap 调参实验
# ============================================================
print("=" * 60)
print("实验 5：chunk_size vs chunk_overlap —— 调参实验")
print("=" * 60)
print("""
这是 RAG 系统最常调的两个参数。用同一个文档，看看不同参数的效果。
""")

if all_docs:
    test_doc = all_docs[0].page_content
else:
    test_doc = sample_text

print(f"测试文档总长度：{len(test_doc)} 字符\n")

configs = [
    {"chunk_size": 100, "chunk_overlap": 0,   "场景": "极小块，无重叠——检索精准但上下文不足"},
    {"chunk_size": 300, "chunk_overlap": 30,  "场景": "中等块，适当重叠——大多数场景推荐"},
    {"chunk_size": 500, "chunk_overlap": 80,  "场景": "大块，大重叠——适合需要完整段落的场景"},
    {"chunk_size": 800, "chunk_overlap": 0,   "场景": "大块，无重叠——块数少但可能切断关键信息"},
]

for cfg in configs:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=cfg["chunk_size"],
        chunk_overlap=cfg["chunk_overlap"],
        separators=["\n\n", "\n", "。", ".", "，", ",", " ", ""],
    )
    chunks = splitter.split_text(test_doc)
    avg_len = sum(len(c) for c in chunks) / len(chunks)
    print(f"  chunk_size={cfg['chunk_size']:>3}, overlap={cfg['chunk_overlap']:>2}  "
          f"→ {len(chunks):>2} 块, 平均 {avg_len:.0f} 字/块  | {cfg['场景']}")

print("""
📌 调参经验：
  - chunk_size 太小（<100）→ 块数爆炸，每块信息太少，检索到的内容不完整
  - chunk_size 太大（>1000）→ 检索不够精准，返回的块里混入无关内容
  - overlap 太小（<10% chunk_size）→ 关键信息可能刚好卡在两块之间
  - overlap 太大（>30% chunk_size）→ 浪费 embedding 调用，块之间重复太多
  - 起步推荐：chunk_size=400, overlap=50，然后根据效果调整
""")


# ============================================================
# 实验 6：实战 —— 封装一个可复用的文档处理函数
# ============================================================
print("=" * 60)
print("实验 6：实战 —— 封装文档处理器")
print("=" * 60)

import glob as glob_module

def load_and_split_directory(
    directory: str,
    chunk_size: int = 400,
    chunk_overlap: int = 50,
) -> list:
    """
    加载目录下所有支持的文档，切割成 chunk。

    参数：
      directory     : 文档目录路径
      chunk_size    : 每块最大字符数
      chunk_overlap : 相邻块重叠字符数

    返回：
      [(chunk_text, metadata_dict), ...]  每个 chunk 带元数据
    """
    all_documents = []

    # ── 加载 TXT ──
    txt_files = glob_module.glob(f"{directory}/**/*.txt", recursive=True)
    for f in txt_files:
        try:
            loader = TextLoader(f, encoding="utf-8")
            all_documents.extend(loader.load())
            print(f"  ✅ TXT: {f} ({len(all_documents[-1].page_content)} 字)")
        except Exception as e:
            print(f"  ❌ TXT 加载失败 {f}: {e}")

    # ── 加载 PDF ──
    pdf_files = glob_module.glob(f"{directory}/**/*.pdf", recursive=True)
    for f in pdf_files:
        try:
            loader = PyPDFLoader(f)
            docs = loader.load()
            all_documents.extend(docs)
            print(f"  ✅ PDF: {f} ({len(docs)} 页)")
        except Exception as e:
            print(f"  ❌ PDF 加载失败 {f}: {e}")

    if not all_documents:
        print("  ⚠️ 没有找到任何文档")
        return []

    # ── 切割 ──
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", ".", "，", ",", " ", ""],
    )

    all_chunks = splitter.split_documents(all_documents)

    print(f"\n  📊 总计：{len(all_documents)} 个原始 Document → {len(all_chunks)} 个 chunk")
    print(f"       chunk_size={chunk_size}, overlap={chunk_overlap}")

    # 转换为 (文本, 元数据) 的简单格式
    result = []
    for chunk in all_chunks:
        result.append({
            "text": chunk.page_content,
            "source": chunk.metadata.get("source", "unknown"),
            "page": chunk.metadata.get("page", None),
        })

    return result


# ── 测试 ──
print("\n测试 load_and_split_directory('data/'):\n")
chunks = load_and_split_directory("data", chunk_size=300, chunk_overlap=40)

if chunks:
    print(f"\n前 3 个 chunk 预览：")
    for i, chunk in enumerate(chunks[:3]):
        print(f"\n  Chunk {i+1} | 来源：{os.path.basename(chunk['source'])}")
        if chunk["page"] is not None:
            print(f"         | 第 {chunk['page']+1} 页")
        print(f"         | {chunk['text'][:120]}...")

print(f"""
{'=' * 60}
这个 load_and_split_directory() 就是你 RAG 系统的「入库模块」。
Day 10 会把这个函数的输出 → Embedding → Chroma，形成完整的文档入库流程。

📌 Day 9 核心收获：
  1. TextLoader     → TXT, Markdown, CSV 等纯文本文件
  2. PyPDFLoader    → PDF（每页一个 Document）
  3. DirectoryLoader → 批量加载整个目录
  4. RecursiveCharacterTextSplitter → 最通用的切割器
  5. chunk_size ~400, overlap ~50 → 起步推荐值

🔜 Day 10 预告：向量嵌入 + Chroma 持久化存储
  把今天切好的 chunk 全部向量化存入数据库，做一个真正的文档检索引擎
{'=' * 60}
""")
