# 系统架构设计文档 — AI Agent 全栈助手

> 版本 2.0 | 2026-07-24 | Day 26-27

---

## 1. 系统概述

### 1.1 项目定位

AI Agent 全栈助手是一个具备多工具自主编排能力的智能对话系统。核心思路是：将 LLM 作为"大脑"，将知识库/搜索引擎/Python执行器作为"手脚"，通过 Agent Loop 连接两者，实现复杂任务的自主完成。

### 1.2 设计目标

- **可演示**：前后端分离，Streamlit Web UI，一键启动
- **可扩展**：工具插件式注册，新增工具只需添加 schema + function
- **可维护**：清晰的分层架构，完善的测试和日志
- **可部署**：FastAPI 标准化 REST API，配套一键部署脚本（systemd + Nginx）

---

## 2. 系统架构

### 2.1 整体架构图

```
┌──────────────────────────────────────────────────────────────────┐
│                          前端层 (Presentation)                    │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Streamlit App (day24_streamlit_frontend.py)               │  │
│  │                                                            │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────────────┐ │  │
│  │  │ 智能对话  │  │ 知识库搜索│  │ 网页搜索                 │ │  │
│  │  │ (SSE 流式)│  │ (直接检索)│  │ (B站 API)               │ │  │
│  │  └──────────┘  └──────────┘  └──────────────────────────┘ │  │
│  │                                                            │  │
│  │  Session State: messages[], session_id, tools_enabled[]   │  │
│  └────────────────────────────────────────────────────────────┘  │
│                              │ HTTP/SSE                           │
└──────────────────────────────┼───────────────────────────────────┘
                               │
┌──────────────────────────────┼───────────────────────────────────┐
│                          应用层 (Application)                     │
│                              │                                    │
│  ┌──────────────────────────┼──────────────────────────────────┐ │
│  │  FastAPI Server (day23_api_refinement.py)                   │ │
│  │                                                            │ │
│  │  Middleware: CORS → RateLimiter → RequestLogger            │ │
│  │                                                            │ │
│  │  ┌─────────────────┐  ┌─────────────┐  ┌────────────────┐ │ │
│  │  │ /chat           │  │ /session/*  │  │ /knowledge     │ │ │
│  │  │ /chat/stream    │  │             │  │ /web/search    │ │ │
│  │  └────────┬────────┘  └─────────────┘  └────────────────┘ │ │
│  │           │                                                 │ │
│  └───────────┼─────────────────────────────────────────────────┘ │
│              │                                                    │
└──────────────┼────────────────────────────────────────────────────┘
               │
┌──────────────┼────────────────────────────────────────────────────┐
│                          引擎层 (Engine)                           │
│              │                                                    │
│  ┌───────────┴──────────────────────────────────────────────────┐ │
│  │  Agent Loop Engine (run_agent)                               │ │
│  │                                                              │ │
│  │  while iterations < max_iterations:                          │ │
│  │    1. LLM 推理 (qwen-plus)                                   │ │
│  │    2. if finish_reason == "stop": break                      │ │
│  │    3. if tool_calls: 执行工具 → 结果塞回对话                  │ │
│  │                                                              │ │
│  │  System Prompt (工具选择策略 + 来源标注要求)                   │ │
│  └──────────┬───────────────────────────────────────────────────┘ │
│             │                                                     │
└─────────────┼─────────────────────────────────────────────────────┘
              │
┌─────────────┼─────────────────────────────────────────────────────┐
│                          工具层 (Tools)                            │
│             │                                                     │
│  ┌──────────┴──────────────────────────────────────────────────┐  │
│  │  Tool Registry (ALL_TOOLS)                                   │  │
│  │                                                              │  │
│  │  ┌──────────────────┐  ┌──────────────────┐                  │  │
│  │  │ 📚 knowledge_base │  │ 🔍 web_search    │                  │  │
│  │  │ _search           │  │                  │                  │  │
│  │  │                   │  │ B站搜索 API       │                  │  │
│  │  │ Chroma 向量检索    │  │ HTTP GET         │                  │  │
│  │  │ Embedding API     │  │ JSON 解析         │                  │  │
│  │  │ 相似度评分         │  │ 发布时间标记      │                  │  │
│  │  └──────────────────┘  └──────────────────┘                  │  │
│  │                                                              │  │
│  │  ┌──────────────────┐  ┌──────────────────┐                  │  │
│  │  │ 🐍 python_repl    │  │ 🔢 calculator    │                  │  │
│  │  │                   │  │                  │                  │  │
│  │  │ 受限 __builtins__ │  │ 编译时代码检查    │                  │  │
│  │  │ 白名单模块         │  │ 白名单函数       │                  │  │
│  │  │ stdout 捕获        │  │ eval() 表达式    │                  │  │
│  │  └──────────────────┘  └──────────────────┘                  │  │
│  │                                                              │  │
│  │  ┌──────────────────┐                                        │  │
│  │  │ 🕐 get_current    │  每个 Tool =                           │  │
│  │  │ _time             │  Function + JSON Schema + Description │  │
│  │  └──────────────────┘                                        │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### 2.2 分层职责

| 层 | 文件 | 职责 |
|----|------|------|
| 前端 | `day24_streamlit_frontend.py` | UI 渲染、SSE 消费、会话状态管理 |
| 应用 | `day23_api_refinement.py` | HTTP 路由、请求验证、限流、日志 |
| 引擎 | `run_agent()` | Agent Loop、消息管理、工具调度 |
| 工具 | 5 个 tool 函数 | 具体的功能实现 |

---

## 3. 核心流程

### 3.1 一次完整的请求处理

```
用户输入 "什么是 RAG？"
    │
    ▼
