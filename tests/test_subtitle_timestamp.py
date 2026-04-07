# -*- coding: utf-8 -*-

import unittest

from services.ai_summary.subtitle_fetcher import SubtitleFetcher


class TestSubtitleTimestamp(unittest.TestCase):
    def test_format_timestamp_mmss(self):
        self.assertEqual(SubtitleFetcher.format_timestamp(0), "00:00")
        self.assertEqual(SubtitleFetcher.format_timestamp(59), "00:59")
        self.assertEqual(SubtitleFetcher.format_timestamp(60), "01:00")
        self.assertEqual(SubtitleFetcher.format_timestamp(61), "01:01")
        self.assertEqual(SubtitleFetcher.format_timestamp(3599), "59:59")

    def test_format_timestamp_hhmmss(self):
        self.assertEqual(SubtitleFetcher.format_timestamp(3600), "01:00:00")
        self.assertEqual(SubtitleFetcher.format_timestamp(3661), "01:01:01")

    def test_subtitle_body_to_text_with_timestamp(self):
        body = [
            {"from": 0.0, "to": 1.0, "content": "开场"},
            {"from": 59.03, "to": 61.0, "content": "消费板块异动"},
            {"from": 122.17, "to": 123.0, "content": "锂午后爆发"},
        ]
        text = SubtitleFetcher.subtitle_body_to_text(body)
        self.assertIn("[00:00] 开场", text)
        self.assertIn("[00:59] 消费板块异动", text)
        self.assertIn("[02:02] 锂午后爆发", text)

    def test_subtitle_body_to_text_ignores_empty(self):
        body = [
            {"from": 1.0, "to": 2.0, "content": "  "},
            {"from": 2.0, "to": 3.0, "content": "有效"},
            "not-a-dict",
            {"from": "bad", "content": "无时间戳也应保留"},
        ]
        text = SubtitleFetcher.subtitle_body_to_text(body)
        self.assertNotIn("[]", text)
        self.assertIn("[00:02] 有效", text)
        self.assertIn("无时间戳也应保留", text)


if __name__ == "__main__":
    unittest.main()
