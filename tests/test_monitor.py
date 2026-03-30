# -*- coding: utf-8 -*-

import logging
import time
import unittest

from services.monitor import MonitorService


class TestMonitorChargeDynamic(unittest.TestCase):
    def test_is_charge_dynamic_by_additional_type(self):
        item = {
            "modules": {
                "module_dynamic": {
                    "additional": {
                        "type": "ONLYFANS",
                    }
                }
            }
        }
        self.assertTrue(MonitorService.is_charge_dynamic(item))

    def test_is_charge_dynamic_by_badge_text(self):
        item = {
            "modules": {
                "module_dynamic": {
                    "major": {
                        "opus": {
                            "badge": {"text": "充电专属"},
                        }
                    }
                }
            }
        }
        self.assertTrue(MonitorService.is_charge_dynamic(item))

    def test_is_charge_dynamic_false_when_no_signals(self):
        item = {
            "modules": {
                "module_dynamic": {
                    "major": {"type": "OPUS"},
                }
            }
        }
        self.assertFalse(MonitorService.is_charge_dynamic(item))


class TestMonitorParseText(unittest.TestCase):
    def test_parse_text_live_dynamic_should_include_title_and_link(self):
        item = {
            "modules": {
                "module_dynamic": {
                    "major": {
                        "type": "MAJOR_TYPE_LIVE_RCMD",
                        "live_rcmd": {
                            "title": "今晚8点开播：聊聊大盘",
                            "jump_url": "https://live.bilibili.com/123",
                            "cover": "https://i0.hdslb.com/bfs/live/cover.jpg",
                            "uname": "测试UP",
                        },
                    },
                    "desc": {
                        "text": "",
                    },
                }
            }
        }
        text = MonitorService.parse_text_from_item(item)
        self.assertTrue(isinstance(text, str))
        self.assertIn("开播通知", text)
        self.assertIn("今晚8点开播", text)
        self.assertIn("https://live.bilibili.com/123", text)


class _FakeFeishuBot:
    LEVEL_INFO = "INFO"
    LEVEL_WARNING = "WARNING"

    def __init__(self):
        self.notifications = []
        self.uploaded_paths = []

    async def upload_local_image(self, path):
        self.uploaded_paths.append(path)
        return "img_key"

    async def send_system_notification(self, level, title, content):
        self.notifications.append((level, title, content))


class _FakeAuth:
    QR_CODE_PATH = "temp/bilibili_qrcode.png"

    def __init__(self):
        self.last_notify_ts = 0.0
        self.pending_reason = None
        self.active_qr = False
        self.start_count = 0
        self.poll_result = ("none", None)

    def get_qr_last_notify_ts(self):
        return self.last_notify_ts

    def set_qr_last_notify_ts(self, ts):
        self.last_notify_ts = float(ts)

    def has_active_qr_login(self):
        return self.active_qr

    async def start_qr_login(self):
        self.active_qr = True
        self.start_count += 1
        return self.QR_CODE_PATH

    async def poll_qr_login(self):
        return self.poll_result

    def get_qr_pending_notify_reason(self):
        return self.pending_reason

    def set_qr_pending_notify_reason(self, reason):
        self.pending_reason = reason

    def clear_qr_pending_notify_reason(self):
        self.pending_reason = None

    def set_credential_values(self, values):
        return None


class TestMonitorQrNotification(unittest.IsolatedAsyncioTestCase):
    def _build_monitor(self, hour):
        monitor = MonitorService.__new__(MonitorService)
        monitor.feishu_bot = _FakeFeishuBot()
        monitor.auth = _FakeAuth()
        monitor.comment_fetcher = None
        monitor.summarizer = None
        monitor.credential = object()
        monitor.logger = logging.getLogger("tests.test_monitor.qr")
        monitor._get_current_local_hour = lambda: hour
        return monitor

    async def test_notify_qr_login_needed_force_bypasses_interval_in_daytime(self):
        monitor = self._build_monitor(hour=10)
        monitor.auth.set_qr_last_notify_ts(time.time())

        await monitor._notify_qr_login_needed("二维码已过期，请重新扫码", force=True)

        self.assertEqual(monitor.auth.start_count, 1)
        self.assertEqual(len(monitor.feishu_bot.notifications), 1)

    async def test_notify_qr_login_needed_defers_during_quiet_hours(self):
        monitor = self._build_monitor(hour=2)

        await monitor._notify_qr_login_needed("未配置或已失效")

        self.assertEqual(monitor.auth.start_count, 0)
        self.assertEqual(len(monitor.feishu_bot.notifications), 0)
        self.assertEqual(monitor.auth.get_qr_pending_notify_reason(), "未配置或已失效")

    async def test_poll_qr_login_status_resends_pending_notify_after_quiet_hours(self):
        monitor = self._build_monitor(hour=10)
        monitor.auth.set_qr_pending_notify_reason("凭证刷新失败")

        await monitor._poll_qr_login_status()

        self.assertEqual(monitor.auth.start_count, 1)
        self.assertEqual(len(monitor.feishu_bot.notifications), 1)
        self.assertIsNone(monitor.auth.get_qr_pending_notify_reason())


if __name__ == "__main__":
    unittest.main()