Streamlit 前端
    │ POST /chat/stream {message, session_id, tools}
    ▼
FastAPI 后端
    │ 1. 限流检查
    │ 2. 创建/复用 session
    │ 3. 构建 messages（含历史）
    ▼
Agent Loop
    │ Round 1: LLM 推理
    │   → finish_reason: tool_calls
    │   → 调用: knowledge_base_search("RAG 概念")
    │   → 返回: [3 个相关 chunk, 含相似度评分]
    │
    │ Round 2: LLM 推理（带着检索结果）
    │   → finish_reason: stop
    │   → 生成答案
    ▼
SSE 事件流 → Streamlit 渲染
    │ 1. tool_call 事件 → 侧边栏展示
    │ 2. answer 事件 → 主区域展示
    │ 3. done 事件 → 结束
    ▼
保存到 session 历史
```

### 3.2 Agent 工具选择决策树

```
用户问题
    │
    ├── 概念/原理/框架解释？
    │   └── 📚 knowledge_base_search（优先级最高）
    │
    ├── 最新新闻/实时数据/价格？
    │   └── 🔍 web_search（sort='newest'）
    │
    ├── 数据处理/统计分析？
    │   └── 🐍 python_repl
    │
    ├── 数学计算？
    │   └── 🔢 calculator
    │
    ├── 日期时间？
    │   └── 🕐 get_current_time
    │
    └── 混合问题？
        └── 先 📚 知识库 → 再 🔍 搜索 → 🐍 分析 → 综合回答
```

---

## 4. 数据模型

### 4.1 请求/响应模型

```python
# 聊天请求
ChatRequest {
    message: str          # 用户问题 (1-5000 字符)
    session_id: str|null  # 会话 ID
    max_iterations: int   # 最大步数 (1-15)
    temperature: float    # LLM 温度 (0.0-1.5)
    tools: list[str]      # 启用的工具列表
}

# 聊天响应
ChatResponse {
    answer: str                    # Agent 回答
    session_id: str                # 会话 ID
    iterations: int                # 实际步数
    tool_calls: list[ToolCallRecord]  # 工具调用记录
    total_elapsed_ms: float        # 总耗时
    model: str                     # 使用的模型
}

# 工具调用记录
ToolCallRecord {
    round: int        # 第几轮
    tool: str         # 工具名
    args: dict        # 调用参数
    result: str       # 返回结果（截断到 500 字符）
    elapsed_ms: float # 工具执行耗时
}
```

### 4.2 SSE 事件格式

```
data: {"type":"tool_call","data":{...tool record...}}

data: {"type":"answer","data":{"answer":"...","iterations":2,"total_elapsed_ms":5000}}

data: {"type":"done","data":{}}

data: {"type":"error","data":{"message":"..."}}
```

---

## 5. 安全设计

### 5.1 Python 沙箱

```python
# 黑名单
禁用: __import__, open, eval, exec, compile, globals, locals

# 白名单
允许: print, len, range, sum, sorted, list, dict, ...
预装: math, json, datetime, statistics, collections, itertools, re

# 执行隔离
- sys.stdout 重定向到 StringIO
- 独立 namespace（不污染全局）
- compile() + exec() 而非直接 eval()
```

### 5.2 API 安全

| 措施 | 实现 |
|------|------|
| 限流 | 滑动窗口，30次/分钟/IP |
| 输入校验 | Pydantic 模型 + 字符串长度限制 |
| CORS | 允许所有来源（开发阶段） |
| 错误处理 | 统一 ErrorResponse 格式，不泄露内部细节 |

---

## 6. 性能指标

| 指标 | 典型值 | 说明 |
|------|--------|------|
| 知识库检索 | 200-400ms | Embedding API + Chroma 查询 |
| 网页搜索 | 1-8s | 取决于 B站 API 响应速度 |
| Python 执行 | <100ms | 本地沙箱 |
| Agent 首字延迟 | 3-8s | 含首次 LLM 推理 + 工具调用 |
| 单次问答总耗时 | 5-35s | 取决于工具调用次数 |
| 流式 SSE 延迟 | <100ms | 事件推送间隔 |

---

## 7. 扩展指南

### 7.1 添加新工具

```python
# 1. 实现函数
def my_new_tool(param: str) -> str:
    return f"处理结果: {param}"

# 2. 注册到 ALL_TOOLS
ALL_TOOLS["my_new_tool"] = {
    "name": "我的新工具",
    "icon": "🆕",
    "schema": {
        "type": "function",
        "function": {
            "name": "my_new_tool",
            "description": "工具描述——LLM 根据这个判断何时调用",
            "parameters": {
                "type": "object",
                "properties": {
                    "param": {"type": "string", "description": "参数说明"}
                },
                "required": ["param"],
            },
        },
    },
    "func": lambda param: my_new_tool(param),
}
```

### 7.2 切换 LLM 模型

在 `.env` 中修改或直接改 `config.py`：

```python
# 切换到 DeepSeek
from config import deepseek_client, DEEPSEEK_MODEL
# 或设置环境变量
# DEEPSEEK_API_KEY=your_key
```

---

## 8. 已知局限

| 局限 | 影响 | 改进方向 |
|------|------|----------|
| B站 API 限流 | 偶尔返回 412 | 增加重试逻辑或备用搜索源 |
| 会话内存存储 | 重启丢失 | 接入 Redis/数据库 |
| 无用户认证 | 所有人共享同一会话空间 | 添加 JWT 认证 |
| 知识库静态 | 无法增量更新 | 实现文档上传 API |
| 单一 LLM | 无 fallback | 多模型自动切换 |

---

> 创建日期：2026-07-24 | 版本 2.0
