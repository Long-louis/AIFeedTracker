# -*- coding: utf-8 -*-
"""聚合流 + 限流器 + 分层延迟的单元测试（档位 A + C）。"""

import asyncio
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

from services.bilibili_rate_limiter import (
    BilibiliRateLimiter,
    CircuitOpenError,
)
from services.monitor import (
    Creator,
    MonitorService,
    _match_session_window,
    _parse_dow_token,
)


def _make_item(did, mid, name="UP", ctype="DYNAMIC_TYPE_WORD"):
    return {
        "id_str": str(did),
        "id": did,
        "type": ctype,
        "modules": {"module_author": {"mid": mid, "name": name}},
    }


class TestSessionWindow(unittest.TestCase):
    def test_parse_dow_range(self):
        self.assertEqual(_parse_dow_token("mon-fri"), [0, 1, 2, 3, 4])
        self.assertEqual(_parse_dow_token("sat,sun"), [5, 6])

    def test_match_inside_window(self):
        tz = ZoneInfo("Asia/Shanghai")
        # 周二 10:00 在 mon-fri 09:15-15:00 内
        self.assertTrue(
            _match_session_window(
                "mon-fri 09:15-15:00", datetime(2026, 6, 23, 10, 0, tzinfo=tz)
            )
        )

    def test_no_match_outside_window(self):
        tz = ZoneInfo("Asia/Shanghai")
        # 周二 16:00 不在窗口内
        self.assertFalse(
            _match_session_window(
                "mon-fri 09:15-15:00", datetime(2026, 6, 23, 16, 0, tzinfo=tz)
            )
        )

    def test_no_match_weekend(self):
        tz = ZoneInfo("Asia/Shanghai")
        # 周日 10:00
        self.assertFalse(
            _match_session_window(
                "mon-fri 09:15-15:00", datetime(2026, 6, 28, 10, 0, tzinfo=tz)
            )
        )


class TestExtractAuthorMid(unittest.TestCase):
    def test_extract_mid(self):
        item = _make_item(1, 12345)
        self.assertEqual(MonitorService._extract_author_mid(item), 12345)

    def test_extract_mid_missing(self):
        self.assertIsNone(MonitorService._extract_author_mid({"modules": {}}))
        self.assertIsNone(MonitorService._extract_author_mid({}))


