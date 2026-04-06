# -*- coding: utf-8 -*-

import importlib
import os
import unittest


def _reload_modules():
    # config.py reads env vars at import time; reload to reflect .env changes.
    import config
    import services.feishu

    importlib.reload(config)
    importlib.reload(services.feishu)
    return config, services.feishu


class TestAISummaryEndToEndRealPush(unittest.IsolatedAsyncioTestCase):
    async def test_real_end_to_end_subtitle_ai_feishu(self):
        config, feishu_mod = _reload_modules()

        try:
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

        if not os.getenv("AI_API_KEY"):
            self.skipTest("需要设置 AI_API_KEY 才能进行真实AI总结")

        from services.ai_summary.service import AISummaryService

        video_url = os.getenv(
            "E2E_TEST_VIDEO_URL", "https://www.bilibili.com/video/BV1v9BEBkEZF"
        )

        svc = AISummaryService(feishu_bot=bot)
        ok, message, links, contents = await svc.summarize_videos([video_url])

        summary = contents[0] if contents else ""
        md = (
            "**[全链条测试] 字幕→AI总结→飞书推送**\n\n"
            f"视频: {video_url}\n\n"
            f"结果: {'✅' if ok else '❌'} {message}\n\n"
            "---\n\n"
            f"{summary}"
        )

        await bot.send_card_message(
            "AIFeedTracker 全链条测试",
            "AISummaryService",
            md,
        )

        # 断言：如果失败，也必须有明确原因，方便从推送直接定位
        if not ok:
            self.assertTrue(isinstance(summary, str) and len(summary) > 0)
            self.assertIn("❌", summary)
            self.assertIn(":", summary)
