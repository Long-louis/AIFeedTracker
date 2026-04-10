# -*- coding: utf-8 -*-

import unittest

from services.ai_summary.summary_generator import SummaryGenerator


class TestSummaryPromptSections(unittest.TestCase):
    def test_user_prompt_only_keeps_required_sections(self):
        prompt = SummaryGenerator.USER_PROMPT_TEMPLATE
        self.assertIn("写作目标", prompt)
        self.assertIn("## 关键信息和观点", prompt)
        self.assertIn("## 时间线总结", prompt)
        self.assertNotIn("## 一句话总结", prompt)
        self.assertNotIn("## 涉及的标的", prompt)
        self.assertNotIn("## 风险与不确定性", prompt)
        self.assertNotIn("## 可执行的关注清单", prompt)


class TestVideoSummaryResultShape(unittest.TestCase):
    def test_video_summary_result_uses_single_markdown_field(self):
        from services.ai_summary.service import VideoSummaryResult

        result = VideoSummaryResult(
            video_url="https://www.bilibili.com/video/BV1xx411c7mD",
            summary_source="subtitle",
            summary_markdown="## 关键信息和观点\n- 要点\n\n## 时间线总结\n- 00:00 ...",
        )

        self.assertEqual(result.summary_source, "subtitle")
        self.assertTrue(result.summary_markdown.startswith("## 关键信息和观点"))
        self.assertFalse(hasattr(result, "key_points_markdown"))
        self.assertFalse(hasattr(result, "timeline_markdown"))


if __name__ == "__main__":
    unittest.main()
