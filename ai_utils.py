"""
AI 工具模块 —— 可复用的 API 调用封装
用法：from ai_utils import chat_with_retry, MODEL
"""

import time
from config import client, MODEL

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
