import importlib
import json
import os
import tempfile
import unittest
from unittest import mock


def _reload_feishu_bot_module():
    # config.py reads env vars at import time; reload to reflect env changes in tests.
    import config
    import services.feishu

    importlib.reload(config)
    importlib.reload(services.feishu)
    return services.feishu


class TestFeishuWebhookPayload(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._env_patch = mock.patch.dict(os.environ, {}, clear=False)
        self._env_patch.start()

    def tearDown(self):
        self._env_patch.stop()

    def test_build_webhook_payload_with_sign(self):
        # 新实现：签名算法是可独立测试的
        os.environ["FEISHU_TEMPLATE_ID"] = "tmpl_test"

        feishu_mod = _reload_feishu_bot_module()

        expected = feishu_mod.FeishuBot._gen_webhook_sign(1730000000, "my-secret")
        self.assertIsInstance(expected, str)
        self.assertTrue(len(expected) > 0)

    async def test_routing_content_vs_alert_channel(self):
        os.environ["FEISHU_TEMPLATE_ID"] = "tmpl_test"
        os.environ["FEISHU_TEMPLATE_VERSION"] = "1.0.0"

        with tempfile.TemporaryDirectory() as d:
            channels_path = os.path.join(d, "feishu_channels.json")
            with open(channels_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "defaults": {
                            "content": "webhook:content",
                            "alert": "webhook:alerts",
                        },
                        "webhooks": {
                            "content": {
                                "url": "https://open.feishu.cn/open-apis/bot/v2/hook/CONTENT",
                                "secret": "",
                            },
                            "alerts": {
                                "url": "https://open.feishu.cn/open-apis/bot/v2/hook/ALERTS",
                                "secret": "",
                            },
                        },
                    },
                    f,
                    ensure_ascii=False,
                )

            os.environ["FEISHU_CHANNELS_CONFIG"] = channels_path

            feishu_mod = _reload_feishu_bot_module()
            bot = feishu_mod.FeishuBot()

            calls = []

            async def _fake_post_webhook(webhook, payload):
                calls.append((webhook.url, payload.get("msg_type")))
                return True

            bot._post_webhook = _fake_post_webhook  # type: ignore[method-assign]

            await bot.send_card_message("测试博主", "B站", "hello")
            await bot.send_system_notification(bot.LEVEL_WARNING, "T", "C")

            self.assertEqual(
                calls[0][0], "https://open.feishu.cn/open-apis/bot/v2/hook/CONTENT"
            )
            self.assertEqual(
                calls[1][0], "https://open.feishu.cn/open-apis/bot/v2/hook/ALERTS"
            )

    async def test_send_card_message_builds_template_card_payload(self):
        os.environ["FEISHU_TEMPLATE_ID"] = "tmpl_test"
        os.environ["FEISHU_TEMPLATE_VERSION"] = "1.0.0"

        with tempfile.TemporaryDirectory() as d:
            channels_path = os.path.join(d, "feishu_channels.json")
            with open(channels_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "defaults": {
                            "content": "webhook:default",
                            "alert": "webhook:default",
                        },
                        "webhooks": {
                            "default": {
                                "url": "https://open.feishu.cn/open-apis/bot/v2/hook/TEST",
                                "secret": "",
                            }
                        },
                    },
                    f,
                    ensure_ascii=False,
                )
            os.environ["FEISHU_CHANNELS_CONFIG"] = channels_path

            feishu_mod = _reload_feishu_bot_module()
            bot = feishu_mod.FeishuBot()

            captured = {}

            async def _fake_post_webhook(webhook, payload):
                captured["url"] = webhook.url
                captured["payload"] = payload
                return True

            bot._post_webhook = _fake_post_webhook  # type: ignore[method-assign]

            ok = await bot.send_card_message("测试博主", "B站", "hello")
            self.assertTrue(ok)

            payload = captured["payload"]
            self.assertEqual(payload["msg_type"], "interactive")
            self.assertIn("card", payload)
            self.assertEqual(payload["card"]["type"], "template")
            data = payload["card"]["data"]
            self.assertEqual(data["template_id"], "tmpl_test")
            self.assertEqual(data["template_version_name"], "1.0.0")
            self.assertEqual(
                data["template_variable"],
                {
                    "Influencer": "测试博主",
                    "platform": "B站",
                    "markdown_content": "hello",
                    "addition_title": "",
                    "addition_subtitle": "",
                },
            )

    async def test_app_channel_routing(self):
        os.environ["FEISHU_TEMPLATE_ID"] = "tmpl_test"
        os.environ["FEISHU_TEMPLATE_VERSION"] = "1.0.0"

        with tempfile.TemporaryDirectory() as d:
            channels_path = os.path.join(d, "feishu_channels.json")
            with open(channels_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "defaults": {"content": "app:default", "alert": "app:alerts"},
                        "apps": {
                            "default": {
                                "app_id": "cli_123",
                                "app_secret": "s1",
                                "receive_id_type": "chat_id",
                                "receive_id": "oc_content",
                            },
                            "alerts": {
                                "app_id": "cli_456",
                                "app_secret": "s2",
                                "receive_id_type": "chat_id",
                                "receive_id": "oc_alert",
                            },
                        },
                    },
                    f,
                    ensure_ascii=False,
                )

            os.environ["FEISHU_CHANNELS_CONFIG"] = channels_path

            feishu_mod = _reload_feishu_bot_module()
            bot = feishu_mod.FeishuBot()

            calls = []

            async def _fake_send_app(
                app_cfg,
                influencer,
                platform,
                markdown_content,
                addition_title="",
                addition_subtitle="",
            ):
                calls.append(
                    (app_cfg["app_id"], influencer, platform, markdown_content)
                )
                return True

            bot._send_via_app_template_card = _fake_send_app  # type: ignore[method-assign]

            await bot.send_card_message("测试博主", "B站", "hello")
            await bot.send_system_notification(bot.LEVEL_WARNING, "T", "C")

            self.assertEqual(calls[0][0], "cli_123")
            self.assertEqual(calls[1][0], "cli_456")
