"""
Day 1 - hello_ai_bailian.py
调用阿里云百炼（通义千问）API
"""

from config import client, MODEL

# ============================================================
# API Key 已迁移到 .env 文件（不再硬编码）
# 如果你还没有 .env，复制 .env.example 并填入你的 Key
# ============================================================

# ============================================================
# 百炼常用模型速查：
#   qwen-turbo     → 最快最便宜，适合简单任务
#   qwen-plus      → 均衡，日常开发推荐
#   qwen-max       → 最强，复杂推理用
#   qwen-long      → 超长上下文（1000万 token），读长文档用
# ============================================================

response = client.chat.completions.create(
    model=MODEL,  # 日常用 qwen-plus 就够了
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
    #n=2,
    temperature=0.7,
)

ai_reply = response.choices[0].message.content
print("🤖 通义千问说：")
print(ai_reply)

usage = response.usage
print(f"\n📊 消耗 token：输入 {usage.prompt_tokens} + 输出 {usage.completion_tokens} = 总计 {usage.total_tokens}")
