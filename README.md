# 🤖 AI 应用开发 30 天冲刺

> 从零到 AI 应用开发工程师 — 一个月系统学习 LLM API → RAG → Agent → 全栈部署

**技术栈**：Python · OpenAI SDK · DeepSeek / 通义千问 · Streamlit · LangChain · Chroma · FastAPI

---

## 📊 Week 1 成果：AI 简历分析器

第一个完整 AI 应用：输入 JD + 简历，AI 输出匹配度评分 + 逐项技能对照 + 改进建议。

```
┌─────────────────────────────────────────────────┐
│  📊 AI 简历分析器                                │
│  ┌──────────────┐  ┌──────────────┐             │
│  │  📋 JD       │  │  📝 简历     │             │
│  │              │  │              │             │
│  └──────────────┘  └──────────────┘             │
│         🔍 开始分析                               │
│  ┌─────────────────────────────────────────┐    │
│  │  🟢 匹配度：78/100  |  强匹配            │    │
│  │  ✅ Python  ✅ Django  ⚠️ Redis  ❌ CI/CD│    │
│  │  💪 优势  ⚠️ 差距  🎯 改进建议          │    │
│  └─────────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
```

### 快速启动

```bash
# 1. 克隆 + 安装依赖
git clone https://github.com/YOUR_USERNAME/ai-learning.git
cd ai-learning
pip install -r requirements.txt

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env，填入你的百炼/DeepSeek API Key

# 3. 运行简历分析器（Web 版）
streamlit run day6_streamlit_app.py

# 4. 或运行 CLI 版
python day4_resume_analyzer.py --demo
```

---

## 📁 项目结构

```
ai-learning/
├── README.md                       # 项目主页
├── requirements.txt                # Python 依赖
├── .env.example                    # API Key 模板（复制为 .env）
├── .gitignore                      # 排除敏感文件和临时文件
│
├── config.py                       # 🔧 全局配置（从 .env 读 Key）
├── ai_utils.py                     # 🔧 可复用工具模块（重试/流式/异常处理）
│
├── hello_ai.py                     # Day 1 — DeepSeek API 初体验
├── hello_ai_bailian.py             # Day 1 — 百炼 API 初体验
├── day2_conversation.py            # Day 2 — 多轮对话 + Token/Temperature
├── day3_prompt_engineering.py      # Day 3 — Prompt 工程（JSON/CoT）
├── day4_resume_analyzer.py         # Day 4 — AI 简历分析器 CLI 版 ⭐
├── day5_streaming_robustness.py    # Day 5 — 流式输出 + 重试 + 异常处理
├── day6_streamlit_app.py           # Day 6 — Streamlit Web 版 ⭐
│
├── day8_rag_intro.py               # Day 8 — RAG 入门（全流程 + 示例）
├── day9_document_loader.py         # Day 9 — 文档加载 & 文本切割实战
├── day10_embedding_chroma.py       # Day 10 — Embedding 深入 + Chroma 持久化
│
├── data/
│   ├── ai_knowledge_base.txt       # 知识库文档（TXT）
│   └── sample_ai_guide.pdf         # 示例 PDF 文档
│
├── docs/
│   └── week1-review.md             # Week 1 复盘文档
│
└── ai-learning-roadmap.md          # 30 天学习路线图
```

---

## 🗓️ 学习进度

### ✅ Week 1：打通 API，建立手感（7/2 — 7/4）

| 天 | 内容 | 技能 | 产出 |
|----|------|------|------|
| Day 1 | API 调用入门 | OpenAI SDK 双平台调用 | `hello_ai.py` |
| Day 2 | 核心概念 | Token/Temperature/多轮对话 | `day2_conversation.py` |
| Day 3 | Prompt 工程 | JSON 输出 + 思维链 CoT | `day3_prompt_engineering.py` |
| Day 4 | 简历分析器 CLI | 第一个 AI 应用 | `day4_resume_analyzer.py` ⭐ |
| Day 5 | 生产级代码 | 流式/重试/异常处理 | `ai_utils.py` |
| Day 6 | Web 界面 | Streamlit | `day6_streamlit_app.py` ⭐ |
| Day 7 | 复盘 + GitHub | 代码整理 + 发布 | 本仓库 🎉 |

### 🔜 Week 2：RAG 私有文档问答系统（7/4 — 7/11）

> LangChain + Chroma + DeepSeek → 上传 PDF，AI 基于文档回答，标注来源

| 天 | 内容 | 技能 | 产出 |
|----|------|------|------|
| Day 8 | RAG 入门 | 全流程概念 + 端到端示例 | `day8_rag_intro.py` |
| Day 9 | 文档加载 | PDF/TXT 加载 + 文本切割 | `day9_document_loader.py` |
| Day 10 | 向量嵌入 | Embedding + Chroma 持久化 | `day10_embedding_chroma.py` |
| Day 11 | RAG 闭环 | 检索 + 生成 + 溯源 | ⏳ |
| Day 12 | 检索优化 | chunk_size/overlap 调参 | ⏳ |
| Day 13 | Web 界面 | Streamlit RAG 应用 | ⏳ |
| Day 14 | 复盘 | Week 2 代码整理 | ⏳ |

### 🔜 Week 3：AI Agent 助手（7/12 — 7/18）

> Function Calling + 多工具串联 → Agent 自主搜索网页、执行计算、查询知识库

### 🔜 Week 4：全栈整合部署（7/19 — 7/25）

> FastAPI + Streamlit + 部署上线 → 有公网链接的完整 AI 产品

---

## 🛠️ 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| LLM | 通义千问（百炼）/ DeepSeek | AI 推理引擎 |
| SDK | OpenAI Python SDK | 统一 API 调用接口 |
| UI | Streamlit | 纯 Python Web 界面 |
| 配置 | python-dotenv | 环境变量管理 |
| RAG 框架 | LangChain | 文档加载 + 切割 + 检索链 |
| 向量库 | Chroma | 本地向量存储（内存模式） |
| 后端 | FastAPI | API 化部署 |
| 部署 | HuggingFace Spaces | 免费公网部署 |

---

## 🎯 学习策略

**不做的事**：
- ❌ 啃深度学习数学（反向传播、梯度下降）
- ❌ 从头训练模型（PyTorch / TensorFlow）
- ❌ 学前端框架（React / Vue）
- ❌ 本地部署开源大模型

**只做的事**：
- ✅ 调 API → 搭 RAG → 做 Agent → 出作品

---

## 👤 关于我

- **黄畅** · 嘉应学院软件工程 2027 届
- 求职方向：AI 应用开发工程师（实习/应届）
- 技术栈：Python · Django · MySQL · Docker · Git

---

> 📌 这个仓库记录了我从零开始学习 AI 应用开发的完整过程。每个 `.py` 文件都可以独立运行，按天数递增展示了技能的逐层叠加。
>
> 如果你也是 AI 初学者，建议按 Day 1 → Day 7 的顺序阅读代码，每天的文件头部都有详细的学习笔记。