class TestComputePollInterval(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.svc = MonitorService.__new__(MonitorService)
        self.svc.feed_config = {
            "market_session_enabled": True,
            "market_session_windows": "mon-fri 09:15-15:00",
            "poll_fast_seconds": 90,
            "poll_normal_seconds": 600,
            "poll_quiet_seconds": 3600,
            "poll_jitter_ratio": 0.25,
            "quiet_hours_start": 0,
            "quiet_hours_end": 6,
        }
        self.svc.logger = __import__("logging").getLogger("test")

    def test_fast_when_in_session_regardless_of_tier(self):
        tz = ZoneInfo("Asia/Shanghai")
        with patch.object(self.svc, "_tz", lambda: tz):
            # 盘口内：无论是否 realtime 都走快周期
            for tier in ("normal", "realtime"):
                creators = [Creator(uid=1, name="a", latency_tier=tier)]
                with patch("services.monitor.datetime", wraps=datetime) as mock_dt:
                    mock_dt.now.return_value = datetime(
                        2026, 6, 23, 10, 0, tzinfo=tz
                    )
                    interval = self.svc.compute_poll_interval(creators)
                self.assertEqual(interval, 90, f"tier={tier} 应为快周期")

    def test_normal_outside_session(self):
        tz = ZoneInfo("Asia/Shanghai")
        creators = [Creator(uid=1, name="a", latency_tier="realtime")]
        with patch.object(self.svc, "_tz", lambda: tz):
            with patch("services.monitor.datetime", wraps=datetime) as mock_dt:
                # 周二 16:00，盘外 -> normal
                mock_dt.now.return_value = datetime(2026, 6, 23, 16, 0, tzinfo=tz)
                interval = self.svc.compute_poll_interval(creators)
        self.assertEqual(interval, 600)

    def test_quiet_hours(self):
        tz = ZoneInfo("Asia/Shanghai")
        creators = [Creator(uid=1, name="a", latency_tier="realtime")]
        with patch.object(self.svc, "_tz", lambda: tz):
            with patch("services.monitor.datetime", wraps=datetime) as mock_dt:
                # 周二 03:00（静默时段）-> quiet
                mock_dt.now.return_value = datetime(2026, 6, 23, 3, 0, tzinfo=tz)
                interval = self.svc.compute_poll_interval(creators)
        self.assertEqual(interval, 3600)

    def test_jittered_interval_within_bounds(self):
        base = 100
        for _ in range(50):
            v = self.svc._jittered_interval(base)
            self.assertGreaterEqual(v, 75.0)
            self.assertLessEqual(v, 125.0)


class TestAggregatedDispatch(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.svc = MonitorService.__new__(MonitorService)
        self.svc.logger = __import__("logging").getLogger("test")
        self.svc.rate_limiter = BilibiliRateLimiter(qps=100, concurrency=10)
        self.svc.feishu_bot = None
        self.svc.summarizer = None
        self.svc.credential = None
        self.svc.feed_config = {"mode": "aggregated"}
        self.svc._allow_backfill_on_start = False
        import tempfile, os
        from services.monitor import JsonState

        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        self._state_path = path
        self.svc.state = JsonState(path)

    def tearDown(self):
        import os
        if os.path.exists(self._state_path):
            os.remove(self._state_path)

    def _prime(self, uid, did):
        self.svc.state.set_last_seen(uid, str(did))
        self.svc.state.save()

    async def test_dispatch_new_dynamic_calls_process(self):
        creator = Creator(uid=100, name="测试UP")
        items = [
            _make_item(300, 100, "测试UP"),
            _make_item(200, 100, "测试UP"),
        ]
        # last_seen=200 -> 只有 300 是新的
        self._prime(100, 200)
        self.svc._process_dynamic_item = AsyncMock()
        await self.svc._dispatch_creator_items(creator, items)
        self.svc._process_dynamic_item.assert_awaited_once()
        dispatched_item = self.svc._process_dynamic_item.await_args.args[0]
        self.assertEqual(dispatched_item["id_str"], "300")
        # last_seen 更新为最新
        self.assertEqual(self.svc.state.get_last_seen(100), "300")

    async def test_dispatch_no_new_skips(self):
        creator = Creator(uid=100, name="测试UP")
        items = [_make_item(200, 100, "测试UP"), _make_item(100, 100, "测试UP")]
        self._prime(100, 200)
        self.svc._process_dynamic_item = AsyncMock()
        await self.svc._dispatch_creator_items(creator, items)
        self.svc._process_dynamic_item.assert_not_awaited()

    async def test_dispatch_first_run_aligns_without_backfill(self):
        creator = Creator(uid=100, name="测试UP")
        items = [_make_item(500, 100, "测试UP"), _make_item(400, 100, "测试UP")]
        # 无 last_seen，不补发 -> 对齐到最新且不派发
        self.svc._process_dynamic_item = AsyncMock()
        await self.svc._dispatch_creator_items(creator, items)
        self.svc._process_dynamic_item.assert_not_awaited()
        self.assertEqual(self.svc.state.get_last_seen(100), "500")

    async def test_process_aggregated_feed_filters_and_dispatches(self):
        creators = [Creator(uid=100, name="A"), Creator(uid=200, name="B")]
        feed_items = [
            _make_item(11, 100, "A"),  # 关注
            _make_item(12, 999, "陌生人"),  # 非关注，应过滤
            _make_item(13, 200, "B"),  # 关注
        ]
        self.svc.fetch_aggregated_feed = AsyncMock(
            return_value={"code": 0, "data": {"items": feed_items}}
        )
        self._prime(100, 10)  # A 有新动态
        self._prime(200, 13)  # B 无新动态
        self.svc._dispatch_creator_items = AsyncMock()
        await self.svc.process_aggregated_feed(creators)
        # 只为 A 派发（B 无新动态由 _dispatch_creator_items 内部判断）
        self.assertEqual(self.svc._dispatch_creator_items.await_count, 2)

    def test_creators_satisfied_empty(self):
        self.assertTrue(self.svc._aggregated_creators_satisfied({}))

    def test_creators_satisfied_when_lastseen_present(self):
        # 分组里含 last_seen id -> 满足
        self._prime(100, 200)
        grouped = {100: [_make_item(300, 100, "A"), _make_item(200, 100, "A")]}
        self.assertTrue(self.svc._aggregated_creators_satisfied(grouped))

    def test_creators_satisfied_when_lastseen_missing(self):
        # 分组里没有 last_seen -> 未满足，需翻页
        self._prime(100, 10)
        grouped = {100: [_make_item(300, 100, "A"), _make_item(200, 100, "A")]}
        self.assertFalse(self.svc._aggregated_creators_satisfied(grouped))

    def test_creators_satisfied_first_run_no_lastseen(self):
        # 首次对齐（无 last_seen）的博主不参与判断
        grouped = {100: [_make_item(300, 100, "A")]}
        self.assertTrue(self.svc._aggregated_creators_satisfied(grouped))

    async def test_pagination_continues_until_satisfied(self):
        creators = [Creator(uid=100, name="A")]
        self._prime(100, 1)  # last_seen 很旧，需翻页直到遇到 id=1
        page1 = [_make_item(30, 100, "A"), _make_item(20, 100, "A")]
        page2 = [_make_item(10, 100, "A"), _make_item(1, 100, "A")]
        self.svc.fetch_aggregated_feed = AsyncMock(
            side_effect=[
                {"code": 0, "data": {"items": page1}, "has_more": True, "offset": "x"},
                {"code": 0, "data": {"items": page2}, "has_more": False, "offset": None},
            ]
        )
        self.svc._dispatch_creator_items = AsyncMock()
        await self.svc.process_aggregated_feed(creators)
        self.assertEqual(self.svc.fetch_aggregated_feed.await_count, 2)

    async def test_dispatch_does_not_poll_comments(self):
        # 评论轮询已从 _dispatch_creator_items 解耦
        creator = Creator(uid=100, name="UP", enable_comments=True)
        items = [_make_item(300, 100, "UP"), _make_item(200, 100, "UP")]
        self._prime(100, 200)
        self.svc._process_dynamic_item = AsyncMock()
        self.svc._poll_creator_comments = AsyncMock()
        self.svc._check_recent_pinned_comments = AsyncMock()
        self.svc.comment_fetcher = object()
        await self.svc._dispatch_creator_items(creator, items)
        self.svc._poll_creator_comments.assert_not_awaited()
        self.svc._check_recent_pinned_comments.assert_not_awaited()

    async def test_dispatch_no_republish_when_lastseen_buried(self):
        # 回归：last_seen 被挤出分页窗口（不在 items 里）时，
        # 旧"精确匹配 break" 会把已推过的旧动态当新动态重发；
        # 数值 id 比较只派发真正更新的。
        creator = Creator(uid=100, name="UP")
        # last_seen=750 不在 items 中，且 700/600 都比它旧（已推过）
        self._prime(100, 750)
        items = [_make_item(800, 100, "UP"), _make_item(700, 100, "UP"),
                 _make_item(600, 100, "UP")]
        self.svc._process_dynamic_item = AsyncMock()
        await self.svc._dispatch_creator_items(creator, items)
        # 只有 800 比 last_seen(750) 新，应只派发 1 条
        self.assertEqual(self.svc._process_dynamic_item.await_count, 1)

    async def test_dispatch_republishes_all_when_truly_new(self):
        # last_seen 很旧，items 全部更新 -> 全部派发（正确行为）
        creator = Creator(uid=100, name="UP")
        self._prime(100, 500)
        items = [_make_item(800, 100, "UP"), _make_item(700, 100, "UP")]
        self.svc._process_dynamic_item = AsyncMock()
        await self.svc._dispatch_creator_items(creator, items)
        self.assertEqual(self.svc._process_dynamic_item.await_count, 2)




class TestRateLimiter(unittest.IsolatedAsyncioTestCase):
    async def test_throttle_enforces_min_interval(self):
        limiter = BilibiliRateLimiter(qps=5, concurrency=2)  # min_interval=0.2s
        import time
        start = time.monotonic()
        for _ in range(3):
            async with limiter.guard("t"):
                pass
        elapsed = time.monotonic() - start
        # 3 次至少间隔 2*0.2=0.4s（首次不需等）
        self.assertGreaterEqual(elapsed, 0.35)

    async def test_circuit_opens_after_streak(self):
        limiter = BilibiliRateLimiter(
            qps=100, concurrency=2, circuit_trips=2, circuit_cooldown=10
        )
        limiter.record_risk("cat")
        limiter.record_risk("cat")  # 连续 2 次 -> 熔断
        with self.assertRaises(CircuitOpenError):
            async with limiter.guard("cat"):
                pass

    async def test_success_resets_streak(self):
        limiter = BilibiliRateLimiter(
            qps=100, concurrency=2, circuit_trips=2, circuit_cooldown=10
        )
        limiter.record_risk("cat")
        limiter.record_success("cat")
        limiter.record_risk("cat")  # streak 重置过，未达阈值
        async with limiter.guard("cat"):
            pass

    def test_classify_response_code_exception(self):
        from bilibili_api.utils.network import ResponseCodeException

        limiter = BilibiliRateLimiter(risk_codes={-352})
        exc = ResponseCodeException(-352, "risk")
        self.assertTrue(limiter.classify(exc))
        safe = ResponseCodeException(-509, "other")
        self.assertFalse(limiter.classify(safe))


class TestDeferredSummary(unittest.IsolatedAsyncioTestCase):
    async def test_deferred_enqueues_and_drain_processes(self):
        svc = MonitorService.__new__(MonitorService)
        svc.logger = __import__("logging").getLogger("test")
        svc._summary_queue = []
        creator = Creator(uid=1, name="复盘", summarize_mode="deferred")
        item = _make_item(9, 1, "复盘", "DYNAMIC_TYPE_AV")
        # _process_video_dynamic：deferred 应入队且不立即总结
        svc._render_video_dynamic_message = lambda it: {
            "markdown_content": "md",
            "addition_title": "",
            "addition_subtitle": "",
        }
        svc._fetch_video_comments = AsyncMock(return_value=None)
        svc.feishu_bot = None
        svc.summarizer = object()  # truthy
        svc.VIDEO_PC_URL = "https://www.bilibili.com/video/{bvid}"
        svc.feishu_docs_service = None
        with patch.object(
            MonitorService, "extract_video_info", return_value=("BV1xxx", "标题")
        ):
            with patch.object(MonitorService, "DYNAMIC_PC_URL", "https://t.bilibili.com/{dynamic_id}"):
                await svc._process_video_dynamic(item, ("BV1xxx", "标题"), creator, "https://t.bilibili.com/9")
        self.assertEqual(len(svc._summary_queue), 1)
        # drain 时调用立即总结（绕过 deferred）
        svc._process_video_dynamic = AsyncMock()
        await svc._drain_summary_queue()
        svc._process_video_dynamic.assert_awaited_once()
        self.assertEqual(svc._summary_queue, [])


if __name__ == "__main__":
    unittest.main()
