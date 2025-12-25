# -*- coding: utf-8 -*-
"""Feishu webhook sender (registry-driven).

Design goals:
- Webhook-only (no app mode) for maximum simplicity.
- All routing is done by a local channel registry file (data/feishu_channels.json).
- Business code only passes channel names like "webhook:default".
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, Optional

import aiohttp

from config import (
    FEISHU_APP_ID,
    FEISHU_APP_SECRET,
    FEISHU_TEMPLATE_ID,
    FEISHU_TEMPLATE_VERSION,
)

from .feishu_channels import FeishuChannelRegistry, WebhookConfig


def _try_import_lark_oapi():
    try:
        import lark_oapi as lark  # type: ignore
        from lark_oapi.api.im.v1 import (
            CreateImageRequest,
            CreateImageRequestBody,
            CreateMessageRequest,
            CreateMessageRequestBody,
        )

        return {
            "lark": lark,
            "CreateImageRequest": CreateImageRequest,
            "CreateImageRequestBody": CreateImageRequestBody,
            "CreateMessageRequest": CreateMessageRequest,
            "CreateMessageRequestBody": CreateMessageRequestBody,
        }
    except Exception:
        return None


class FeishuBot:
    # 通知级别常量（保持现有调用方语义）
    LEVEL_INFO = "INFO"
    LEVEL_WARNING = "WARNING"
    LEVEL_ERROR = "ERROR"

    LEVEL_EMOJI = {
        "INFO": "✅",
        "WARNING": "⚠️",
        "ERROR": "❌",
    }

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.template_id = FEISHU_TEMPLATE_ID
        self.template_version_name = FEISHU_TEMPLATE_VERSION
        self.registry = FeishuChannelRegistry.load()

        # 用于图片上传的应用配置（从 .env 读取）
        self._image_upload_app_cfg: Optional[Dict[str, str]] = None
        if FEISHU_APP_ID and FEISHU_APP_SECRET:
            self._image_upload_app_cfg = {
                "app_id": FEISHU_APP_ID,
                "app_secret": FEISHU_APP_SECRET,
            }
            self.logger.info("已配置飞书应用凭证，图片上传功能可用")

        if not self.template_id or self.template_id == "YOUR_TEMPLATE_ID":
            self.logger.warning("未配置 FEISHU_TEMPLATE_ID：模板卡片将无法发送")

    @staticmethod
    def _gen_webhook_sign(timestamp: int, secret: str) -> str:
        """Feishu webhook v2 sign: base64(hmac_sha256(msg=ts+'\n'+secret, key=secret))."""

        msg = f"{timestamp}\n{secret}".encode("utf-8")
        key = secret.encode("utf-8")
        digest = hmac.new(key, msg, digestmod=hashlib.sha256).digest()
        return base64.b64encode(digest).decode("utf-8")

    def _build_template_card(
        self,
        *,
        influencer: str,
        platform: str,
        markdown_content: str,
        addition_title: str = "",
        addition_subtitle: str = "",
    ) -> Dict[str, Any]:
        if not self.template_id or self.template_id == "YOUR_TEMPLATE_ID":
            raise ValueError("未配置 FEISHU_TEMPLATE_ID")

        return {
            "type": "template",
            "data": {
                "template_id": self.template_id,
                "template_version_name": self.template_version_name,
                "template_variable": {
                    "Influencer": influencer,
                    "platform": platform,
                    "markdown_content": markdown_content,
                    "addition_title": addition_title,
                    "addition_subtitle": addition_subtitle,
                },
            },
        }

    async def _post_webhook(
        self, webhook: WebhookConfig, payload: Dict[str, Any]
    ) -> bool:
        send_payload = dict(payload)

        if webhook.secret:
            ts = int(time.time())
            send_payload["timestamp"] = str(ts)
            send_payload["sign"] = self._gen_webhook_sign(ts, webhook.secret)

        # 调试日志：打印发送的 template_variable
        if "card" in send_payload and "data" in send_payload["card"]:
            tv = send_payload["card"]["data"].get("template_variable", {})
            self.logger.info(
                f"发送卡片 template_variable: addition_title={tv.get('addition_title')!r}, Influencer={tv.get('Influencer')!r}"
            )

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook.url,
                    json=send_payload,
                    headers={"Content-Type": "application/json; charset=utf-8"},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    data = await resp.json(content_type=None)

            code = data.get("code")
            if resp.status == 200 and code == 0:
                return True

            self.logger.error(f"Webhook 发送失败: http={resp.status}, resp={data}")
            return False
        except Exception as e:
            self.logger.error(f"Webhook 发送异常: {e}")
            return False

    def _get_webhook_for(
        self, kind: str, override_channel: Optional[str]
    ) -> WebhookConfig:
        channel = self.registry.pick_channel(kind, override_channel)
        # Resolve and ensure it's a webhook channel
        if channel.startswith("webhook:"):
            webhook = self.registry.resolve_webhook(channel)
            if not webhook:
                raise ValueError(f"通道未定义或不可用: {channel}")
            return webhook
        raise ValueError(f"通道类型不为 webhook: {channel}")

    def _get_channel(self, kind: str, override_channel: Optional[str]):
        """返回 (type, channel, config) 三元组，type in {'webhook','app'}"""
        channel = self.registry.pick_channel(kind, override_channel)
        if channel.startswith("webhook:"):
            wh = self.registry.resolve_webhook(channel)
            if not wh:
                raise ValueError(f"webhook 通道未定义: {channel}")
            return "webhook", channel, wh
        if channel.startswith("app:"):
            app = self.registry.resolve_app(channel)
            if not app:
                raise ValueError(f"app 通道未定义: {channel}")
            return "app", channel, app
        raise ValueError(f"不支持的通道: {channel}")

    async def upload_image_to_feishu(
        self, image_url: str, app_cfg: Dict[str, str]
    ) -> Optional[str]:
        """上传图片到飞书（依赖飞书应用接口）。返回 image_key 或 None。"""
        if not app_cfg:
            return None

        sdk = _try_import_lark_oapi()
        if not sdk:
            return None

        try:
            client = (
                sdk["lark"]
                .Client.builder()
                .app_id(app_cfg["app_id"])
                .app_secret(app_cfg["app_secret"])
                .log_level(sdk["lark"].LogLevel.ERROR)
                .build()
            )

            async with aiohttp.ClientSession() as session:
                # B站图片需要 Referer 头才能访问
                headers = {
                    "Referer": "https://www.bilibili.com/",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                }
                async with session.get(image_url, headers=headers) as response:
                    if response.status != 200:
                        self.logger.warning(
                            f"下载图片失败: {image_url}, status: {response.status}"
                        )
                        return None
                    image_data = await response.read()

            import tempfile

            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
                temp_file.write(image_data)
                temp_file_path = temp_file.name

            try:
                with open(temp_file_path, "rb") as image_file:
                    request = (
                        sdk["CreateImageRequest"]
                        .builder()
                        .request_body(
                            sdk["CreateImageRequestBody"]
                            .builder()
                            .image_type("message")
                            .image(image_file)
                            .build()
                        )
                        .build()
                    )

                    response = client.im.v1.image.create(request)

                    if response.success():
                        image_key = response.data.image_key
                        self.logger.info(f"图片上传成功，image_key: {image_key}")
                        return image_key
                    else:
                        self.logger.error(f"图片上传失败: {response.msg}")
                        return None
            finally:
                try:
                    os.unlink(temp_file_path)
                except Exception:
                    pass

        except Exception as e:
            self.logger.error(f"上传图片到飞书异常: {e}")
            return None

    async def convert_images_in_markdown(
        self, markdown_content: str, app_cfg: Dict[str, str]
    ) -> str:
        """将Markdown中的图片URL转换为飞书image key（仅在 app 模式使用）。"""
        if not app_cfg:
            return markdown_content

        image_pattern = r"!\[([^\]]*)\]\(([^)]+)\)"
        import re

        matches = re.findall(image_pattern, markdown_content)
        if not matches:
            return markdown_content

        converted_content = markdown_content
        for alt_text, image_url in matches:
            if image_url.startswith("img_"):
                continue
            image_key = await self.upload_image_to_feishu(image_url, app_cfg)
            if image_key:
                old_pattern = f"![{alt_text}]({image_url})"
                new_pattern = f"![{alt_text}]({image_key})"
                converted_content = converted_content.replace(old_pattern, new_pattern)
                self.logger.info(f"图片转换成功: {image_url} -> {image_key}")
            else:
                self.logger.warning(f"图片转换失败，保持原链接: {image_url}")

        return converted_content

    async def _send_via_app_template_card(
        self,
        app_cfg: Dict[str, str],
        influencer: str,
        platform: str,
        markdown_content: str,
        addition_title: str = "",
        addition_subtitle: str = "",
    ) -> bool:
        """使用飞书应用机器人发送模板卡片（懒加载 lark-oapi）。"""
        sdk = _try_import_lark_oapi()
        if not sdk:
            self.logger.error("lark-oapi 不可用: 无法使用 app 通道发送卡片消息")
            return False

        if not app_cfg.get("user_open_id"):
            self.logger.error("app 通道未配置 user_open_id，无法发送消息")
            return False

        try:
            self.logger.info("开始处理Markdown中的图片链接（app模式）...")
            converted = await self.convert_images_in_markdown(markdown_content, app_cfg)

            client = (
                sdk["lark"]
                .Client.builder()
                .app_id(app_cfg["app_id"])
                .app_secret(app_cfg["app_secret"])
                .log_level(sdk["lark"].LogLevel.ERROR)
                .build()
            )

            card_content = {
                "data": {
                    "template_id": self.template_id,
                    "template_version_name": self.template_version_name,
                    "template_variable": {
                        "Influencer": influencer,
                        "platform": platform,
                        "markdown_content": converted,
                        "addition_title": addition_title,
                        "addition_subtitle": addition_subtitle,
                    },
                },
                "type": "template",
            }

            request = (
                sdk["CreateMessageRequest"]
                .builder()
                .receive_id_type("open_id")
                .request_body(
                    sdk["CreateMessageRequestBody"]
                    .builder()
                    .receive_id(app_cfg.get("user_open_id"))
                    .msg_type("interactive")
                    .content(json.dumps(card_content, ensure_ascii=False))
                    .build()
                )
                .build()
            )

            response = client.im.v1.message.create(request)
            if response.success():
                self.logger.info(f"飞书应用卡片发送成功: {influencer} - {platform}")
                return True
            self.logger.error(f"飞书应用卡片发送失败: {response.msg}")
            return False
        except Exception as e:
            self.logger.error(f"通过 app 发送卡片失败: {e}")
            return False

    async def send_card_message(
        self,
        influencer: str,
        platform: str,
        markdown_content: str,
        channel: Optional[str] = None,
        addition_title: str = "",
        addition_subtitle: str = "",
    ) -> bool:
        """发送内容卡片。

        - 默认走 defaults.content
        - creator 可传入 channel 覆盖（例如 webhook:vip）
        - 如果配置了飞书应用凭证，会自动转换 Markdown 中的图片
        """

        try:
            ch_type, ch_name, cfg = self._get_channel("content", channel)

            # 如果有应用凭证，转换 Markdown 中的图片 URL 为飞书 image_key
            processed_content = markdown_content
            if self._image_upload_app_cfg:
                processed_content = await self.convert_images_in_markdown(
                    markdown_content, self._image_upload_app_cfg
                )

            card = self._build_template_card(
                influencer=influencer,
                platform=platform,
                markdown_content=processed_content,
                addition_title=addition_title,
                addition_subtitle=addition_subtitle,
            )
            payload: Dict[str, Any] = {"msg_type": "interactive", "card": card}

            if ch_type == "webhook":
                return await self._post_webhook(cfg, payload)

            # app channel
            if ch_type == "app":
                ok = await self._send_via_app_template_card(
                    cfg,
                    influencer,
                    platform,
                    processed_content,
                    addition_title,
                    addition_subtitle,
                )
                return bool(ok)

            raise ValueError(f"未知通道类型: {ch_type}")
        except Exception as e:
            self.logger.error(f"发送飞书卡片失败: {e}")
            return False

    async def send_text(self, text: str, channel: Optional[str] = None) -> bool:
        """发送纯文本消息（用于调试/测试）。"""

        try:
            ch_type, ch_name, cfg = self._get_channel("content", channel)

            if ch_type == "webhook":
                payload: Dict[str, Any] = {
                    "msg_type": "text",
                    "content": {"text": text},
                }
                return await self._post_webhook(cfg, payload)

            # app: send as text via app message API
            if ch_type == "app":
                sdk = _try_import_lark_oapi()
                if not sdk:
                    self.logger.error("lark-oapi 不可用: 无法使用 app 通道发送文本消息")
                    return False
                try:
                    client = (
                        sdk["lark"]
                        .Client.builder()
                        .app_id(cfg["app_id"])
                        .app_secret(cfg["app_secret"])
                        .log_level(sdk["lark"].LogLevel.ERROR)
                        .build()
                    )

                    request = (
                        sdk["CreateMessageRequest"]
                        .builder()
                        .receive_id_type("open_id")
                        .request_body(
                            sdk["CreateMessageRequestBody"]
                            .builder()
                            .receive_id(cfg.get("user_open_id"))
                            .msg_type("text")
                            .content(text)
                            .build()
                        )
                        .build()
                    )

                    response = client.im.v1.message.create(request)
                    return response.success()
                except Exception as e:
                    self.logger.error(f"通过 app 发送文本失败: {e}")
                    return False

            raise ValueError(f"未知通道类型: {ch_type}")
        except Exception as e:
            self.logger.error(f"发送飞书文本失败: {e}")
            return False

    async def send_system_notification(
        self, level: str, title: str, content: str
    ) -> bool:
        """发送告警通知（走 defaults.alert）。"""

        emoji = self.LEVEL_EMOJI.get(level, "📢")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        markdown = f"**{emoji} {level}**\n\n**{title}**\n\n{content}\n\n---\n时间: {ts}"

        try:
            ch_type, ch_name, cfg = self._get_channel("alert", None)
            card = self._build_template_card(
                influencer="系统通知",
                platform="AIFeedTracker",
                markdown_content=markdown,
            )
            payload: Dict[str, Any] = {"msg_type": "interactive", "card": card}

            if ch_type == "webhook":
                return await self._post_webhook(cfg, payload)

            if ch_type == "app":
                ok = await self._send_via_app_template_card(
                    cfg, "系统通知", "AIFeedTracker", markdown
                )
                return bool(ok)

            raise ValueError(f"未知通道类型: {ch_type}")
        except Exception as e:
            self.logger.error(f"发送系统通知失败: {e}")
            return False
