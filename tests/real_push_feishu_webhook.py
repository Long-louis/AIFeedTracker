import importlib
import os
import time
import unittest


def _reload_feishu_bot_module():
    # config.py reads env vars at import time; reload to reflect .env changes.
    import config
    import services.feishu

    importlib.reload(config)
    importlib.reload(services.feishu)
    return services.feishu


class TestFeishuWebhookRealPush(unittest.IsolatedAsyncioTestCase):
    async def test_real_push_text(self):
        try:
            feishu_mod = _reload_feishu_bot_module()
            bot = feishu_mod.FeishuBot()
        except FileNotFoundError:
            self.skipTest(
                "需要配置 data/feishu_channels.json（从 .example 复制并填写）才能真实推送"
            )

        if (
            not os.getenv("FEISHU_TEMPLATE_ID")
            or os.getenv("FEISHU_TEMPLATE_ID") == "YOUR_TEMPLATE_ID"
        ):
            self.skipTest("需要设置 FEISHU_TEMPLATE_ID 才能真实推送")

        now = time.strftime("%Y-%m-%d %H:%M:%S")
        ok = await bot.send_text(f"[AIFeedTracker 测试] 文本推送 {now}")
        self.assertTrue(ok)

    async def test_real_push_template_card(self):
        try:
            feishu_mod = _reload_feishu_bot_module()
            bot = feishu_mod.FeishuBot()
        except FileNotFoundError:
            self.skipTest(
                "需要配置 data/feishu_channels.json（从 .example 复制并填写）才能真实推送"
            )

        if (
            not os.getenv("FEISHU_TEMPLATE_ID")
            or os.getenv("FEISHU_TEMPLATE_ID") == "YOUR_TEMPLATE_ID"
        ):
            self.skipTest("需要设置 FEISHU_TEMPLATE_ID 才能真实推送模板卡片")

        now = time.strftime("%Y-%m-%d %H:%M:%S")
        ok = await bot.send_card_message(
            "AIFeedTracker 测试",
            "Feishu Webhook",
            f"这是一条真实推送测试卡片。\n\n时间：{now}",
        )
        self.assertTrue(ok)
