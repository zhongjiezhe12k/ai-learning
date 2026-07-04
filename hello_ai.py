"""
Day 1 - hello_ai.py
你的第一个 AI 程序：调用 DeepSeek API，让大模型跟你对话
"""

from config import deepseek_client as client, DEEPSEEK_MODEL as MODEL

# ============================================================
# API Key 已迁移到 .env 文件（不再硬编码）
# 如果你还没有 .env，复制 .env.example 并填入你的 Key
# ============================================================

# ============================================================
# 第一次调用：问一个问题
# ============================================================
response = client.chat.completions.create(
    model=MODEL,  # DeepSeek 的聊天模型
    messages=[
        {
            "role": "system",
            "content": "你是一个友好的Python编程老师，用通俗易懂的方式回答问题。",
        },
        {
            "role": "user",
            "content": "用一句话解释：什么是API？",
        },
    ],
    temperature=0.7,  # 0=死板精确, 1=天马行空, 聊天用0.7刚好
)

# ============================================================
# 打印 AI 的回复
# ============================================================
ai_reply = response.choices[0].message.content
print("🤖 AI 说：")
print(ai_reply)

# ============================================================
# 偷偷看一眼后台数据：用了多少 token？
# ============================================================
usage = response.usage
print(f"\n📊 消耗 token：输入 {usage.prompt_tokens} + 输出 {usage.completion_tokens} = 总计 {usage.total_tokens}")
print(f"💸 约花费：¥{usage.total_tokens * 0.000001:.6f}（几乎免费）")
