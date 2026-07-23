# Week 3 复盘：AI Agent 智能助手

> 时间：2026 年 7 月 16 日 — 7 月 22 日
> 目标：从零掌握 AI Agent 开发，建成具备多工具自主编排能力的 Agent 混合系统

---

## 🎯 本周目标 vs 完成情况

| 目标 | 状态 |
|------|------|
| 理解 Agent 概念：Planning → Tool Use → Reflection + Function Calling | ✅ |
| 实现网页搜索 Tool（国内多平台：Bing中国 + B站 + 搜狗）| ✅ |
| 实现 Python 代码执行 Tool（安全沙箱 + 自我调试）| ✅ |
| 实现多工具串联：意图识别 + Plan-Execute + Self-Reflection | ✅ |
| Streamlit Agent 可视化监控台：推理链条 + 工具调用详情 | ✅ |
| Agent + RAG 混合：知识库检索 + 外部搜索 + 来源感知综合 | ✅ |
| 周末复盘 + GitHub 发布 | ✅ |

**🎯 Week 3 产出：** AI Agent 混合助手 — 5 个工具自主编排，支持知识库检索、外部搜索、Python 执行、数学计算、时间查询。

---

## 📅 每日回顾

### Day 15 — Agent 入门：Function Calling 基础

**产出**：[`day15_agent_intro.py`](../day15_agent_intro.py)（976 行）

**学到的**：
- **Agent = LLM + 工具 + 循环**：LLM 理解问题 → 判断需要什么工具 → 调用工具 → 看结果 → 决定继续还是结束
- **Function Calling 机制**：用 JSON Schema 描述工具 → OpenAI SDK 传入 `tools` 参数 → LLM 返回 `tool_calls` → 执行函数 → 结果塞回对话
- Agent 循环的核心：`while iterations < max_iterations:` + 消息拼接 + tool_call 序列化格式
- 实现 2 个工具：`calculator`（安全 eval）+ `get_current_time`（日期/时间/星期）

**关键认知**：
- Function Calling 的本质不是「AI 调用函数」，而是「AI 说我想调哪个函数、传什么参数，你来执行并把结果告诉我」
- Agent 循环 = 一个 while 循环 + 正确的消息格式。不是什么黑魔法

---

### Day 16 — Agent + 网页搜索

**产出**：[`day16_agent_search.py`](../day16_agent_search.py)（744 行）

**学到的**：
- **为什么 Agent 需要搜索**：LLM 训练数据有截止日期，无法回答实时问题。搜索让 Agent 从「封闭系统」变成「开放系统」
- **国内多平台搜索架构**：插件式设计 — 每个平台只需实现「URL 模板」+「HTML/JSON 解析函数」
  - Bing 中国版（`cn.bing.com`）：通用搜索
  - 哔哩哔哩 API：视频/教程/评测搜索
  - 搜狗搜索：微信文章/中文内容
- **三层封装模式**：`raw_web_search`（原始 HTTP）→ `format_search_results`（格式化为 LLM 友好文本）→ `web_search`（Agent 工具门面函数）
- 对比实验：有搜索 vs 无搜索 Agent，答案质量差距显著

**踩过的坑**：
- DuckDuckGo（`ddgs`）国内被墙，每次搜索 17-25 秒 → 切到 B站 API（0.5-1.5秒）
- B站 API 偶尔返回空响应 → 加 `try/except` 兜底
- 搜索结果太长撑爆上下文 → `max_body_len` 截断 + 编号格式

---

### Day 17 — Agent + Python 代码执行沙箱

**产出**：[`day17_agent_python.py`](../day17_agent_python.py)（636 行）

**学到的**：
- **安全沙箱设计**：受限 `__builtins__`（禁用 `open`/`eval`/`exec`/`__import__`）+ 白名单模块（`math`/`json`/`statistics`/`collections` 等）
- **自我调试循环**：Agent 写代码 → 执行报错 → Agent 看错误信息 → 修复代码 → 重新执行 → 直到成功
- `sys.stdout` 重定向到 `StringIO` 捕获 `print()` 输出
- `compile()` + `exec()` 模式手动控制代码执行环境

