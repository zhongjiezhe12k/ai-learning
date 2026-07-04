# Week 1 复盘：从零到 AI 应用开发者

> 时间：2026 年 7 月 2 日 — 7 月 4 日
> 目标：打通 LLM API，建立手感，产出第一个 AI 应用

---

## 🎯 本周目标 vs 完成情况

| 目标 | 状态 |
|------|------|
| 调用 DeepSeek + 百炼两个平台的 API | ✅ |
| 理解 Token / Temperature / 消息角色 | ✅ |
| 掌握 Prompt 工程（角色设定 + JSON 输出 + 思维链） | ✅ |
| 做一个可用的 AI 简历分析器 | ✅ |
| 学会流式输出 + 异常处理 + 重试 | ✅ |
| 用 Streamlit 做出 Web 界面 | ✅ |

---

## 📅 每日回顾

### Day 1 — API 调用入门
**产出**：`hello_ai.py`、`hello_ai_bailian.py`

**学到的**：
- OpenAI Python SDK 同时兼容 DeepSeek 和百炼，区别只在 `base_url` 和 `model` 名
- `client.chat.completions.create()` 是最核心的方法，所有后续项目都在这个基础上构建
- Token 消耗极小，一次对话不到 1 分钱

**踩坑**：
- 两个平台的 API Key 获取入口不同，百炼在阿里云控制台，DeepSeek 在 platform.deepseek.com
- 百炼的 base_url 是 `https://dashscope.aliyuncs.com/compatible-mode/v1`，路径末尾的 `/compatible-mode/v1` 不能省

---

### Day 2 — 多轮对话 + 核心概念
**产出**：`day2_conversation.py`（含交互式对话机器人）

**学到的**：
- **三种消息角色**：`system`（设定人设）、`user`（用户输入）、`assistant`（AI 回复）
- **Temperature**：0.0 = 精确死板，1.0 = 均衡自然，1.8 = 天马行空
- **Token**：中文 ~1-2 token/字，英文 ~1.3 token/词。qwen-plus 上下文 131K token
- **多轮对话**：把每轮对话追加到 `messages` 列表里，AI 就能"记住"上下文

**关键认知**：
- System prompt 不是建议——AI 会非常认真地执行。这为 Day 3 的 Prompt 工程打下基础
- 上下文窗口是有限的，对话太长会丢失早期的信息

---

### Day 3 — Prompt 工程实战
**产出**：`day3_prompt_engineering.py`

**学到的三大技能**：

1. **角色设定** — system prompt 精准控制 AI 的行为和风格
   - 同一个问题，三种人设 → 三种完全不同的回答
   
2. **结构化 JSON 输出** — 让 AI 返回程序可读的数据
   - 技巧：temperature 降到 0.1 + system prompt 写"纯 JSON" + 给 JSON 示例
   - 这是「AI 应用开发」和「跟 AI 聊天」的分水岭
   
3. **思维链（CoT）** — "先想清楚，再说答案"
   - 最简单的触发词：「请一步一步思考」
   - 在数学、逻辑、代码审查场景效果显著

**产出了一个可复用的 Prompt 模板** — `EVALUATION_TEMPLATE`，后续 Day 4 的核心资产。

---

### Day 4 — AI 简历分析器（CLI 版）
**产出**：`day4_resume_analyzer.py`

**这是第一个完整的 AI 应用**，整合了前三天的所有技能：

```
输入 JD + 简历 → AI 输出 {
  匹配度评分,
  技能逐项对照（✅/⚠️/❌）,
  优势分析, 差距分析,
  改进建议, 求职信卖点
}
```

