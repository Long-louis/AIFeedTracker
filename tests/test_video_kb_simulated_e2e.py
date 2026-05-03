# -*- coding: utf-8 -*-

import logging
import time
import unittest
from unittest.mock import AsyncMock

from services.ai_summary.service import VideoSummaryResult
from services.monitor import MonitorService


class _FakeState:
    def __init__(self, last_seen=None):
        self._last_seen = dict(last_seen or {})
        self.save_calls = 0

    def get_last_seen(self, uid):
        return self._last_seen.get(uid)

    def set_last_seen(self, uid, value):
        self._last_seen[uid] = str(value)

    def save(self):
        self.save_calls += 1


class _FakeFeishuBot:
    def __init__(self):
        self.cards = []
        self.texts = []

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

    async def send_text(self, text, channel=None):
        self.texts.append({"text": text, "channel": channel})
        return True


class _FakeSummarizer:
    def __init__(self):
        self.calls = []

    async def summarize_video(self, video_url):
        self.calls.append(video_url)
        return (
            True,
            "成功总结 1 个视频",
            VideoSummaryResult(
                video_url=video_url,
                summary_source="subtitle",
                summary_markdown="## 关键信息和观点\n- 模拟要点\n\n## 时间线总结\n- 00:00 模拟时间线",
            ),
        )


class _FakeDocsService:
    def __init__(self):
        self.calls = []

    async def upsert_video_summary(self, **kwargs):
        self.calls.append(kwargs)
        return "https://tenant.feishu.cn/wiki/simulated-kb-doc"


class TestVideoKnowledgeBaseSimulatedE2E(unittest.IsolatedAsyncioTestCase):
    async def test_process_creator_runs_simulated_video_kb_flow_without_external_platform(
        self,
    ):
        monitor = MonitorService.__new__(MonitorService)
        monitor.logger = logging.getLogger("tests.test_video_kb_simulated_e2e")
        monitor.feishu_bot = _FakeFeishuBot()
        monitor.summarizer = _FakeSummarizer()
        monitor.feishu_docs_service = _FakeDocsService()
        monitor.state = _FakeState({1001: "100"})
        monitor._allow_backfill_on_start = False

        async def _noop(*args, **kwargs):
            return None

        monitor._check_recent_pinned_comments = _noop
        monitor._poll_creator_comments = _noop
        monitor._fetch_video_comments = _noop

        now_ts = int(time.time())

        new_item = {
            "id_str": "101",
            "modules": {
                "module_author": {
                    "pub_ts": now_ts,
                    "pub_time": "2026-04-09 10:00:00",
                },
                "module_dynamic": {
                    "major": {
                        "type": "MAJOR_TYPE_ARCHIVE",
                        "archive": {
                            "title": "模拟发布视频",
                            "bvid": "BV1simulated101",
                            "jump_url": "https://www.bilibili.com/video/BV1simulated101",
                        },
                    }
                },
            },
        }
        old_item = {
            "id_str": "100",
            "modules": {
                "module_author": {
                    "pub_ts": now_ts - 120,
                    "pub_time": "2026-04-09 09:00:00",
                },
                "module_dynamic": {
                    "major": {
                        "type": "MAJOR_TYPE_ARCHIVE",
                        "archive": {
                            "title": "旧视频",
                            "bvid": "BV1oldvideo100",
                            "jump_url": "https://www.bilibili.com/video/BV1oldvideo100",
                        },
                    }
                },
            },
        }

        monitor.fetch_user_space_dynamics = AsyncMock(
            return_value={
                "code": 0,
                "data": {
                    "items": [new_item, old_item],
                },
            }
        )

        creator = type(
            "CreatorStub",
            (),
            {
                "uid": 1001,
                "name": "模拟UP主",
                "feishu_channel": None,
                "enable_comments": False,
                "comment_rules": [],
            },
        )()

        await monitor.process_creator(creator)

        self.assertEqual(len(monitor.feishu_bot.cards), 1)
        sent_card = monitor.feishu_bot.cards[0]
        self.assertEqual(sent_card["addition_title"], "发布新视频")
        self.assertIn("**AI 总结**", sent_card["markdown_content"])
        self.assertIn("已写入飞书知识库", sent_card["markdown_content"])
        self.assertNotIn("## 关键信息和观点", sent_card["markdown_content"])
        self.assertNotIn("## 时间线总结", sent_card["markdown_content"])
        self.assertEqual(len(monitor.feishu_bot.texts), 1)
        self.assertEqual(
            monitor.feishu_bot.texts[0]["text"],
            "https://tenant.feishu.cn/wiki/simulated-kb-doc",
        )

        self.assertEqual(
            monitor.summarizer.calls, ["https://www.bilibili.com/video/BV1simulated101"]
        )
        self.assertEqual(len(monitor.feishu_docs_service.calls), 1)
        self.assertEqual(
            monitor.feishu_docs_service.calls[0]["bvid"], "BV1simulated101"
        )

        self.assertEqual(monitor.state.get_last_seen(1001), "101")
        self.assertEqual(monitor.state.save_calls, 1)

        # 同样数据再次执行，不应重复推送/写知识库
        await monitor.process_creator(creator)
        self.assertEqual(len(monitor.feishu_bot.cards), 1)
        self.assertEqual(len(monitor.feishu_docs_service.calls), 1)
        self.assertEqual(len(monitor.summarizer.calls), 1)


if __name__ == "__main__":
    unittest.main()
