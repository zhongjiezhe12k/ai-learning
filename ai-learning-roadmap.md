# 黄畅 · AI 应用开发 30 天冲刺路线

> 起点：Python 基础 + C + Java + 数据库 | 嘉应学院软件工程 2027 届
> 目标：AI 应用开发工程师（实习/应届），投递广深
> 时间：2026 年 7 月开始，一个月高强度冲刺
> 状态：🟢 进行中 | Week 1 完成 ✅ | Week 2 即将开始

---

## 📊 进度追踪

| 天 | 日期 | 内容 | 状态 | 产出 |
|----|------|------|------|------|
| Day 1 | 2026-07-02 | API 调用入门：DeepSeek + 百炼双平台跑通 | ✅ 完成 | `hello_ai.py` `hello_ai_bailian.py` |
| Day 2 | 2026-07-02 | 多轮对话 + Token/Temperature/消息角色 | ✅ 完成 | `day2_conversation.py`（含对话机器人） |
| Day 3 | 2026-07-03 | Prompt 工程：结构化输出 + 思维链 | ✅ 完成 | `day3_prompt_engineering.py` |
| Day 4 | 2026-07-03 | AI 简历分析器 CLI 版 | ✅ 完成 | `day4_resume_analyzer.py` |
| Day 5 | 2026-07-03 | 流式输出 + 异常处理 + 重试逻辑 | ✅ 完成 | `day5_streaming_robustness.py` `ai_utils.py` |
| Day 6 | 2026-07-03 | Streamlit Web 界面 | ✅ 完成 | `day6_streamlit_app.py` |
| Day 7 | 2026-07-04 | 复盘 + GitHub 发布 | ✅ 完成 | `README.md` `docs/week1-review.md` `.env.example` `config.py` |

### 环境已就绪

- ✅ Python 3.13.3 + pip
- ✅ `openai` 包
- ✅ 百炼 API Key（阿里云）
- ✅ DeepSeek API Key
- ✅ 会用 `base_url` 切换平台

---

## 核心策略

```
不做的事：
  ❌ 啃深度学习数学（反向传播、梯度下降）
  ❌ 从头训练模型（PyTorch / TensorFlow）
  ❌ 学前端框架（React / Vue）
  ❌ 本地部署开源大模型（CUDA 配置地狱）
  ❌ 同时追多个框架

只做的事：
  ✅ 调 API → 搭 RAG → 做 Agent → 出作品
```

---

## 四周项目产出总览

| 时间点 | 项目 | 性质 | 技术栈 |
|--------|------|------|--------|
| Day 4-6 | **AI简历分析器** | 第一个小项目，练手感 | Streamlit + DeepSeek API |
| Day 8-13 | **RAG 私有文档问答系统** | ⭐ 核心项目，含金量最高 | LangChain + Chroma + DeepSeek |
| Day 15-20 | **AI Agent 助手** | 进阶项目，展示上限 | LangChain Agent + 多工具 |
| Day 22-28 | **全栈整合部署** | 包装成完整产品 | FastAPI + Streamlit + 部署上线 |

---

## 第一周：打通 API，建立手感

| 天 | 做什么 | 产出 |
|----|--------|------|
| Day 1 | 注册 DeepSeek API + 阿里云百炼（免费额度够用一个月），跑通第一个 `hello_ai.py` | 一行代码让 LLM 说话 |
| Day 2 | 理解核心概念：Token、Temperature、System/User/Assistant 消息角色、上下文窗口 | 多轮对话脚本 |
| Day 3 | Prompt 工程实战：角色设定、指定输出格式（JSON）、思维链（CoT） | 一份可复用的 Prompt 模板 |
| Day 4 | 做一个 **AI简历分析器** —— 输入 JD + 你的简历，让 AI 输出匹配度评分和改进建议 | 第一个可用小工具 |
| Day 5 | 流式输出（`stream=True`）+ 异常处理 + 重试逻辑 | 健壮的 API 调用封装 |
| Day 6 | 用 **Streamlit** 把 Day 4 的简历分析器做成 Web 界面 | 第一个有 UI 的 AI 应用 |
| Day 7 | 复盘 + 整理代码到 GitHub | Week 1 仓库 |

**🎯 Week 1 产出：** AI 简历分析器（Streamlit + DeepSeek API），能输入 JD 和简历，输出匹配评分和修改建议。

---

## 第二周：RAG —— 2026 年最核心的 AI 应用形态

| 天 | 做什么 | 产出 |
|----|--------|------|
| Day 8 | 理解 RAG 全流程：加载 → 切割 → 向量化 → 检索 → 生成 | 能画出 RAG 架构图 |
| Day 9 | 用 LangChain 加载 PDF/TXT 文档 + 文本切割 | 文档处理脚本 |
| Day 10 | 向量嵌入（Embedding）+ Chroma 向量数据库存储 | 文档 → 向量全流程 |
| Day 11 | 语义检索 + 拼接上下文 + 调用 LLM 生成答案 | RAG 核心闭环跑通 |
| Day 12 | 提升检索质量：调整 chunk size、overlap、相似度阈值 | 比 Day 11 准确率明显提升 |
| Day 13 | 用 Streamlit 把 RAG 系统做成 Web 界面（上传文档 → 提问 → 回答 + 原文溯源） | ⭐ 私有文档问答系统 |
| Day 14 | 周末复盘 + 代码整理 + GitHub 发布 | Week 2 仓库 |