**架构设计**：
- 支持三种运行模式：交互式粘贴 / 从文件读取 / `--demo` 演示
- `batch_compare()` 可一次对比多个 JD
- JSON 解析做了容错处理（AI 偶尔会在 JSON 外包 \`\`\`json）

---

### Day 5 — 流式输出 + 异常处理 + 重试
**产出**：`day5_streaming_robustness.py`、`ai_utils.py`

**从"玩具代码"升级到"生产级代码"的三个技能**：

1. **流式输出**（`stream=True`）
   - 首 token 延迟 ~0.3s vs 普通模式等 3s 一次性出全文
   - 用户体验质变：像 ChatGPT 一样逐字蹦
   
2. **异常处理**
   - 分类处理：401（认证）、402（余额）、429（限流）、503（过载）、timeout
   - 不再一崩到底，而是优雅降级
   
3. **重试逻辑 + 指数退避**
   - 只重试可恢复的错误（网络超时、服务过载），不重试认证失败
   - 等待间隔：1s → 2s → 4s → 8s...

**最重要的产出：`ai_utils.py`**
- `chat_with_retry()` — 带自动重试的 API 调用
- `safe_chat()` — 安全版 API 调用，错误分类处理
- 这是第一个**可复用模块**，后续所有项目都直接 import

---

### Day 6 — Streamlit Web 界面
**产出**：`day6_streamlit_app.py`

**零前端基础，纯 Python 写出 Web 应用**：

- `st.columns()` 双栏布局（左 JD 右简历）
- `st.metric()` 展示匹配度分数卡片
- `st.dataframe()` 展示技能逐项对照表
- `st.expander()` 折叠原始 JSON
- 颜色编码：绿（≥80）/ 黄（≥60）/ 红（<60）

**启动**：`streamlit run day6_streamlit_app.py` → 浏览器打开 `http://localhost:8501`

---

## 🔗 技能图谱：六天如何串成一条线

```
Day 1: API 调用
  ↓ 能调了但不可控
Day 2: 消息角色 + Temperature + 多轮对话
  ↓ 可控了但输出是自由文本
Day 3: Prompt 工程（角色设定 + JSON 输出 + CoT）
  ↓ 输出结构化数据，程序可直接消费
Day 4: 简历分析器 — 第一个完整应用
  ↓ 能用但不够健壮
Day 5: 流式输出 + 异常处理 + 重试 → ai_utils.py
  ↓ 代码从"玩具"升级到"生产级"
Day 6: Streamlit Web 界面
  ↓ 有 UI 的完整 AI 应用 🎉
```

---

## 🛠️ 本周技术栈

| 层级 | 技术 | 掌握程度 |
|------|------|----------|
| LLM API | OpenAI SDK（兼容 DeepSeek + 百炼） | 🟢 熟练 |
| 提示词 | System Prompt / JSON 输出 / CoT | 🟢 熟练 |
| 容错 | try-except / 重试 / 指数退避 | 🟢 熟练 |
| UI | Streamlit | 🟡 会用 |
| 工程化 | 模块封装 / .env 配置管理 | 🟡 会用 |

---

## ⚠️ 本周踩过的坑

| 坑 | 怎么解决的 |
|----|-----------|
| API Key 硬编码在源码里 | Day 7 迁移到 `.env` + `config.py` |
| AI 返回的 JSON 外包了 \`\`\`json | 加清洗逻辑：去掉首尾的 markdown 标记 |
| Temperature 太高导致 JSON 格式不稳定 | 结构化输出统一用 0.1 |
| 网络抖动导致程序崩溃 | `chat_with_retry()` 自动重试 |
| Streamlit 每次点按钮重跑整个脚本 | 理解 Streamlit 的 reactive 执行模型 |

---

## 🔜 Week 2 展望：RAG 私有文档问答系统

下周要学的是 2026 年最核心的 AI 应用形态 — **RAG（检索增强生成）**：

```
用户上传 PDF → 文档切割 → 向量嵌入 → 存入 Chroma
                                         ↓
用户提问 → 语义检索 → 拼接上下文 → LLM 生成答案（带来源标注）
```

**关键依赖准备**：
- `langchain` — RAG 编排框架
- `chromadb` — 向量数据库（本地内存模式，零配置）
- `openai` — 已有，Embedding API 也在同一个 SDK 里

---

> 📝 复盘日期：2026-07-04
> 🎯 Week 1 产出：AI 简历分析器（Streamlit + 百炼/DeepSeek），支持 JD+简历输入 → 匹配评分 + 逐项分析 + 改进建议
