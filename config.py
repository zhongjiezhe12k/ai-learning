"""
全局配置 — 从 .env 文件读取 API Keys
用法：from config import get_client, MODEL
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# ============================================================
# 默认使用百炼（qwen-plus），稳定、有免费额度
# ============================================================
BAILIAN_API_KEY = os.getenv("BAILIAN_API_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

BAILIAN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# 默认客户端（百炼）
client = OpenAI(
    api_key=BAILIAN_API_KEY,
    base_url=BAILIAN_BASE_URL,
)
MODEL = "qwen-plus"

# DeepSeek 客户端（备用）
deepseek_client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
)
DEEPSEEK_MODEL = "deepseek-chat"


def get_client(platform: str = "bailian") -> tuple[OpenAI, str]:
    """
    获取指定平台的客户端和模型名

    参数：
        platform: "bailian"（默认）或 "deepseek"

    返回：
        (client, model_name)
    """
    if platform == "deepseek":
        return deepseek_client, DEEPSEEK_MODEL
    return client, MODEL