**关键认知**：
- Python REPL 工具让 Agent 从「信息搬运工」升级为「数据分析师」
- 安全沙箱的关键不是「绝对安全」，而是「最小权限原则」——只给完成任务必需的模块
- Agent 的自我调试能力来自「把报错信息塞回对话里」这个简单操作

---

### Day 18 — 多工具串联：自主编排

**产出**：[`day18_agent_orchestration.py`](../day18_agent_orchestration.py)（854 行）

**学到的四大 Agent 模式**：

1. **意图识别**：4 个工具同时就位，Agent 自主判断「纯计算 → calculator」、「实时信息 → web_search」、「数据处理 → python_repl」、「常识 → 直接回答」

2. **复杂工具链编排**：`web_search → python_repl → calculator → 最终答案`。Agent 自主决定调用顺序、调用次数、何时停止

3. **Plan-then-Execute 模式**：先输出「执行计划」→ 再按计划逐步调工具 → 检查完整性。比 ReAct 更系统、更可靠、更可解释

4. **Self-Reflection 模式**：给出初步答案 → LLM 审查质量 → 发现不足 → 补充搜索/计算 → 改进答案 → 循环直到满意。这是让 Agent「靠谱」的关键

**关键认知**：
- Agent 的智能 ≠ 工具多，而是「在恰当的时候选择恰当的工具用恰当的顺序」
- Plan-Execute 和 ReAct 不互斥——高级 Agent 是「Plan-Execute + ReAct 动态调整」
- Self-Reflection 的代价是更多 API 调用，但质量和可靠性显著提升

---

### Day 19 — Streamlit Agent 可视化监控台

**产出**：[`day19_agent_visual.py`](../day19_agent_visual.py)（710 行）

**学到的**：
- **Agent 推理过程可视化**：每一轮「思考 → 工具调用 → 结果」实时展示在 UI 上
- **会话统计面板**：总轮数、工具调用次数、工具使用分布、响应时间
- **工具调用详情展开**：参数 JSON + 返回结果 + 耗时
- **策略对比模式**：同一问题用不同 System Prompt 跑两次，对比结果
- Streamlit 的 `st.session_state` 管理 Agent 运行状态

**UI 布局**：
```
┌─ 侧边栏 ─────────────┐  ┌─ 主区域 ──────────────────────┐
│ 📊 会话统计           │  │ 💬 对话区                      │
│ 总轮数: 3            │  │ ┌─────────────────────────┐   │
│ 工具调用: 5次        │  │ │ 用户: 对比RAG和Agent     │   │
│ 知识库: 2 搜索: 3    │  │ │ 🔧 Round 1: web_search  │   │
│ 平均耗时: 1.2s       │  │ │ 🔧 Round 2: python_repl │   │
│                      │  │ │ ✅ 最终回答...          │   │
│ ⚙️ 设置              │  │ └─────────────────────────┘   │
│ max_iterations: 6    │  │                               │
│ temperature: 0.0     │  │ 📈 工具调用链时间线            │
└──────────────────────┘  └───────────────────────────────┘
```

---

### Day 20 — Agent + RAG 混合系统 ⭐

**产出**：[`day20_agent_rag.py`](../day20_agent_rag.py)（1121 行）

**学到的**：
- **RAG 作为 Tool**：和 web_search 完全相同的封装模式 — Chroma 检索 → 格式化 → Function Calling Schema
- **双通道知识体系**：📚 知识库（权威、可溯源）+ 🔍 外部搜索（实时、广覆盖）
- **来源感知综合（Source-Aware Synthesis）**：答案中明确区分 `📚 内部资料` vs `🔍 外部信息`，信息矛盾时主动指出
- **工具选择策略**：概念/原理 → knowledge_base_search，最新/趋势 → web_search，综合问题 → 两者并行调用
- **向量相似度处理**：百炼 text-embedding-v2 向量未归一化，用 `1/(1+dist)` 映射 + ★★★ 等级标注
- 三方对比实验：纯 RAG（理论基础好，缺最新动态）vs 纯搜索（有最新信息，缺权威基础）vs 混合 Agent（两者互补，最完整）

