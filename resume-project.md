# 简历项目描述（STAR 法则）

## 项目名称：AI Agent 全栈助手 — 多工具自主编排智能对话系统

> **2026.07 · 独立开发 · GitHub 开源**
> Python · FastAPI · Streamlit · Chroma · LangChain · 通义千问 API

---

### S (Situation — 背景)

校招 AI 应用开发岗位竞争激烈，传统软件工程项目经验难以体现 AI 工程化落地能力。需要在短时间内从零构建一个覆盖 LLM 应用开发全链路、具备生产级特性的完整项目，作为求职核心竞争力。

### T (Task — 任务)

独立设计并实现一个具备多工具自主编排能力的 AI Agent 全栈应用。要求覆盖 API 调用、RAG 文档问答、Agent 工具编排、前后端分离、生产环境部署等完整技术链路，并能一键启动演示。

### A (Action — 行动)

1. **架构设计**：采用 4 层架构（前端展示层 → FastAPI 应用层 → Agent 编排层 → 工具层），前后端分离，插件式工具注册机制支持热扩展
2. **Agent + RAG 混合引擎**：实现 5 个 Function Calling 工具（Chroma 向量知识库检索、B站网页搜索、Python 安全沙箱执行、数学计算器、日期时间），Agent 自主进行意图分析并编排多工具调用顺序，支持来源感知综合（Source-Aware Synthesis），信息冲突时自动检测并标注出处
3. **5 种编排模式**：逐一实现 ReAct（推理-行动循环）、Intent Routing（意图路由）、Plan-Execute（先规划后执行）、Self-Reflection（自我反思迭代改进）、Source-Aware Synthesis（内外源融合）五种 Agent 编排策略
4. **后端工程化**：基于 FastAPI 构建 REST API，包含 10 个端点（聊天、SSE 流式响应、会话 CRUD、知识库搜索、网页搜索），Pydantic 请求校验，自动生成 Swagger/ReDoc 接口文档
5. **前端交互**：Streamlit 构建 3-Tab 全功能界面（智能对话 + 知识库搜索 + 网页搜索），SSE 流式渲染 Agent 推理过程，工具调用实时可视化面板，会话管理
6. **生产级特性**：实现基于 UUID 的会话管理（多轮对话上下文记忆）、Python logging 结构化日志（请求追踪 + 每轮耗时统计）、令牌桶限流（30次/分钟/IP）、统一错误响应格式
7. **质量保障**：编写 15 个 pytest + httpx 单元测试与集成测试，覆盖全部 API 端点
8. **生产环境部署**：编写一键部署脚本，自动化完成 Python 虚拟环境、systemd 后台服务、Nginx 反向代理配置，支持阿里云 ECS 部署

### R (Result — 成果)

- 累计编写 **7,000+ 行** Python 代码，**22 个代码文件**，**10 个 API 端点**，**15 个测试用例**
- 项目可通过 `bash deploy-no-docker.sh` 一键部署，前后端完整联通，具备生产环境部署能力
- GitHub 开源，包含专业 README（架构图 + API 文档 + 快速开始 + 面试描述模板）、系统架构设计文档、3 篇阶段性学习复盘
- 30 天内完成从 「Hello World」到「全栈 AI Agent」的完整学习路径，每一天均有代码产出和笔记记录

---

## 面试精简版（一页简历用）

> **AI Agent 全栈助手** | Python · FastAPI · Chroma · Streamlit | 2026.07
>
> - 独立设计并实现 4 层架构的 AI Agent 全栈应用，前后端分离（FastAPI + Streamlit），支持一键脚本部署
> - 实现 5 个 Function Calling 工具的 Agent + RAG 混合引擎，Agent 自主意图识别并编排多工具调用顺序，支持来源感知综合
> - 5 种 Agent 编排模式：ReAct / Intent Routing / Plan-Execute / Self-Reflection / Source-Aware Synthesis
> - 10 个 REST API 端点 + SSE 流式响应 + Swagger 文档，15 个 pytest 测试用例，限流 + 结构化日志 + 会话管理
> - 累计 7,000+ 行代码，配套系统架构设计文档与 3 篇学习复盘
