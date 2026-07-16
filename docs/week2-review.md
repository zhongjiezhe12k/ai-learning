# Week 2 复盘：RAG 私有文档 AI 问答系统

> 时间：2026 年 7 月 4 日 — 7 月 8 日
> 目标：从零掌握 RAG（检索增强生成），建成可部署的私有文档 AI 问答系统

---

## 🎯 本周目标 vs 完成情况

| 目标 | 状态 |
|------|------|
| 理解 RAG 全流程架构（Load → Split → Embed → Store → Retrieve+Generate） | ✅ |
| 用 LangChain 加载 PDF/TXT 并切割文档 | ✅ |
| 掌握 Embedding 概念 + Chroma 向量数据库持久化存储 | ✅ |
| 跑通 RAG 核心闭环：检索 + 上下文拼接 + LLM 生成 | ✅ |
| 检索质量调优：chunk_size / overlap / 相似度阈值 | ✅ |
| 用 Streamlit 做成 Web 界面（上传文档 → 提问 → 溯源） | ✅ |
| 周末复盘 + GitHub 发布 | ✅ |

**🎯 Week 2 产出：** 私有文档 AI 问答系统（上传任意 PDF/TXT → AI 基于文档内容回答 + 标注原文来源）

---

## 📅 每日回顾

### Day 8 — RAG 入门：全流程概念 + 最简示例

**产出**：[`day8_rag_intro.py`](../day8_rag_intro.py)（509 行）

**学到的**：
- **RAG 五步流程**：Load（加载文档）→ Split（切割成 chunk）→ Embed（向量嵌入）→ Store（存储到向量库）→ Retrieve + Generate（检索 + LLM 生成）
- **为什么需要 RAG**：LLM 的知识截止日期 + 不会私域知识 + 幻觉问题 → RAG 把"检索"和"生成"结合，让 AI 基于真实文档回答
- 搭建了最简单的 RAG 演示流程，用 `heapq` 手动实现文本相似度搜索

**关键认知**：
- RAG 不是什么高深技术——就是"先搜索，再回答"。搜索部分用向量相似度，回答部分跟 Day 1 调 API 一模一样
- 从这里开始，代码不再是"玩具脚本"级别——每次实验都建了专门的测试文档

---

### Day 9 — 文档加载 & 文本切割实战

**产出**：[`day9_document_loader.py`](../day9_document_loader.py)（372 行）

**学到的三大技能**：

1. **LangChain Document Loaders**
   - `TextLoader` → 加载 TXT 文件（注意 encoding 坑：默认 utf-8）
   - `PyPDFLoader` → 加载 PDF（每页独立成一个 Document）
   - `DirectoryLoader` → 批量加载整个目录（`glob="**/*.txt"`）

2. **文本切割策略**
   - `RecursiveCharacterTextSplitter` 的核心参数：
     - `chunk_size` — 每个块的大小（字符数）
     - `chunk_overlap` — 相邻块的重叠字符数
   - 切割器按优先级依次尝试分隔符：`\n\n` → `\n` → `。` → `.` → ` ` → 逐字切割
   - LangChain 的 `Document` 对象包含 `page_content`（文本）+ `metadata`（来源信息）

3. **切割质量的直观验证**
   - 打印每个 chunk 的头部和尾部，验证"语义边界"有没有被切断
   - overlap 的意义：防止关键信息正好落在两个 chunk 的边界上被割裂

**踩坑**：
- PDF 加载后的文本可能包含大量空白和换行，需要留意
- `PyPDFLoader` 对扫描版 PDF（图片）无效——只能识别文字型 PDF

---

### Day 10 — Embedding 深入 + Chroma 持久化存储

**产出**：[`day10_embedding_chroma.py`](../day10_embedding_chroma.py)（848 行）

**这是本周信息密度最高的一天**——从"概念理解"跨入"工程落地"：

1. **Embedding 本质理解**
   - Embedding = 把文本转换成高维向量（我用的 `text-embedding-v2` 是 1536 维）
   - 语义相近的文本 → 向量空间中距离近；语义无关 → 距离远
   - 验证方法：用余弦距离计算 `猫 vs 狗`（应该近）vs `猫 vs 电脑`（应该远）