---

## 🏗️ Week 3 架构演进

```
Day 15: Agent = LLM + 工具 + 循环
        ┌──────┐    ┌──────────┐
        │ LLM  │◄──►│ calculator│
        └──────┘    │ get_time │
                    └──────────┘

Day 16: + 外部搜索能力
        ┌──────┐    ┌──────────┐
        │ LLM  │◄──►│ calculator│
        └──────┘    │ get_time  │
                    │ web_search│ ← 新增
                    └──────────┘

Day 17: + 代码执行能力
        ┌──────┐    ┌──────────┐
        │ LLM  │◄──►│ calculator│
        └──────┘    │ get_time  │
                    │ web_search│
                    │ python_repl│ ← 新增
                    └──────────┘

Day 18: + 编排模式（Plan-Execute + Reflection）
        ┌──────┐    ┌──────────┐
        │Plan  │    │ 4 tools  │
        │ ↓    │◄──►│ 同时就位  │
        │Execute│   └──────────┘
        │ ↓    │
        │Reflect│   关键：不是工具多了，是编排能力
        └──────┘

Day 19: + 可视化监控台
        ┌──────────────────────┐
        │  Streamlit Dashboard  │
        │  ┌─────────────────┐ │
        │  │ Agent 推理过程   │ │
        │  │ 工具调用链       │ │
        │  │ 会话统计         │ │
        │  │ 策略对比         │ │
        │  └─────────────────┘ │
        └──────────────────────┘

Day 20: + 知识库检索（Agent + RAG 混合）⭐
             用户提问
                │
         Agent 意图分析
                │
    ┌───────────┼───────────┐
    ▼           ▼           ▼
  📚 RAG     🔍 搜索    🐍 Python
(内部知识)  (外部信息)  (数据处理)
    │           │           │
    └───────────┴───────────┘
                │
         来源感知综合
          📚 内部 + 🔍 外部
```

---

## 📊 代码统计

| 文件 | 行数 | 核心内容 |
|------|------|----------|
| `day15_agent_intro.py` | 976 | Agent 概念 + Function Calling + 基础 Agent 循环 |
| `day16_agent_search.py` | 744 | 国内多平台搜索 + 三层封装 + 对比实验 |
| `day17_agent_python.py` | 636 | 安全沙箱 + self-debugging 循环 |
| `day18_agent_orchestration.py` | 854 | Plan-Execute + Self-Reflection + 意图识别 |
| `day19_agent_visual.py` | 710 | Streamlit 可视化监控台 |
| `day20_agent_rag.py` | 1121 | Agent + RAG 混合系统 ⭐ |
| **总计** | **5,041** | **5 个工具 + 5 种编排模式** |

### 工具生态

| 工具 | 引入时间 | 功能 |
|------|----------|------|
| `calculator` | Day 15 | 安全数学计算 |
| `get_current_time` | Day 15 | 日期时间查询 |
| `web_search` | Day 16 | B站搜索（外部信息）|
| `python_repl` | Day 17 | Python 安全沙箱执行 |
| `knowledge_base_search` | Day 20 | Chroma 知识库语义检索 |
| **5 个工具** | — | **Agent 完整工具箱** |

### 编排模式

| 模式 | 引入时间 | 说明 |
|------|----------|------|
| ReAct（推理-行动循环）| Day 15 | 基础模式：边走边看 |
| Multi-Tool Intent Routing | Day 18 | 意图识别：自动选择工具 |
| Plan-then-Execute | Day 18 | 先规划再执行，更系统 |
| Self-Reflection | Day 18 | 自我审查 + 迭代改进 |
| Source-Aware Synthesis | Day 20 | 内外源融合 + 来源标注 |
| **5 种模式** | — | **从简单到高级的完整演进** |

---

## 🕳️ 踩过的坑

