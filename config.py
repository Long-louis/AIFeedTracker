# -*- coding: utf-8 -*-
"""
配置管理模块

统一管理项目的配置信息，包括环境变量加载和常量定义
"""

import json
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

# ============================================
# Feishu 配置（通过 channels registry 路由 webhook/app 通道）
# ============================================

# 模板卡片配置
FEISHU_TEMPLATE_ID = os.getenv("FEISHU_TEMPLATE_ID", "YOUR_TEMPLATE_ID")
FEISHU_TEMPLATE_VERSION = os.getenv("FEISHU_TEMPLATE_VERSION", "1.0.0")

# 飞书应用配置（用于上传图片等需要 API 的功能）
FEISHU_APP_ID = os.getenv("app_id", "")
FEISHU_APP_SECRET = os.getenv("app_secret", "")

# 通道注册表配置文件路径（默认 data/feishu_channels.json）
FEISHU_CHANNELS_CONFIG = os.getenv(
    "FEISHU_CHANNELS_CONFIG", str(project_root / "data" / "feishu_channels.json")
)

# B站配置
BILIBILI_CONFIG = {
    "SESSDATA": os.getenv("SESSDATA"),
    "bili_jct": os.getenv("bili_jct"),
    "buvid3": os.getenv("buvid3"),
    "buvid4": os.getenv("buvid4"),
    # 兼容两种写法
    "DedeUserID": os.getenv("DedeUserID") or os.getenv("dedeuserid"),
    "DedeUserID__ckMd5": os.getenv("DedeUserID__ckMd5"),
    "ac_time_value": os.getenv("ac_time_value"),
    "refresh_token": os.getenv("refresh_token"),
}

# API配置
BILI_SPACE_API = "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space"
BILI_VIDEO_API = "https://api.bilibili.com/x/web-interface/view"

