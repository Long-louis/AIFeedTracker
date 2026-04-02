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


class TestMonitorDynamicRendering(unittest.TestCase):
    def setUp(self):
        self.monitor = MonitorService.__new__(MonitorService)

    def test_render_video_dynamic_uses_video_title(self):
        item = {
            "id_str": "1",
            "modules": {
                "module_author": {"pub_time": "发布时间：2026-03-31 12:00:00"},
                "module_dynamic": {
                    "major": {
                        "type": "MAJOR_TYPE_ARCHIVE",
                        "archive": {
                            "title": "视频标题",
                            "bvid": "BV1xx411c7mD",
                            "jump_url": "https://www.bilibili.com/video/BV1xx411c7mD",
                            "cover": "https://example.com/cover.jpg",
                        },
                    }
                },
            },
        }

        rendered = self.monitor._render_dynamic_message(item)

        self.assertEqual(rendered["addition_title"], "发布新视频")
        self.assertIn("**视频标题**", rendered["markdown_content"])
        self.assertIn(
            "[原视频链接](https://www.bilibili.com/video/BV1xx411c7mD)",
            rendered["markdown_content"],
        )

    def test_render_opus_dynamic_uses_image_text_title(self):
        item = {
            "id_str": "2",
            "modules": {
                "module_author": {"pub_time": "发布时间：2026-03-31 12:00:00"},
                "module_dynamic": {
                    "major": {
                        "type": "MAJOR_TYPE_OPUS",
                        "opus": {
                            "title": "图文标题",
                            "summary": {"text": "图文摘要"},
                            "pics": [{"url": "https://example.com/p1.jpg"}],
                        },
                    }
                },
            },
        }

        rendered = self.monitor._render_dynamic_message(item)

        self.assertEqual(rendered["addition_title"], "发布图文动态")
        self.assertIn("**图文标题**", rendered["markdown_content"])
        self.assertIn("图文摘要", rendered["markdown_content"])

    def test_render_text_dynamic_uses_text_title(self):
        item = {
            "id_str": "3",
            "modules": {
                "module_author": {"pub_time": "发布时间：2026-03-31 12:00:00"},
                "module_dynamic": {
                    "desc": {"text": "这是一条纯文字动态"},
                    "major": None,
                },
            },
        }

        rendered = self.monitor._render_dynamic_message(item)

        self.assertEqual(rendered["addition_title"], "发布文字动态")
        self.assertIn("这是一条纯文字动态", rendered["markdown_content"])

    def test_render_live_dynamic_uses_live_title(self):
        item = {
            "id_str": "4",
            "modules": {
                "module_author": {"pub_time": "发布时间：2026-03-31 12:00:00"},
                "module_dynamic": {
                    "major": {
                        "type": "MAJOR_TYPE_LIVE_RCMD",
                        "live_rcmd": {
                            "title": "今晚开播",
                            "uname": "测试UP",
                            "link": "https://live.bilibili.com/123",
                            "cover": "https://example.com/live.jpg",
                        },
                    }
                },
            },
        }

        rendered = self.monitor._render_dynamic_message(item)

        self.assertEqual(rendered["addition_title"], "直播动态")
        self.assertIn("今晚开播", rendered["markdown_content"])
        self.assertIn(
            "[进入直播间](https://live.bilibili.com/123)",
            rendered["markdown_content"],
        )

    def test_render_live_dynamic_detects_live_rcmd_without_canonical_type(self):
        item = {
            "id_str": "4b",
            "modules": {
                "module_author": {"pub_time": "发布时间：2026-03-31 12:00:00"},
                "module_dynamic": {
                    "major": {
                        "type": "MAJOR_TYPE_COMMON",
                        "live_rcmd": {
                            "title": "补档直播",
                            "link": "https://live.bilibili.com/456",
                            "uname": "测试UP",
                        },
                    }
                },
            },
        }

        rendered = self.monitor._render_dynamic_message(item)

        self.assertEqual(rendered["addition_title"], "直播动态")
        self.assertIn("补档直播", rendered["markdown_content"])
        self.assertIn(
            "[进入直播间](https://live.bilibili.com/456)",
            rendered["markdown_content"],
        )

    def test_render_repost_with_empty_forward_text_preserves_original_block(self):
        item = {
            "id_str": "5",
            "modules": {
                "module_author": {"pub_time": "发布时间：2026-03-31 12:00:00"},
                "module_dynamic": {
                    "desc": {"text": ""},
                    "major": None,
                },
            },
            "orig": {
                "id_str": "500",
                "modules": {
                    "module_author": {"name": "原作者"},
                    "module_dynamic": {
                        "desc": {"text": "原动态内容"},
                        "major": None,
                    },
                },
            },
        }

        rendered = self.monitor._render_dynamic_message(item)

        self.assertEqual(rendered["addition_title"], "发布文字动态")
        self.assertIn("**转发内容：**", rendered["markdown_content"])
        self.assertIn("**@原作者**", rendered["markdown_content"])
        self.assertIn("原动态内容", rendered["markdown_content"])
        self.assertNotIn("(无文本内容)", rendered["markdown_content"])
        self.assertIn(
            "[查看原动态](https://t.bilibili.com/500)",
            rendered["markdown_content"],
        )

    def test_render_fallback_dynamic_keeps_link_and_title(self):
        item = {
            "id_str": "6",
            "modules": {
                "module_author": {"pub_time": "发布时间：2026-03-31 12:00:00"},
                "module_dynamic": {
                    "major": {
                        "type": "MAJOR_TYPE_COMMON",
                        "common": {
                            "title": "预约活动",
                            "jump_url": "https://example.com/detail",
                            "cover": "https://example.com/cover.jpg",
                        },
                    }
                },
            },
        }

        rendered = self.monitor._render_dynamic_message(item)

        self.assertEqual(rendered["addition_title"], "发布新动态")
        self.assertIn("预约活动", rendered["markdown_content"])
        self.assertIn("https://example.com/detail", rendered["markdown_content"])
        self.assertIn(
            "[查看原动态](https://t.bilibili.com/6)", rendered["markdown_content"]
        )