**🎯 Week 2 产出：** 私有文档 AI 问答系统（上传任意 PDF → 提问 → AI 基于文档内容回答 + 标注来源）。

---

## 第三周：Agent —— 让 AI 干活而不是聊天

| 天 | 做什么 | 产出 |
|----|--------|------|
| Day 15 | 理解 Agent 概念：Planning → Tool Use → Reflection。什么是 Function Calling | Agent 调用一个 Tool |
| Day 16 | 实现第一个 Tool：让 Agent 搜索网页（Tavily / DuckDuckGo） | Agent + 搜索 |
| Day 17 | 实现第二个 Tool：让 Agent 执行 Python 代码/数学计算 | Agent + 计算 |
| Day 18 | 多 Tool 串联：Agent 自主决定用哪个工具，多步骤完成任务 | 多工具 Agent |
| Day 19 | 用 Streamlit 给 Agent 做 UI，能看到它每一步的思考和工具调用 | Agent 可视化界面 |
| Day 20 | 进阶：Agent + RAG 结合（Agent 从知识库检索 + 外部搜索 + 综合回答） | Agent + RAG 混合系统 |
| Day 21 | 周末复盘 + GitHub | Week 3 仓库 |

**🎯 Week 3 产出：** AI Agent 助手（能自主搜索网页、执行计算、查询知识库，多步骤完成任务）。

---

## 第四周：整合 + 作品集打磨

| 天 | 做什么 | 产出 |
|----|--------|------|
| Day 22-23 | 用 **FastAPI** 把最有亮点的项目（推荐 RAG 系统）包装成 API | 有 API 接口的 AI 服务 |
| Day 24-25 | 前后端联通：Streamlit 前端 ↔ FastAPI 后端 ↔ LLM + 向量库 | 完整全栈 AI 应用 |
| Day 26-27 | 写 README：项目介绍、架构图、安装步骤、Demo 截图/视频 | 专业级项目首页 |
| Day 28 | 部署上线（推荐 Railway / HuggingFace Spaces / 阿里云函数计算） | **有公网链接** |
| Day 29 | 整理简历中的 AI 项目描述，润色「项目经验」板块 | 可投递的简历更新 |
| Day 30 | 总复盘 + 收尾 | 🎉 |

**🎯 最终产出：** 1 个部署上线的完整 AI 应用 + 2 个小工具 + 更新后的简历。

---

## 技术栈（全部国内可用，免费额度够练）

| 层级 | 技术 | 说明 |
|------|------|------|
| LLM API | DeepSeek（首选）、通义千问（备用） | 国内直连，免费额度 |
| 框架 | LangChain | RAG + Agent 编排 |
| UI | Streamlit | 纯 Python 写 Web，零前端基础 |
| 后端 | FastAPI | 第四周 API 化 |
| 向量库 | Chroma | 本地内存模式，零配置 |
| 部署 | HuggingFace Spaces / 阿里云 | 免费 + 简单 |

---

## 每天学习节奏

```
上午（1h）  ：看目标概念 + 读 API 文档
下午（1.5h）：动手写代码，遇到问题先问 AI
晚上（0.5h）：复盘今天写了什么、遇到了什么坑、怎么解决的
```

> 🔑 关键原则：每天必须有代码产出。不是看完教程才算——是跑通一个自己能改参数的程序才算。

---

## 常见坑预警

| 坑 | 解法 |
|----|------|
| API 返回 401/403 | 检查 API Key 和 base_url，免费额度是否用完 |
| RAG 检索不准 | 先调 chunk_size（500 → 300 → 200），再调 overlap |
| Chroma 连接报错 | 换 `chromadb.Client()` 内存模式 |
| Agent 循环不停 | 设 `max_iterations=5`，永远设上限 |
| Streamlit 部署失败 | `requirements.txt` 固定版本号 |

---

## 四周前 vs 四周后

| 能力 | 现在 | 四周后 |
|------|------|--------|
| 调 LLM API | ❌ | ✅ 流式输出、错误处理、Prompt 工程 |
| RAG 系统 | ❌ | ✅ 完整 RAG 问答系统，部署上线 |
| Agent 开发 | ❌ | ✅ 多工具 Agent，自主决策 |
| GitHub AI 项目 | ❌ | ✅ 2-3 个完整项目 + 专业 README |
| 简历 AI 经验 | ❌ | ✅ 有公网 Demo 链接 |

---

## 一月后的进阶方向

```
当前（一个月完成）
    ↓
阶段二：Web 框架集成
    FastAPI + 数据库 + 用户认证 + API 限流
    ↓
阶段三：RAG 深入
    向量数据库(Pinecone/Weaviate) + 文档解析优化 + 混合检索
    ↓
阶段四：AI Agent 深入
    Function Calling / Tool Use + 多步骤任务规划 + LangGraph
    ↓
阶段五（进阶）：模型微调
    LoRA 微调 + 数据集准备 + 本地部署(Ollama)
```

---

> 创建日期：2026-07-02
> 基于：AI 校招岗位同比增长 47.3%，传统软件开发需求下降 25%，AI 应用开发需求增长 60%+
