# -*- coding: utf-8 -*-

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


if __name__ == "__main__":
    unittest.main()