class _FakeFeishuBot:
    LEVEL_INFO = "INFO"
    LEVEL_WARNING = "WARNING"

    def __init__(self):
        self.notifications = []
        self.cards = []
        self.uploaded_paths = []

    async def upload_local_image(self, path):
        self.uploaded_paths.append(path)
        return "img_key"

    async def send_system_notification(self, level, title, content):
        self.notifications.append((level, title, content))

    async def send_card_message(
        self,
        influencer,
        platform,
        markdown_content,
        channel=None,
        addition_title="",
        addition_subtitle="",
    ):
        self.cards.append(
            {
                "influencer": influencer,
                "platform": platform,
                "markdown_content": markdown_content,
                "channel": channel,
                "addition_title": addition_title,
                "addition_subtitle": addition_subtitle,
            }
        )
        return True


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


class TestMonitorDynamicSendPath(unittest.IsolatedAsyncioTestCase):
    async def test_process_text_dynamic_uses_rendered_addition_title(self):
        monitor = MonitorService.__new__(MonitorService)
        monitor.feishu_bot = _FakeFeishuBot()
        monitor.logger = logging.getLogger("tests.test_monitor.render_send")

        item = {
            "id_str": "3",
            "modules": {
                "module_author": {"pub_time": "发布时间：2026-03-31 12:00:00"},
                "module_dynamic": {
                    "desc": {"text": "这是一条纯文字动态"},
                    "major": None,
                },
            },
        }
        creator = type("CreatorStub", (), {"name": "测试UP", "feishu_channel": None})()

        await monitor._process_text_dynamic(item, creator, "https://t.bilibili.com/3")

        self.assertEqual(len(monitor.feishu_bot.notifications), 0)
        self.assertEqual(len(monitor.feishu_bot.cards), 1)
        self.assertEqual(monitor.feishu_bot.cards[0]["addition_title"], "发布文字动态")

    async def test_process_charge_text_dynamic_preserves_locked_content_marker(self):
        monitor = MonitorService.__new__(MonitorService)
        monitor.feishu_bot = _FakeFeishuBot()
        monitor.logger = logging.getLogger("tests.test_monitor.render_send")

        item = {
            "id_str": "33",
            "modules": {
                "module_author": {"pub_time": "发布时间：2026-03-31 12:00:00"},
                "module_dynamic": {
                    "desc": {"text": ""},
                    "major": None,
                    "additional": {"type": "ONLYFANS"},
                },
            },
        }
        creator = type("CreatorStub", (), {"name": "测试UP", "feishu_channel": None})()

        await monitor._process_text_dynamic(item, creator, "https://t.bilibili.com/33")

        self.assertEqual(len(monitor.feishu_bot.cards), 1)
        self.assertEqual(monitor.feishu_bot.cards[0]["addition_title"], "发布文字动态")
        self.assertIn("**【充电】**", monitor.feishu_bot.cards[0]["markdown_content"])
        self.assertIn(
            "🔒 充电专属内容，请前往 B 站查看",
            monitor.feishu_bot.cards[0]["markdown_content"],
        )

    async def test_process_video_dynamic_keeps_renderer_title_and_enrichment(self):
        monitor = MonitorService.__new__(MonitorService)
        monitor.feishu_bot = _FakeFeishuBot()
        monitor.logger = logging.getLogger("tests.test_monitor.render_send")
        monitor.summarizer = None

        async def fake_fetch_video_comments(bvid, title, creator):
            self.assertEqual(bvid, "BV1xx411c7mD")
            self.assertEqual(title, "视频标题")
            return "---\n\n### 🔥 精选评论"

        monitor._fetch_video_comments = fake_fetch_video_comments

        item = {
            "id_str": "1",
            "modules": {
                "module_author": {"pub_time": "发布时间：2026-03-31 12:00:00"},
                "module_dynamic": {
                    "major": {
                        "type": "MAJOR_TYPE_ARCHIVE",
                        "archive": {
                            "title": "视频标题",
                            "bvid": "BV1xx411c7mD",
                            "jump_url": "https://www.bilibili.com/video/BV1xx411c7mD",
                        },
                    }
                },
            },
        }
        creator = type(
            "CreatorStub",
            (),
            {
                "name": "测试UP",
                "feishu_channel": None,
                "enable_comments": True,
                "comment_rules": [],
            },
        )()

        await monitor._process_video_dynamic(
            item,
            ("BV1xx411c7mD", "视频标题"),
            creator,
            "https://t.bilibili.com/1",
        )

        self.assertEqual(len(monitor.feishu_bot.cards), 1)
        self.assertEqual(monitor.feishu_bot.cards[0]["addition_title"], "发布新视频")
        self.assertIn("**视频标题**", monitor.feishu_bot.cards[0]["markdown_content"])
        self.assertIn(
            "### 🔥 精选评论", monitor.feishu_bot.cards[0]["markdown_content"]
        )

    async def test_process_charge_video_dynamic_preserves_charge_prefix(self):
        monitor = MonitorService.__new__(MonitorService)
        monitor.feishu_bot = _FakeFeishuBot()
        monitor.logger = logging.getLogger("tests.test_monitor.render_send")
        monitor.summarizer = None

        async def fake_fetch_video_comments(bvid, title, creator):
            return None

        monitor._fetch_video_comments = fake_fetch_video_comments

        item = {
            "id_str": "11",
            "modules": {
                "module_author": {"pub_time": "发布时间：2026-03-31 12:00:00"},
                "module_dynamic": {
                    "major": {
                        "type": "MAJOR_TYPE_ARCHIVE",
                        "archive": {
                            "title": "充电视频标题",
                            "bvid": "BV1charge411c7mD",
                            "jump_url": "https://www.bilibili.com/video/BV1charge411c7mD",
                            "badge": {"text": "充电专属"},
                        },
                    }
                },
            },
        }
        creator = type(
            "CreatorStub",
            (),
            {
                "name": "测试UP",
                "feishu_channel": None,
                "enable_comments": False,
                "comment_rules": [],
            },
        )()

        await monitor._process_video_dynamic(
            item,
            ("BV1charge411c7mD", "充电视频标题"),
            creator,
            "https://t.bilibili.com/11",
        )

        self.assertEqual(len(monitor.feishu_bot.cards), 1)
        self.assertEqual(monitor.feishu_bot.cards[0]["addition_title"], "发布新视频")
        self.assertIn("**【充电】**", monitor.feishu_bot.cards[0]["markdown_content"])
        self.assertIn(
            "**充电视频标题**", monitor.feishu_bot.cards[0]["markdown_content"]
        )


if __name__ == "__main__":
    unittest.main()
