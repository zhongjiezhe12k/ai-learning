# 🤖 AI Agent 全栈助手 — 从零到全栈 AI 应用

<div align="center">

**30 天 · 3 个项目 · 7,000+ 行代码**

[![Python](https://img.shields.io/badge/Python-3.13-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.139-green)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.50-red)](https://streamlit.io)
[![Chroma](https://img.shields.io/badge/Chroma-1.0-orange)](https://trychroma.com)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

</div>

---

## 📌 项目简介

一个具备 **5 个 AI 工具**、支持**多轮对话**、**自主编排**的智能助手全栈应用。Agent 能自动判断什么时候查知识库、什么时候搜网页、什么时候跑代码——就像一个真正的 AI 工程师。

```
你：对比 RAG 和 Agent 在 2026 年的最新发展，给出学习建议

Agent：→ 📚 知识库检索 "RAG基本原理"
      → 🔍 搜索 "2026 RAG最新发展"  
      → 🔍 搜索 "2026 Agent框架对比"
      → 🐍 Python 综合分析
      → ✅ 综合回答（标注来源：📚内部资料 + 🔍外部信息）
```

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     AI Agent 全栈助手                             │
│                                                                 │
│  ┌──────────────────┐         HTTP/SSE         ┌──────────────┐ │
│  │  Streamlit 前端   │ ◄─────────────────────► │ FastAPI 后端  │ │
│  │                  │                          │              │ │
│  │  💬 智能对话      │   POST /chat             │  Agent Loop  │ │
│  │  📊 工具调用可视化 │   POST /chat/stream      │  5 个 Tool   │ │
│  │  🔄 会话管理      │   POST /session/*        │  限流 + 日志  │ │
│  │  📚 知识库搜索    │   POST /knowledge/search │  15 个测试   │ │
│  │  🔍 网页搜索      │   POST /web/search       │              │ │
│  └──────────────────┘                          └──────┬───────┘ │
│                                                       │         │
│                                              ┌────────┴───────┐ │
│                                              │  工具层         │ │
│                                              │                │ │
│                                              │ 📚 知识库检索   │ │
│                                              │    Chroma 向量库 │ │
│                                              │    1536 维向量  │ │
│                                              │                │ │
│                                              │ 🔍 外部搜索     │ │
│                                              │    B站 API      │ │
│                                              │                │ │
│                                              │ 🐍 Python 执行  │ │
│                                              │    安全沙箱     │ │
│                                              │                │ │
│                                              │ 🔢 数学计算     │ │
│                                              │ 🕐 日期时间     │ │
│                                              └────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- 百炼 API Key（[免费注册](https://www.aliyun.com/product/bailian)）

### 安装运行

```bash
# 1. 克隆项目
git clone https://github.com/zhongjiezhe12k/ai-learning.git
cd ai-learning

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置 API Key
cp .env.example .env
# 编辑 .env，填入 BAILIAN_API_KEY=你的key

# 4. 启动后端
uvicorn day23_api_refinement:app --host 0.0.0.0 --port 8000

# 5. 新终端，启动前端
streamlit run day24_streamlit_frontend.py
```

打开 http://localhost:8501 即可使用。API 文档：http://localhost:8000/docs

---

## ⭐ 核心特性

### Agent 智能编排

| 场景 | Agent 行为 | 使用的工具 |
|------|-----------|-----------|
| 概念/原理/框架 | 查知识库 | 📚 knowledge_base_search |
| 最新新闻/趋势 | 搜网页 | 🔍 web_search |
| 数据分析/统计 | 写代码 | 🐍 python_repl |
| 数学计算 | 快速算 | 🔢 calculator |
| 混合问题 | 知识库+搜索+Python | 三工具协同 |

### 5 种编排模式

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| **ReAct** | 推理-行动循环，边走边看 | 探索性任务 |
| **Intent Routing** | 自动识别意图，选择工具 | 明确类别的问题 |
| **Plan-Execute** | 先规划再执行 | 复杂多步任务 |
| **Self-Reflection** | 自我审查 + 迭代改进 | 对质量要求高的场景 |
| **Source-Aware** | 内外源融合 + 冲突检测 | 需要标注来源的回答 |

### 生产级特性

- 🔄 **会话管理**：多轮对话，上下文记忆
- 📊 **结构化日志**：请求追踪 + 耗时统计
- 🛡️ **限流保护**：30次/分钟/IP
- ⚡ **SSE 流式**：实时推送 Agent 推理过程
- 🧪 **测试覆盖**：15 个单元+集成测试
- 📖 **自动文档**：Swagger UI + ReDoc

---

## 📡 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/` | 健康检查 + 系统信息 |
| `GET` | `/tools` | 列出所有可用工具 |
| `POST` | `/chat` | 主聊天（非流式） |
| `POST` | `/chat/stream` | 流式聊天（SSE） |
| `POST` | `/session/create` | 创建会话 |
| `GET` | `/session/list` | 活跃会话列表 |
| `GET` | `/session/{id}` | 查看会话历史 |
| `DELETE` | `/session/{id}` | 删除会话 |
| `POST` | `/knowledge/search` | 直接搜索知识库 |
| `POST` | `/web/search` | 直接搜索网页 |

---

## 📁 项目结构

```
ai-learning/
│
├── README.md                         # 项目主页（你在这里）
├── requirements.txt                  # Python 依赖
├── .env.example                      # API Key 配置模板
├── config.py                         # 全局配置
├── ai-learning-roadmap.md            # 30 天学习路线
│
├── 📂 第一阶段：LLM API 基础 (Week 1)
│   ├── hello_ai.py                   # Day 1  — API 初体验
│   ├── hello_ai_bailian.py           # Day 1  — 百炼平台
│   ├── day2_conversation.py          # Day 2  — 多轮对话
│   ├── day3_prompt_engineering.py    # Day 3  — Prompt 工程
│   ├── day4_resume_analyzer.py       # Day 4  — AI 简历分析器 ⭐
│   ├── day5_streaming_robustness.py  # Day 5  — 流式+异常处理
│   ├── day6_streamlit_app.py         # Day 6  — Web 界面
│   └── ai_utils.py                   # 工具模块
│
├── 📂 第二阶段：RAG 文档问答 (Week 2)
│   ├── day8_rag_intro.py             # Day 8  — RAG 入门
│   ├── day9_document_loader.py       # Day 9  — 文档加载
│   ├── day10_embedding_chroma.py     # Day 10 — Embedding 深入
│   ├── day11_rag_pipeline.py         # Day 11 — RAG 闭环
│   ├── day12_retrieval_tuning.py     # Day 12 — 检索调优
│   └── day13_rag_webapp.py           # Day 13 — RAG Web ⭐
│
├── 📂 第三阶段：AI Agent (Week 3)
│   ├── day15_agent_intro.py          # Day 15 — Agent 入门
│   ├── day16_agent_search.py         # Day 16 — +搜索工具
│   ├── day17_agent_python.py         # Day 17 — +Python执行
│   ├── day18_agent_orchestration.py  # Day 18 — 多工具编排
│   ├── day19_agent_visual.py         # Day 19 — 可视化监控
│   └── day20_agent_rag.py            # Day 20 — Agent+RAG ⭐
│
├── 📂 第四阶段：全栈部署 (Week 4)
│   ├── day22_fastapi_backend.py      # Day 22 — FastAPI 后端
│   ├── day23_api_refinement.py       # Day 23 — 生产级完善
│   └── day24_streamlit_frontend.py   # Day 24-25 — 全栈联通 ⭐
│
├── deploy-no-docker.sh               # Day 28 — 直接部署脚本（venv + systemd + Nginx）
├── nginx.conf                        # Day 28 — 反向代理
│
├── data/                             # 知识库文档
│   ├── ai_knowledge_base.txt
│   └── sample_ai_guide.pdf
│
├── docs/                             # 复盘文档
│   ├── week1-review.md
│   ├── week2-review.md
│   ├── week3-review.md
│   └── architecture.md               # 系统架构设计文档
│
└── chroma_db/                        # Chroma 向量存储
```

---

## 📊 项目数据

| 维度 | 数据 |
|------|------|
| 总代码行数 | **7,000+** |
| 代码文件 | 22 个 .py |
| 学习天数 | 25 天（进行中） |
| Agent 工具数 | 5 个 |
| API 端点 | 10 个 |
| 测试用例 | 15 个 |
| 向量库文档 | 15 chunks |
| 复盘文档 | 3 篇（Week 1-3） |

---

## 🗓️ 学习路线

```
Week 1 ──→ Week 2 ──→ Week 3 ──→ Week 4
调 API     搭 RAG    做 Agent   全栈上线
  │          │          │          │
  ▼          ▼          ▼          ▼
简历分析器  文档问答   Agent助手   🚀 部署
(Streamlit) (Chroma)  (5 Tools)  (FastAPI)
```

完整路线见 [ai-learning-roadmap.md](ai-learning-roadmap.md)，每日复盘见 [docs/](docs/)。

---

## 🎯 核心项目：AI Agent 全栈助手

> ⭐ **这是简历上的主打项目**

### 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| LLM | 通义千问 qwen-plus | 百炼 API，免费额度 |
| 向量库 | Chroma + text-embedding-v2 | 1536 维语义检索 |
| 后端 | FastAPI + Pydantic | REST API + SSE 流式 |
| 前端 | Streamlit | 纯 Python Web UI |
| 搜索 | B站 API | 国内直连，秒级响应 |
| 沙箱 | 受限 Python REPL | 安全代码执行 |

### 面试描述模板

> **AI Agent 全栈助手** | Python · FastAPI · Chroma · Streamlit  
> 设计并实现了一个具备 5 个 Function Calling 工具的 AI Agent 系统：
> - **多工具自主编排**：Agent 自动判断意图，在知识库检索、网页搜索、Python 执行、数学计算之间自主选择和编排调用顺序
> - **Agent + RAG 混合架构**：Chroma 向量知识库 + B站外部搜索双通道，来源感知综合（Source-Aware Synthesis），信息冲突时自动检测并标注
> - **5 种编排模式**：ReAct → Intent Routing → Plan-Execute → Self-Reflection → Source-Aware Synthesis
> - **前后端分离**：FastAPI REST API（10 端点 + SSE 流式） + Streamlit 全功能前端（会话管理、工具可视化）
> - **生产级特性**：结构化日志、限流保护、15 个测试用例、自动生成 Swagger 文档
> - 项目完整可运行，代码 7,000+ 行，有详细的复盘文档和学习路线

---

## 👤 关于我

- **黄畅** · 嘉应学院 软件工程 2027 届
- 求职方向：AI 应用开发工程师（实习/应届）
- 技术栈：Python · Django · MySQL · Nginx · Git

---

> 📌 这个仓库记录了我从零开始学习 AI 应用开发的完整过程。
> 30 天，4 个阶段，从 Hello World 到全栈 AI Agent——每一步都有代码、有笔记、有复盘。