2. **Chroma 向量数据库**
   - `chromadb.Client()` — 内存模式（临时，关程序就丢）
   - `chromadb.PersistentClient(path="./chroma_db")` — **持久化模式**（存磁盘，重启不丢）⭐
   - Collection 的组织方式：add/query/get/delete

3. **持久化存储的坑**
   - 第一次写的代码有个致命 bug：每次运行时调了 `delete_collection` + `create_collection`，导致之前存的向量全丢了
   - 正确做法：启动时先 `get_collection`，存在就直接用；不存在才新建
   - **这个 bug 面试时讲出来特别加分**——说明你理解"数据库初始化"和"数据库重置"的区别

4. **验证检索效果**
   - 用已知的知识库文档做"冒烟测试"：搜几个关键词，看返回的内容是否相关
   - 发现了相似度阈值的问题（0.3 太严 → Day 12 解决）

---

### Day 11 — RAG 核心闭环：检索 + 上下文拼接 + LLM 生成

**产出**：[`day11_rag_pipeline.py`](../day11_rag_pipeline.py)（876 行）

**RAG 的灵魂环节——把前三天搭的积木串成一条完整流水线**：

1. **RAG Prompt 设计精髓**
   ```
   System: 你是一个严谨的知识库助手，严格根据提供参考资料回答。
           资料里没有的就说不知道。引用资料编号标注来源。
   User:   【参考资料】
           [资料1]（来源：xxx.pdf，相似度 0.87）...
           [资料2]（来源：xxx.pdf，相似度 0.82）...
           ...
           【用户问题】...
   ```
   - **关键设计点**：明确说"资料中没有就如实说明" → 对抗幻觉
   - 让 AI 标注 `[资料1]` → 可溯源，用户能回头验证

2. **上下文窗口管理（Token 预算分配）**
   - 不是把检索结果全塞进去——要考虑 LLM 的上下文限制
   - 实现了一个智能拼接器：估算 token 数 → 分配给检索结果和回答 → 超限就截断

3. **对比实验：RAG ON vs OFF**
   - 同一个问题分别发给 RAG 模式和纯 LLM 模式
   - 差距肉眼可见：RAG 回答有具体章节引用 + 精确数据；纯 LLM 回答模糊、泛泛而谈

4. **流式 RAG 回答**
   - `stream=True` + 逐 token yield → 打字机效果
   - 来源标注在答案生成完毕后统一展示

5. **完整 RAG 问答引擎封装**
   - `RAGEngine` 类：初始化知识库 + 问答 + 流式问答
   - 这是第一个**可以直接复用的 RAG 核心模块**

**核心认知**：
```
RAG ≠ 搜索 + LLM 拼接字符串
RAG = 精心设计的 Prompt + 检索质量控制 + 上下文窗口管理 + 来源溯源
```

面试官不会问"你用过 RAG 吗"——他们会问"你的 RAG Prompt 怎么设计才能抑制幻觉？""你怎么管理 token 预算？"

---

### Day 12 — RAG 检索质量调优

**产出**：[`day12_retrieval_tuning.py`](../day12_retrieval_tuning.py)（962 行）

**从"能用"到"好用"——建立参数调优的系统方法论**：

1. **chunk_size 对检索质量的影响**
   - 太小（100-200）：信息碎片化，丢失上下文，搜"深圳 GDP"可能只返回"深圳是..."没提到 GDP
   - 太大（800-1000）：语义稀释，一个 chunk 包含太多无关内容给 LLM 造成干扰
   - 最佳区间：**400-600**（中文文档），在这个区间内精确率和召回率平衡最好

2. **overlap 的权衡**
   - 太小：关键句被切断在两个 chunk 里 → 搜不到
   - 太大：冗余存储，同一个句子出现在多个 chunk 中 → 检索结果重复
   - 经验值：**chunk_size 的 10-15%**（如 400 × 15% = 60）

