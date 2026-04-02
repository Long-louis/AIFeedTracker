# -*- coding: utf-8 -*-
"""
二维码扫码登录端到端测试

说明：
- 运行后会向飞书 alert 通道推送二维码
- 请在超时时间内用手机扫码完成登录
"""

import asyncio
import os
import time
import unittest

from services import FeishuBot, MonitorService


@unittest.skipUnless(
    os.getenv("RUN_QR_LOGIN_E2E") == "1",
    "manual QR login e2e test; set RUN_QR_LOGIN_E2E=1 to enable",
)
class TestQrLoginFlow(unittest.IsolatedAsyncioTestCase):
    async def test_qr_login_notify_and_update(self):
        feishu_bot = FeishuBot()
        monitor = MonitorService(feishu_bot=feishu_bot, summarizer=None)

        # 强制走二维码通知流程
        monitor.credential = None
        if monitor.comment_fetcher:
            monitor.comment_fetcher.credential = None

        monitor.auth.set_qr_last_notify_ts(0)

        await monitor._notify_qr_login_needed("测试二维码登录流程")

        self.assertTrue(monitor.auth.has_active_qr_login())

        start_time = time.time()
        timeout_seconds = 600

        while time.time() - start_time < timeout_seconds:
            await monitor._poll_qr_login_status()
            if not monitor.auth.has_active_qr_login():
                break
            await asyncio.sleep(2)

        self.assertFalse(monitor.auth.has_active_qr_login(), "扫码超时或未完成")
        self.assertTrue(
            monitor.credential and getattr(monitor.credential, "sessdata", None),
            "扫码完成后未更新凭证",
        )
