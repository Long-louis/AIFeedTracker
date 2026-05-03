# -*- coding: utf-8 -*-
"""Feishu channel registry.

Goal: keep notification routing clean and configurable.

- A "channel" is a string like "webhook:<name>" or "app:<name>".
- Webhook and app targets both live in a local JSON file.
- Business code only passes channel names; it never touches raw endpoints/IDs.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

DEFAULT_CHANNELS_PATH = os.path.join("data", "feishu_channels.json")


@dataclass(frozen=True)
class WebhookConfig:
    url: str
    secret: str = ""


class FeishuChannelRegistry:
    """Loads and resolves Feishu channels."""

    def __init__(self, raw: Dict[str, Any]):
        self._raw = raw or {}
        self._defaults: Dict[str, str] = {}
        self._webhooks: Dict[str, WebhookConfig] = {}

        defaults = self._raw.get("defaults")
        if isinstance(defaults, dict):
            for k in ("content", "alert"):
                v = defaults.get(k)
                if v:
                    self._defaults[k] = str(v).strip()

        webhooks = self._raw.get("webhooks")
        if isinstance(webhooks, dict):
            for name, cfg in webhooks.items():
                if not name:
                    continue
                if not isinstance(cfg, dict):
                    continue
                url = str(cfg.get("url") or "").strip()
                if not url:
                    continue
                secret = str(cfg.get("secret") or "").strip()
                self._webhooks[str(name).strip()] = WebhookConfig(
                    url=url, secret=secret
                )

        # apps: optional app-mode configs (loaded when used)
        self._apps: Dict[str, Dict[str, str]] = {}
        apps = self._raw.get("apps")
        if isinstance(apps, dict):
            for name, cfg in apps.items():
                if not name or not isinstance(cfg, dict):
                    continue
                app_id = str(cfg.get("app_id") or "").strip()
                app_secret = str(cfg.get("app_secret") or "").strip()
                receive_id = str(cfg.get("receive_id") or "").strip()
                receive_id_type = str(cfg.get("receive_id_type") or "").strip()
                if app_id and app_secret and receive_id and receive_id_type:
                    self._apps[str(name).strip()] = {
                        "app_id": app_id,
                        "app_secret": app_secret,
                        "receive_id": receive_id,
                        "receive_id_type": receive_id_type,
                    }

    @classmethod
    def load_from_file(cls, path: str) -> "FeishuChannelRegistry":
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            raise ValueError("feishu_channels.json 必须是 JSON object")
        return cls(raw)

    @classmethod
    def load(cls) -> "FeishuChannelRegistry":
        """Load registry from FEISHU_CHANNELS_CONFIG (or default path).

        No legacy env compatibility by design.
        """

        path = (
            os.getenv("FEISHU_CHANNELS_CONFIG") or ""
        ).strip() or DEFAULT_CHANNELS_PATH
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"未找到飞书通道配置文件: {path}. 请从 data/feishu_channels.json.example 复制并填写。"
            )
        return cls.load_from_file(path)

    def default_channel(self, kind: str) -> Optional[str]:
        return self._defaults.get(kind)

    def resolve_webhook(self, channel: str) -> Optional[WebhookConfig]:
        channel = (channel or "").strip()
        if not channel.startswith("webhook:"):
            return None
        name = channel.split(":", 1)[1].strip()
        if not name:
            return None
        return self._webhooks.get(name)

    def pick_channel(self, kind: str, override_channel: Optional[str]) -> str:
        """返回最终选择的 channel 字符串（例如 webhook:default / app:default）。

        会校验通道是否存在（webhook 或 app）。
        """
        channel = (override_channel or self.default_channel(kind) or "").strip()
        if not channel:
            raise ValueError(f"未配置默认通道 defaults.{kind}")

        if channel.startswith("webhook:"):
            if not self.resolve_webhook(channel):
                raise ValueError(f"webhook 通道不可用或未定义: {channel}")
            return channel

        if channel.startswith("app:"):
            name = channel.split(":", 1)[1].strip()
            if not name or name not in self._apps:
                raise ValueError(f"app 通道不可用或未定义: {channel}")
            return channel

        raise ValueError(f"不支持的通道类型: {channel}")

    def resolve_app(self, channel: str) -> Optional[Dict[str, str]]:
        channel = (channel or "").strip()
        if not channel.startswith("app:"):
            return None
        name = channel.split(":", 1)[1].strip()
        if not name:
            return None
        return self._apps.get(name)