3. **相似度阈值的精确率 vs 召回率博弈**
   - 阈值高（>0.5）：只看最相关的，但可能漏掉有用的 → 精确率高，召回率低
   - 阈值低（<0.1）：什么都返回，但混入噪声 → 召回率高，精确率低
   - 找到了"甜点区间"：**0.15-0.25**，根据文档类型微调

4. **建立了检索质量评估方法**
   - **Hit@K**：前 K 个结果中至少有 1 个相关的比例
   - **MRR**（Mean Reciprocal Rank）：第一个相关结果排名的倒数均值
   - **平均相似度**：快速识别"搜索结果整体太远"的问题

5. **参数搜索实验**
   - 网格搜索：`chunk_size ∈ [200,400,600,800]` × `overlap ∈ [30,60,90]`
   - 用 Hit@K 和 MRR 打分 → 找到最优参数组合
   - 产出了 **RAG 参数调优的标准流程**（假设 → 实验 → 指标 → 结论）

**面试时最亮眼的回答**：
> "我们的 chunk_size 不是拍脑袋定的。我们做了网格搜索，用 Hit@5 和 MRR 做评估指标，在 12 组参数组合中找到了这个数据集的最优配置。"

---

### Day 13 — Streamlit RAG Web 界面 ⭐

**产出**：[`day13_rag_webapp.py`](../day13_rag_webapp.py)（614 行）

**Week 2 的核心产出——一个完整可部署的 Web 应用**：

1. **应用架构**
   ```
   侧边栏：文档上传 + 参数控制 + 知识库状态面板
   主区域：聊天对话界面 + 原文溯源 + 流式回答
   ```

2. **关键技术实现**
   - **Session State 管理**：Chroma client、collection、聊天记录、已处理文件 → 全部存在 `st.session_state`
   - **文件上传管道**：`st.file_uploader` → 临时文件 → LangChain Loader → 切割 → 向量化 → Chroma
   - **流式 RAG 回答**：yield-based 生成器 + `st.empty()` 占位符逐 token 渲染
   - **来源溯源 UI**：`st.expander` 折叠展示每条资料的完整文本 + 来源文件名 + 相似度分数

3. **用户体验设计**
   - 知识库持久化：重启 Streamlit 不需要重新上传文档
   - 首页引导提示：分步骤告诉用户怎么用
   - 底部状态栏：知识库状态 / 对话轮次 / 模型信息
   - 可调参数：chunk_size / overlap / top_k / 相似度阈值

**启动命令**：`streamlit run day13_rag_webapp.py`

---

## 🔗 技能图谱：六天如何串成一条完整 RAG 系统

```
Day 8: RAG 概念 + 最简示例
  ↓ 知道 RAG 是什么，但不知道每步怎么做
Day 9: 文档加载 + 文本切割
  ↓ 能把 PDF/TXT 变成结构化的小块
Day 10: Embedding + Chroma 持久化
  ↓ 能把文本向量化存起来 + 重启不丢
Day 11: 检索 + 上下文拼接 + LLM 生成
  ↓ 完整 RAG 问答闭环跑通 🎉
Day 12: 检索质量调优
  ↓ 从"能用"到"好用"，有数据支持的最优参数
Day 13: Streamlit Web 界面
  ↓ 从命令行脚本到可部署的 Web 应用 🚀
```

### 技术栈层次

```
┌─────────────────────────────────────────┐
│  Web 层    │ Streamlit (Day 13)         │  ← 用户交互
├─────────────────────────────────────────┤
│  编排层    │ RAG Engine (Day 11)        │  ← 检索+生成的编排逻辑
├─────────────────────────────────────────┤
│  检索层    │ Chroma Query (Day 10)      │  ← 语义检索
├─────────────────────────────────────────┤
│  存储层    │ Chroma Persist (Day 10)    │  ← 向量持久化
├─────────────────────────────────────────┤
│  Embedding │ text-embedding-v2 (Day 10) │  ← 文本 → 向量
├─────────────────────────────────────────┤
│  加载层    │ LangChain Loaders (Day 9)  │  ← PDF/TXT → Document
├─────────────────────────────────────────┤
│  切割层    │ TextSplitter (Day 9)        │  ← Document → Chunk
├─────────────────────────────────────────┤
│  LLM 层    │ 通义千问 qwen-plus (全部)  │  ← 生成答案
└─────────────────────────────────────────┘
```

