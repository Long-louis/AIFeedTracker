# -*- coding: utf-8 -*-
"""
配置管理模块

统一管理项目的配置信息，包括环境变量加载和常量定义
"""

import os
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:

    def load_dotenv(*args, **kwargs):
        """备用函数，避免导入错误"""
        pass


# 加载.env文件
project_root = Path(__file__).parent
env_file = project_root / ".env"
if env_file.exists():
    load_dotenv(env_file)

# 飞书配置
# 注意：以下配置需要根据您自己的飞书应用进行修改
# 详见文档: docs/FEISHU_CARD_SETUP.md
FEISHU_CONFIG = {
    "app_id": os.getenv("app_id"),
    "app_secret": os.getenv("app_secret"),
    "template_id": os.getenv("FEISHU_TEMPLATE_ID", "YOUR_TEMPLATE_ID"),  # 替换为您的卡片模板ID
    "template_version_name": os.getenv("FEISHU_TEMPLATE_VERSION", "1.0.0"),  # 替换为您的卡片版本号
    "user_open_id": os.getenv("FEISHU_USER_OPEN_ID", "YOUR_USER_OPEN_ID"),  # 替换为接收消息的用户open_id
}

# B站配置
BILIBILI_CONFIG = {
    "SESSDATA": os.getenv("SESSDATA"),
    "bili_jct": os.getenv("bili_jct"),
    "buvid3": os.getenv("buvid3"),
    "DedeUserID": os.getenv("DedeUserID"),
    "DedeUserID__ckMd5": os.getenv("DedeUserID__ckMd5"),
    "refresh_token": os.getenv("refresh_token"),  # 添加refresh_token支持
}

# API配置
BILI_SPACE_API = "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space"
BILI_VIDEO_API = "https://api.bilibili.com/x/web-interface/view"

# User-Agent配置（从.env读取，如果没有则使用默认值）
USER_AGENT = (
    os.getenv("USER_AGENT")
    or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# AI总结服务配置
AI_CONFIG = {
    "service": os.getenv("AI_SERVICE", "deepseek"),
    "api_key": os.getenv("AI_API_KEY"),
    "base_url": os.getenv("AI_BASE_URL"),  # 可选，不设置则根据service自动选择
    "model": os.getenv("AI_MODEL"),  # 可选，不设置则根据service自动选择
}

# 反爬虫配置
ANTI_BAN_CONFIG = {
    "user_agent": USER_AGENT,  # 使用配置的User-Agent
    "request_delay": (1, 3),  # 请求间隔（秒）
    "timeout": 30,
}


def build_bilibili_cookie() -> Optional[str]:
    """构建B站请求所需的Cookie字符串"""
    parts = []
    for key, value in BILIBILI_CONFIG.items():
        if value:
            parts.append(f"{key}={value}")
    return "; ".join(parts) if parts else None


def get_config_status() -> dict:
    """获取配置状态，用于诊断"""
    return {
        "env_file_exists": env_file.exists(),
        "feishu_configured": bool(
            FEISHU_CONFIG["app_id"] and FEISHU_CONFIG["app_secret"]
        ),
        "bilibili_configured": bool(BILIBILI_CONFIG["SESSDATA"]),
        "cookie_available": bool(build_bilibili_cookie()),
    }


if __name__ == "__main__":
    # 配置状态检查
    status = get_config_status()
    print("配置状态检查:")
    for key, value in status.items():
        emoji = "✅" if value else "❌"
        print(f"  {emoji} {key}: {value}")

    if status["cookie_available"]:
        print(f"\nB站Cookie: {build_bilibili_cookie()[:50]}...")
