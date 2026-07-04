"""
Day 5 - 流式输出 + 异常处理 + 重试逻辑
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
今天的目标：把 Day 1-4 的"玩具代码"升级成"生产级代码"

三个核心技能：
  1. 流式输出（stream=True）     → 像 ChatGPT 一样逐字蹦出来
  2. 异常处理（try/except）      → API 挂了不会崩溃，优雅降级
  3. 重试逻辑（retry + backoff） → 网络抖动自动重试，不用手动重跑

最后把这些封装成一个可复用的 ai.py 工具模块。
"""

import json
import time
import sys
import os

# API Key 已迁移到 .env → config.py（不再硬编码）
from config import client, MODEL, get_client
# 想切到 DeepSeek？取消下面注释：
# client, MODEL = get_client("deepseek")


# ============================================================
# 实验 1：流式输出 —— 像 ChatGPT 一样逐字蹦
# ============================================================
print("=" * 60)
print("实验 1：流式输出（stream=True）")
print("=" * 60)

def demo_stream_vs_normal():
    """对比：普通模式 vs 流式模式"""

    question = "用三句话介绍 Python 的诞生故事"

    # ── 1.1 普通模式 —— 等全部生成完再一次性返回 ──
    print("\n📦 普通模式（stream=False）：")
    print("   等待中...", end=" ", flush=True)
    t0 = time.time()

    r = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": question}],
        stream=False,  # 默认值
    )
    elapsed = time.time() - t0
    print(f"（等了 {elapsed:.1f} 秒后一次性拿到全文）")
    print(f"   → {r.choices[0].message.content}")

    # ── 1.2 流式模式 —— 生成一个 token 就打印一个 ──
    print(f"\n🌊 流式模式（stream=True）：")
    print("   ", end="", flush=True)
    t0 = time.time()
    first_token_time = None

    stream = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": question}],
        stream=True,
    )

    full_text = ""
    for chunk in stream:
        # 每个 chunk 包含一小段文本（通常是几个 token）
        delta = chunk.choices[0].delta
        if delta.content:
            if first_token_time is None:
                first_token_time = time.time() - t0
            print(delta.content, end="", flush=True)  # 逐段打印
            full_text += delta.content

    total_time = time.time() - t0
    print(f"\n   ⏱️  首 token 延迟：{first_token_time:.2f}s | 总耗时：{total_time:.2f}s")

    print("""
📌 流式 vs 普通的区别：
   普通模式：用户盯着白屏等 3 秒 → 突然蹦出一大段文字
   流式模式：用户 0.3 秒就看到第一个字 → 像真人在打字

   什么时候用流式？
   ✅ 聊天机器人、AI 写作、任何用户盯着屏幕等的场景
   ❌ 后台批处理、结构化 JSON 输出、不需要用户体验的场景
""")


demo_stream_vs_normal()


# ============================================================
# 实验 2：异常处理 —— API 不会永远正常
# ============================================================
print("=" * 60)
print("实验 2：异常处理 —— 让代码扛得住各种翻车")
print("=" * 60)

# 真实的 API 调用会遇到这些错误：
ERRORS = {
    "认证失败": "API Key 过期或被禁用 → 401 错误",
    "余额不足": "免费额度用完 → 402/429 错误",
    "网络超时": "家里 WiFi 抽风 → 连接超时",
    "服务过载": "API 服务器忙 → 503/429 错误",
    "返回乱码": "AI 抽风返回了非 JSON → 解析失败",
}

print("\n常见翻车场景：")
for k, v in ERRORS.items():
    print(f"   ❌ {k}：{v}")