---

## 🛠️ 本周技术栈

| 层级 | 技术 | 掌握程度 |
|------|------|----------|
| LLM API | 通义千问 qwen-plus（文本生成 + Embedding） | 🟢 熟练 |
| RAG 框架 | LangChain（Document Loader + TextSplitter） | 🟢 熟练 |
| 向量数据库 | Chroma（PersistentClient + Collection API） | 🟢 熟练 |
| Embedding | text-embedding-v2（1536 维） | 🟢 熟练 |
| UI | Streamlit（chat_message + session_state + expander） | 🟢 熟练 |
| 评估方法 | Hit@K / MRR / 平均相似度 | 🟡 会用 |
| 参数调优 | 网格搜索 + 指标对比 | 🟡 会用 |

---

## ⚠️ 本周踩过的坑

| 坑 | 怎么解决的 |
|----|-----------|
| 每次启动重复建 Chroma collection → 旧数据全丢 | Day 10 修复：先 `get_collection`，存在就不新建 |
| `min_similarity=0.3` 太严导致搜不到结果 | Day 12 修复：降到 0.2，用评估指标验证 |
| PDF 加载后有大量空白和换行符 | 用 `RecursiveCharacterTextSplitter` 的分隔符链自动清理 |
| Embedding API 调用限流（单次太多文本） | 分批调用，每批 20 个 chunk |
| LangChain `get_collection` 的坑：不存在的 collection 会抛异常 | `try/except` 兜底，失败就建新的 |
| Streamlit 的 reactive 模型——点按钮整个脚本重跑 | 把持久化对象放在 `session_state` 里 |
| `PyPDFLoader` 对非文字型 PDF 无效 | 文档开头标注「仅支持文字型 PDF」 |

---

## 💡 Week 2 核心方法论

### RAG 开发的最佳实践

1. **先跑通再优化**（Day 8-11：搭骨架 → Day 12：调参数）
2. **用评估指标说话**——不要凭感觉调参，设计实验 + 对比指标
3. **Prompt 是 RAG 的灵魂**——检索结果再好，Prompt 不好也白搭
4. **持久化 vs 重置是两件事**——启动时检查已有数据，不要无脑重建
5. **流式输出是用户体验的分水岭**——从"干等 3 秒"到"逐字蹦出"

### 面试可以这样讲

> "我独立完成了一个基于 RAG 的私有文档问答系统。技术栈是 LangChain + Chroma + 通义千问。系统支持 PDF 和 TXT 文件上传，用 RecursiveCharacterTextSplitter 做中文语义切割，通过 text-embedding-v2 向量化后存入 Chroma 持久化存储。我做了网格搜索来调优 chunk_size 和 overlap 参数，用 Hit@5 和 MRR 做评估指标。前端用 Streamlit 实现，支持流式 RAG 回答和原文溯源。整个系统约 4000 行 Python 代码。"

---

## 🔜 Week 3 展望：AI Agent 助手

接下来要学的是 Agent——让 AI 不仅回答问题，还能主动使用工具：

```
用户提需求 → Agent 规划步骤 → Function Calling 调用工具 → 综合结果
                                  ↓
                        搜索网页 / 执行代码 / 查知识库 / ...
```

**关键技能预览**：
- Function Calling（让 LLM 调用你定义的函数）
- 多工具串联（Agent 自主决定用哪个工具、顺序）
- Agent + RAG 结合（既能查知识库，又能搜索外部信息）
- Streamlit Agent 可视化（看到 Agent 每一步的思考和决策）

---

> 📝 复盘日期：2026-07-08（实际学习） → 2026-07-16（复盘文档整理）
> 🎯 Week 2 产出：RAG 私有文档 AI 问答系统（4181 行代码），支持上传 PDF/TXT → 语义检索 → AI 回答 + 原文溯源
> 📊 两周累计：10,000+ 行代码 | 2 个完整 AI 项目 | 1 个可复用工具库