| 坑 | 现象 | 解法 |
|----|------|------|
| DuckDuckGo 国内被墙 | `ddgs` 每次搜索 17-25 秒 | 切到 B站 API（0.5-1.5秒） |
| B站 API 返回空响应 | 偶尔触发反爬，resp.json() 报错 | try/except + 友好错误提示 |
| Agent 循环停不下来 | LLM 不断调工具，永远不 `stop` | `max_iterations=6`，永远设上限 |
| tool_call 消息格式错误 | OpenAI SDK 对 message 格式要求严格 | 正确序列化 `id/type/function` 三个字段 |
| Python 沙箱 `__import__` 绕过 | `import math` 在受限环境仍可能被绕过 | 显式覆盖 `__import__` 抛出异常 |
| 百炼 embedding 未归一化 | `1-dist` 得出负相似度 | 改用 `1/(1+dist)` + ★★★ 等级标注 |
| System Prompt 不够强 | Agent 凭记忆回答，声称来自「内部资料」 | 加 ⚠️ 标记 + 明确禁止规则 |
| B站搜索结果时效性差 | 默认综合排序可能返回旧视频 | 暴露 `sort='newest'` 参数给 Agent |

---

## 💡 核心收获

### 1. Agent 的本质理解

```
Agent ≠ 多个 API 调用的叠加
Agent = LLM 作为「大脑」+ 工具作为「手脚」+ 循环作为「神经系统」

大脑（LLM）：理解意图、制定计划、评估结果
手脚（Tools）：执行具体操作（搜索/计算/执行代码）
神经（Loop）：连接大脑和手脚，传递信息和反馈
```

### 2. Function Calling 的精髓

- **工具描述即 Prompt**：Schema 的 `description` 字段是最重要的 Prompt Engineering——告诉 LLM 什么时候用这个工具
- **返回值格式决定效果**：返回字符串要结构化、截断、编号——LLM 需要的是「信息密度高」的文本
- **错误处理要友好**：工具报错不能直接抛异常，要返回友好文本让 Agent 知道发生了什么

### 3. System Prompt 是 Agent 的灵魂

- 不是写「你是一个助手」，而是写「什么时候用什么工具、输出什么格式」
- Day 20 最关键的改进：加了一条 `❌ 禁止：在没有调用知识库的情况下，声称信息来自「内部资料」`——一行字解决了幻觉问题

### 4. 混合架构的价值

```
纯 LLM：       知识全面但可能过时/幻觉
纯 RAG：       基于文档但缺实时信息
纯搜索 Agent：  有最新信息但缺权威基础

混合 Agent = 三者互补 → 最佳答案
这应该是 2026 年 AI 应用的主流架构方向
```

---

## 🔜 Week 4 预告：全栈整合部署

| 天 | 内容 | 目标 |
|----|------|------|
| Day 22-23 | FastAPI 后端 API | 把 Agent+RAG 系统包装为 REST API |
| Day 24-25 | Streamlit 前后端联通 | 完整全栈 AI 应用 |
| Day 26-27 | 专业 README | 架构图 + Demo 截图 + 安装步骤 |
| Day 28 | 部署上线 | 有公网链接的 AI 产品 |
| Day 29 | 简历更新 | 可投递的项目经验描述 |
| Day 30 | 总复盘 | 🎉 30 天冲刺完成 |

---

## 📸 Week 3 文件清单

```
day15_agent_intro.py         — Agent 入门：Function Calling 基础
day16_agent_search.py        — Agent + 搜索：国内多平台搜索
day17_agent_python.py        — Agent + Python：安全沙箱执行
day18_agent_orchestration.py — 多工具编排：Plan-Execute + Reflection
day19_agent_visual.py        — Streamlit Agent 可视化监控台
day20_agent_rag.py           — Agent + RAG 混合系统 ⭐
```

---

> 创建日期：2026-07-23
> Week 3 总代码量：**5,041 行** | 工具：**5 个** | 编排模式：**5 种**
> 下一个里程碑：Week 4 — 把 Agent+RAG 系统做成有公网链接的完整产品