def safe_chat(messages, model=MODEL, temperature=0.7, max_retries=3):
    """
    一个「安全版」的 API 调用函数
    能自动处理：认证错误、网络超时、服务过载、意外异常
    """
    try:
        r = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        return r.choices[0].message.content

    except Exception as e:
        error_str = str(e).lower()

        # 分类处理不同错误
        if "401" in error_str or "unauthorized" in error_str:
            print(f"🔒 认证失败：API Key 无效或已过期，请检查")
        elif "402" in error_str or "insufficient" in error_str:
            print(f"💰 余额不足：免费额度用完了，去充值或等重置")
        elif "429" in error_str or "rate" in error_str:
            print(f"🚦 请求太频繁：被限流了，等几秒再试")
        elif "timeout" in error_str or "timed out" in error_str:
            print(f"⏰ 网络超时：检查网络连接")
        elif "503" in error_str or "overloaded" in error_str:
            print(f"🏥 服务过载：API 服务器忙，稍后重试")
        else:
            print(f"💥 未知错误：{e}")
        return None


# 测试：故意用错的 API Key 触发认证错误
print("\n测试认证错误处理：")
fake_client = OpenAI(
    api_key="this-is-a-fake-key-12345",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)
try:
    fake_client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": "hi"}],
    )
except Exception as e:
    err = str(e)
    if "401" in err or "unauthorized" in err.lower():
        print(f"   ✅ 正确捕获了认证错误，没有崩溃")
    else:
        print(f"   ⚠️ 捕获到错误但类型不符：{err[:80]}...")


# ============================================================
# 实验 3：重试逻辑 —— 网络抖动自动重来
# ============================================================
print("\n" + "=" * 60)
print("实验 3：重试逻辑 —— 遇到临时故障自动重来")
print("=" * 60)
print("""
核心思路：指数退避（Exponential Backoff）

  第 1 次失败 → 等 1 秒再试
  第 2 次失败 → 等 2 秒再试
  第 3 次失败 → 等 4 秒再试
  第 4 次失败 → 等 8 秒再试
  ...直到 max_retries 次 → 放弃，报错

为什么要越等越久？
  如果是服务器过载，立即重试只会雪上加霜。
  逐步拉长间隔，给服务器恢复的时间。
""")


def chat_with_retry(messages, model=MODEL, temperature=0.7, max_retries=3):
    """
    带自动重试的 API 调用 —— 这是你今天最重要的产出

    参数：
      messages      : 消息列表
      model         : 模型名
      temperature   : 温度
      max_retries   : 最大重试次数

    返回：
      成功 → AI 回复文本
      失败 → None（不会抛异常）
    """
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            r = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
            )
            # 成功！
            if attempt > 1:
                print(f"     ✅ 第 {attempt} 次尝试成功！")
            return r.choices[0].message.content

        except Exception as e:
            last_error = e
            error_str = str(e).lower()

            # 判断这个错误值不值得重试
            is_retryable = any(
                kw in error_str
                for kw in ["timeout", "timed out", "503", "429", "overloaded", "connection"]
            )

            if not is_retryable:
                # 认证失败、余额不足 → 重试也没用，直接放弃
                print(f"     ❌ 不可重试的错误：{e}")
                return None

            if attempt < max_retries:
                wait = 2 ** (attempt - 1)  # 指数退避：1, 2, 4, 8...
                print(f"     ⚠️ 第 {attempt} 次失败（{e}），{wait}s 后重试...")
                time.sleep(wait)
            else:
                print(f"     ❌ 重试 {max_retries} 次后仍然失败：{e}")

    return None


# 测试重试（正常调用，通常一次就成功）
print("\n测试 chat_with_retry：")
result = chat_with_retry(
    [{"role": "user", "content": "说一个程序员才懂的冷笑话"}]
)
if result:
    print(f"   结果：{result}")
else:
    print("   调用失败")


# ============================================================
# 实验 4：实战 —— 给 Day 4 的简历分析器加固
# ============================================================
print("\n" + "=" * 60)
print("实验 4：实战 —— 给简历分析器加上流式输出 + 异常处理 + 重试")
print("=" * 60)

