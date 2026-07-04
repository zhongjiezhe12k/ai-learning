"""
Day 2 - 多轮对话 + 理解 Token / Temperature / 消息角色

今天掌握四个概念：
  1. 消息角色（System / User / Assistant）—— 谁在说话？
  2. Token —— AI 怎么"数"文字？
  3. Temperature —— 控制 AI 的"创意温度"
  4. 上下文窗口 —— 让 AI 记住刚才聊了什么

跑一遍就全懂了。
"""

# API Key 已迁移到 .env → config.py（不再硬编码）
from config import client, MODEL, get_client

# 想切到 DeepSeek？把下面两行取消注释：
# client, MODEL = get_client("deepseek")


# ============================================================
# 实验 1：消息角色 —— System / User / Assistant
# ============================================================
print("=" * 60)
print("实验 1：三种消息角色")
print("=" * 60)
print("""
┌──────────┬──────────────────────────────────────┐
│ system   │ 设定 AI 的人设、行为规则、输出格式    │
│ user     │ 你（用户）说的话                      │
│ assistant│ AI 之前的回复（用来维持对话记忆）      │
└──────────┴──────────────────────────────────────┘
""")

# 不加 system prompt
r1 = client.chat.completions.create(
    model=MODEL,
    messages=[{"role": "user", "content": "你好，我叫黄畅，跟我打个招呼"}],
)
print("❌ 没有 system prompt：")
print(f"   {r1.choices[0].message.content}\n")

# 加了 system prompt
r2 = client.chat.completions.create(
    model=MODEL,
    messages=[
        {"role": "system", "content": "你是一个面试教练，说话简洁干练，不超过两句话。称呼对方为「畅哥」。每次回复结尾加一句加油。"},
        {"role": "user", "content": "你好，我叫黄畅，跟我打个招呼"},
    ],
)
print("✅ 有了 system prompt：")
print(f"   {r2.choices[0].message.content}\n")


# ============================================================
# 实验 2：Temperature —— AI 的"创意温度计"（0.0 ~ 2.0）
# ============================================================
print("=" * 60)
print("实验 2：Temperature 对比 —— 同一个问题，三种温度")
print("=" * 60)

question = "用一句话鼓励一个正在学编程的软件工程学生"

for temp in [0.0, 1.0, 1.8]:
    r = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": question}],
        temperature=temp,
    )
    label = {0.0: "❄️ 冰冷精确", 1.0: "🌤️ 均衡自然", 1.8: "🔥 天马行空"}[temp]
    print(f"\n{label} (temperature={temp})：")
    print(f"   {r.choices[0].message.content}")

print("""
📌 什么时候用什么温度：
   0.0~0.3 → 代码生成、事实问答、数据提取（要准确不要创意）
   0.5~0.8 → 日常对话、写作、翻译（默认用这个范围）
   1.0~1.5 → 创意写作、头脑风暴、起名字
   1.5~2.0 → 基本不会用，输出会胡言乱语
""")


# ============================================================
# 实验 3：Token —— AI 怎么"数"文字？
# ============================================================
print("=" * 60)
print("实验 3：Token —— AI 的计数单位")
print("=" * 60)

test_text = "你好，我是软件工程专业的学生。"

r = client.chat.completions.create(
    model=MODEL,
    messages=[{"role": "user", "content": test_text}],
    max_tokens=1,  # 只让 AI 输出 1 个 token，我们不关心回复，只为看 token 计数
)

tokens_in = r.usage.prompt_tokens
print(f'输入文本："{test_text}"')
print(f"中文字数：{len(test_text)} 个字")
print(f"Token 数：{tokens_in} 个 token")
print(f"💡 中文大约 1 个字 ≈ 1~2 个 token；英文大约 1 个单词 ≈ 1.3 个 token")
print(f"   qwen-plus 上下文窗口：131,072 token（约 10 万字中文，能塞一本小说）")
print(f"   deepseek-chat 上下文窗口：131,072 token")


# ============================================================
# 实验 4：多轮对话 —— 让 AI 记住上下文
# ============================================================
print("\n" + "=" * 60)
print("实验 4：多轮对话 —— AI 能记住前面聊了什么吗？")
print("=" * 60)

# 关键：把 AI 每次的回复追加到 messages 列表里
messages = [
    {"role": "system", "content": "你是一个乐于助人的助手，回答尽量简短。"},
]

print("\n🗣️  对话开始（输入 quit 退出）\n")

while True:
    user_input = input("你：")
    if user_input.lower() in ("quit", "退出", "q"):
        print("👋 再见！")
        break

    # 把用户的话加入历史
    messages.append({"role": "user", "content": user_input})

    # 发送完整历史给 AI
    r = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.7,
    )

    reply = r.choices[0].message.content

    # 把 AI 的回复也加入历史（这样下一轮它就能"记住"）
    messages.append({"role": "assistant", "content": reply})

    print(f"AI：{reply}")
    print(f"   [当前对话已累计 {len(messages)} 条消息]\n")

# ============================================================
# 课后思考
# ============================================================
print("""
📝 Day 2 你应该已经理解：

   1. system prompt → 给 AI 设定人设和行为规则
   2. temperature  → 控制输出的随机性/创造性
   3. token        → AI 的计费单位，中英文 token 数不一样
   4. 多轮对话     → 把历史消息放进 messages 列表，AI 就能"记住"

🔜 Day 3 预告：Prompt 工程实战 —— 让 AI 输出结构化 JSON、思维链推理
""")