# User-Agent配置（从.env读取，如果没有则使用默认值）
USER_AGENT = (
    os.getenv("USER_AGENT")
    or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _get_env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def _get_env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    normalized_value = value.strip().lower()
    if normalized_value in {"1", "true", "yes", "on"}:
        return True
    if normalized_value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean value for {name}: {value}")


def _get_env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


def load_local_asr_config() -> dict:
    return {
        "enabled": _get_env_bool("LOCAL_ASR_ENABLED", False),
        "provider": _get_env_str("LOCAL_ASR_PROVIDER", "sensevoice_api"),
        "api_url": _get_env_str("ASR_API_URL", "http://127.0.0.1:8900/v1/transcribe"),
        "api_timeout_seconds": _get_env_int("ASR_API_TIMEOUT_SECONDS", 300),
        "temp_dir": _get_env_str("LOCAL_ASR_TEMP_DIR", "./data/temp_asr"),
        "max_audio_minutes": _get_env_int("LOCAL_ASR_MAX_AUDIO_MINUTES", 90),
        "cleanup_temp_files": _get_env_bool("LOCAL_ASR_CLEANUP_TEMP_FILES", True),
    }


def load_feishu_docs_config() -> dict:
    return {
        "enabled": _get_env_bool("FEISHU_DOCS_ENABLED", False),
        "app_id": _get_env_str("FEISHU_DOCS_APP_ID", FEISHU_APP_ID),
        "app_secret": _get_env_str("FEISHU_DOCS_APP_SECRET", FEISHU_APP_SECRET),
        "wiki_space_id": _get_env_str("FEISHU_DOCS_WIKI_SPACE_ID", ""),
        "tenant_host": _get_env_str("FEISHU_DOCS_TENANT_HOST", ""),
        "root_node_token": _get_env_str("FEISHU_DOCS_ROOT_NODE_TOKEN", ""),
        "root_title": _get_env_str("FEISHU_DOCS_ROOT_TITLE", "AI视频知识库"),
        "state_path": _get_env_str(
            "FEISHU_DOCS_STATE_PATH",
            str(project_root / "data" / "feishu_doc_state.json"),
        ),
        "request_timeout_seconds": _get_env_int(
            "FEISHU_DOCS_REQUEST_TIMEOUT_SECONDS", 30
        ),
    }


# AI总结服务配置
AI_CONFIG = {
    "service": os.getenv("AI_SERVICE", "deepseek"),
    "api_key": os.getenv("AI_API_KEY"),
    "base_url": os.getenv("AI_BASE_URL"),  # 可选，不设置则根据service自动选择
    "model": os.getenv("AI_MODEL"),  # 可选，不设置则根据service自动选择
    # 适配长视频总结：按模型上下文窗口做 token 预算（DeepSeek 文档：128K）
    "context_window_tokens": int(os.getenv("AI_CONTEXT_WINDOW_TOKENS", "128000")),
    # 推理模型(deepseek-v4-flash)的 reasoning tokens 也计入 max_tokens，
    # 4000 不够时 content 返回 null。提升到 8000 留足 reasoning 预算。
    "max_output_tokens": int(os.getenv("AI_MAX_OUTPUT_TOKENS", "8000")),
    # 分段(map)阶段每段输出 token 上限（推理模型需要更大预算）
    "map_max_output_tokens": int(os.getenv("AI_MAP_MAX_OUTPUT_TOKENS", "2000")),
    # DeepSeek V4 推理强度: low/high/max。视频总结用 low 即可，
    # 减少 reasoning token 消耗，降低成本，避免 content 为空。
    "reasoning_effort": os.getenv("AI_REASONING_EFFORT", "low"),
    # tiktoken 编码名（DeepSeek OpenAI-compat 通常可用 cl100k_base；如你确认其它编码可覆盖）
    "token_encoding": os.getenv("AI_TOKEN_ENCODING", "cl100k_base"),
}

def load_feed_config() -> dict:
    """监控聚合流与分层延迟配置（档位 A + C）。"""
    return {
        # aggregated=聚合流（每轮 1 次调用拉全部关注）；legacy=逐博主轮询（旧逻辑）
        "mode": _get_env_str("FEED_MODE", "aggregated"),
        "poll_fast_seconds": _get_env_int("FEED_POLL_FAST_SECONDS", 300),
        "poll_normal_seconds": _get_env_int("FEED_POLL_NORMAL_SECONDS", 600),
        "poll_quiet_seconds": _get_env_int("FEED_POLL_QUIET_SECONDS", 3600),
        "poll_jitter_ratio": _get_env_int("FEED_POLL_JITTER_PCT", 25) / 100.0,
        # 聚合流单次最多翻页数（避免漏检被挤出首页的关注博主动态）
        "feed_max_pages": _get_env_int("FEED_MAX_PAGES", 5),
        # 评论轮询解耦循环基准间隔（秒）；仍受逐博主 comment_poll_interval_seconds 节流
        "comment_loop_seconds": _get_env_int("FEED_COMMENT_LOOP_SECONDS", 600),
        "market_session_enabled": _get_env_bool("MARKET_SESSION_ENABLED", True),
        # 盘中窗口，如 "mon-fri 09:15-15:00"
        "market_session_windows": _get_env_str(
            "MARKET_SESSION_WINDOWS", "mon-fri 09:15-15:00"
        ),
        # 延迟总结批量队列 cron（仅 summarize_mode=deferred 的视频走此队列）
        "summary_batch_cron": _get_env_str("FEED_SUMMARY_BATCH_CRON", "0 * * * *"),
        # 深夜时段（24h 制，quiet 周期生效）
        "quiet_hours_start": _get_env_int("QUIET_HOURS_START", 0),
        "quiet_hours_end": _get_env_int("QUIET_HOURS_END", 6),
    }


LOCAL_ASR_CONFIG = load_local_asr_config()
FEISHU_DOCS_CONFIG = load_feishu_docs_config()
FEED_CONFIG = load_feed_config()

# 反爬虫配置
ANTI_BAN_CONFIG = {
    "user_agent": USER_AGENT,  # 使用配置的User-Agent
    "request_delay": (1, 3),  # 请求间隔（秒）
    "timeout": 30,  # 常规API请求超时
    "audio_download_timeout": 120,  # 音频文件下载超时（大文件需要更长）
}


def build_bilibili_cookie() -> Optional[str]:
    """构建B站请求所需的Cookie字符串（仅Cookie字段）"""
    cookie_keys = (
        "SESSDATA",
        "bili_jct",
        "buvid3",
        "buvid4",
        "DedeUserID",
        "DedeUserID__ckMd5",
    )
    parts = []
    for key in cookie_keys:
        value = BILIBILI_CONFIG.get(key)
        if value:
            parts.append(f"{key}={value}")
    return "; ".join(parts) if parts else None


def build_bilibili_credential():
    """创建 bilibili-api-python 的 Credential 对象（若缺关键字段则返回 None）"""

    try:
        from bilibili_api import Credential
    except Exception:
        return None

    cfg = BILIBILI_CONFIG
    if not cfg.get("SESSDATA"):
        return None

    return Credential(
        sessdata=cfg.get("SESSDATA"),
        bili_jct=cfg.get("bili_jct"),
        buvid3=cfg.get("buvid3"),
        buvid4=cfg.get("buvid4"),
        dedeuserid=cfg.get("DedeUserID"),
        ac_time_value=cfg.get("ac_time_value"),
    )


def apply_bilibili_config(values: dict) -> None:
    """将新的B站凭证写入进程环境与运行时配置。"""
    allowed_keys = {
        "SESSDATA",
        "bili_jct",
        "buvid3",
        "buvid4",
        "DedeUserID",
        "DedeUserID__ckMd5",
        "ac_time_value",
        "refresh_token",
    }
    for key, value in values.items():
        if key not in allowed_keys:
            continue
        if not value:
            continue
        os.environ[str(key)] = str(value)
        BILIBILI_CONFIG[str(key)] = str(value)


def _load_bilibili_auth_data(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("bilibili_auth.json 必须是 JSON object")
    return data


_AUTH_DATA_PATH = project_root / "data" / "bilibili_auth.json"
_AUTH_DATA = _load_bilibili_auth_data(_AUTH_DATA_PATH)
if _AUTH_DATA:
    apply_bilibili_config(_AUTH_DATA)


def get_config_status() -> dict:
    """获取配置状态，用于诊断"""
    feishu_channels_exists = Path(FEISHU_CHANNELS_CONFIG).exists()
    return {
        "env_file_exists": env_file.exists(),
        "feishu_configured": bool(
            feishu_channels_exists
            and FEISHU_TEMPLATE_ID
            and FEISHU_TEMPLATE_ID != "YOUR_TEMPLATE_ID"
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