MY_RESUME = """
黄畅 | 嘉应学院 软件工程 2027 届
技能：Python、Django、Java、C、MySQL、Redis（基础）、Git、Docker（基础）、Linux
项目：校园二手交易平台（Django + MySQL + Docker，日活 200+，500+ 交易）
"""

DEMO_JD = "Python 后端开发实习生 - 要求 Python/Django/MySQL，了解 Docker 优先"


def analyze_resume_robust(jd_text: str, resume: str, stream: bool = False):
    """
    Day 4 分析器的「加固版」
    - 带重试逻辑
    - 可选流式输出
    - JSON 解析容错
    """

    SYSTEM_PROMPT = """你是技术招聘专家。输出纯 JSON：
{
  "match_score": 数字(1-100),
  "level": "strong_match / potential / reach",
  "summary": "一句话总结",
  "strengths": ["优势1", "优势2"],
  "gaps": ["差距1", "差距2"],
  "tip": "求职建议"
}"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"【JD】\n{jd_text}\n\n【简历】\n{resume}"},
    ]

    if stream:
        # 流式模式：一边输出一边收集全文
        print("\n🌊 流式分析中：", end="", flush=True)
        full = ""
        for chunk in client.chat.completions.create(
            model=MODEL, messages=messages, temperature=0.1, stream=True
        ):
            delta = chunk.choices[0].delta
            if delta.content:
                print(delta.content, end="", flush=True)
                full += delta.content
        raw = full.strip()
        print()
    else:
        # 普通模式 + 重试
        raw = chat_with_retry(messages, temperature=0.1, max_retries=3)
        if raw is None:
            print("❌ API 调用失败，跳过分析")
            return None

    # JSON 清洗 + 解析（Day 4 的容错逻辑）
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        if raw.endswith("```"):
            raw = raw[:-3]

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"⚠️ JSON 解析失败，原始返回：{raw[:200]}...")
        return None


# 普通模式测试
print("\n📦 普通模式（带重试）：")
result = analyze_resume_robust(DEMO_JD, MY_RESUME, stream=False)
if result:
    print(f"   匹配度：{result['match_score']}/100 | {result['level']}")
    print(f"   {result['summary']}")

# 流式模式测试
print("\n🌊 流式模式：")
result = analyze_resume_robust(DEMO_JD, MY_RESUME, stream=True)
if result:
    print(f"\n   匹配度：{result['match_score']}/100 | {result['level']}")


# ============================================================
# Bonus：封装成可复用模块
# ============================================================
print("\n" + "=" * 60)
print("🎁 Bonus：封装你的第一个 AI 工具模块")
print("=" * 60)
print("""
把 chat_with_retry 和 safe_chat 保存到 ai_utils.py，
以后每个项目直接 import，不用每次都重写：

  from ai_utils import chat_with_retry

  answer = chat_with_retry([
      {"role": "system", "content": "你是 Python 专家"},
      {"role": "user", "content": "解释闭包"},
  ])

这就是从「学习」到「工程」的转变 🚀
""")


# ============================================================
# 课后总结
# ============================================================
print("=" * 60)
print("📝 Day 5 总结")
print("=" * 60)
print("""
  ✅ 流式输出     → stream=True，逐 token 打印，用户体验质变
  ✅ 异常处理     → try/except 分类处理，不再一崩到底
  ✅ 重试逻辑     → 指数退避，网络抖动自动恢复
  ✅ 三者组合     → 你的 API 调用代码已经从"玩具"升到"生产级"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛠️ 课后作业

  1. 运行 day5 脚本，观察流式输出和非流式的速度差异
  2. 把 chat_with_retry 保存到 ai_utils.py，让 day4_resume_analyzer.py import 它
  3. 打开 Windows 任务管理器 → 性能 → WiFi，跑脚本时拔网线看重试逻辑是否生效

🔜 Day 6 预告：Streamlit —— 把简历分析器变成 Web 界面
   纯 Python，零前端，30 行代码出一个网页！
""")
