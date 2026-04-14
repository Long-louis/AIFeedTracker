import logging
import unittest
from unittest.mock import AsyncMock

from services.ai_summary.service import AISummaryService
from services.ai_summary.subtitle_fetcher import SubtitleErrorType


class TestAISummaryASRFallback(unittest.IsolatedAsyncioTestCase):
    def create_service(self):
        service = object.__new__(AISummaryService)
        service.logger = logging.getLogger("tests.ai_summary_asr_fallback")
        service.feishu_bot = None
        service.subtitle_fetcher = AsyncMock()
        service.summary_generator = AsyncMock()
        service.ai_client = AsyncMock()
        service.local_asr_enabled = False
        service.audio_transcription_service = None
        return service

    async def test_subtitle_success_uses_platform_subtitle_without_local_asr(self):
        service = self.create_service()
        service.subtitle_fetcher.fetch_subtitle = AsyncMock(return_value="平台字幕")
        service.summary_generator.generate_summary = AsyncMock(return_value="总结结果")
        service.audio_transcription_service = AsyncMock()
        video_url = "https://www.bilibili.com/video/BV1xx411c7mD"

        (
            success,
            message,
            summary_links,
            summary_contents,
        ) = await service.summarize_videos([video_url])

        self.assertTrue(success)
        self.assertEqual(message, "成功总结 1 个视频")
        self.assertEqual(summary_links, [])
        self.assertEqual(summary_contents, ["总结结果"])
        service.subtitle_fetcher.fetch_subtitle.assert_awaited_once_with(video_url)
        service.summary_generator.generate_summary.assert_awaited_once_with("平台字幕")
        service.audio_transcription_service.transcribe_video.assert_not_called()

    async def test_no_subtitle_uses_local_asr_text_for_summary(self):
        service = self.create_service()
        service.local_asr_enabled = True
        service.subtitle_fetcher.fetch_subtitle = AsyncMock(return_value=None)
        service.subtitle_fetcher.last_error_type = SubtitleErrorType.NO_SUBTITLE
        service.subtitle_fetcher.last_error = "视频无平台字幕"
        service.audio_transcription_service = AsyncMock()
        service.audio_transcription_service.transcribe_video = AsyncMock(
            return_value={
                "text": "本地ASR转写文本",
                "text_source": "local_asr",
                "video_id": "BV1xx411c7mD",
                "duration_seconds": 42.0,
            }
        )
        service.summary_generator.generate_summary = AsyncMock(return_value="总结结果")
        video_url = "https://www.bilibili.com/video/BV1xx411c7mD"

        (
            success,
            message,
            summary_links,
            summary_contents,
        ) = await service.summarize_videos([video_url])

        self.assertTrue(success)
        self.assertEqual(message, "成功总结 1 个视频")
        self.assertEqual(summary_links, [])
        self.assertEqual(summary_contents, ["总结结果"])
        service.audio_transcription_service.transcribe_video.assert_awaited_once_with(
            video_url
        )
        service.summary_generator.generate_summary.assert_awaited_once_with(
            "本地ASR转写文本"
        )

    async def test_cookie_expired_does_not_use_local_asr(self):
        service = self.create_service()
        service.local_asr_enabled = True
        service.subtitle_fetcher.fetch_subtitle = AsyncMock(return_value=None)
        service.subtitle_fetcher.last_error_type = SubtitleErrorType.COOKIE_EXPIRED
        service.subtitle_fetcher.last_error = "SESSDATA 已失效"
        service.audio_transcription_service = AsyncMock()
        video_url = "https://www.bilibili.com/video/BV1xx411c7mD"

        (
            success,
            message,
            summary_links,
            summary_contents,
        ) = await service.summarize_videos([video_url])

        self.assertFalse(success)
        self.assertEqual(message, "所有视频总结都失败")
        self.assertEqual(summary_links, [])
        self.assertEqual(summary_contents, ["❌ Cookie已失效: SESSDATA 已失效"])
        service.audio_transcription_service.transcribe_video.assert_not_called()

    async def test_local_asr_failure_after_no_subtitle_is_visible(self):
        service = self.create_service()
        service.local_asr_enabled = True
        service.subtitle_fetcher.fetch_subtitle = AsyncMock(return_value=None)
        service.subtitle_fetcher.last_error_type = SubtitleErrorType.NO_SUBTITLE
        service.subtitle_fetcher.last_error = "视频无平台字幕"
        service.audio_transcription_service = AsyncMock()
        service.audio_transcription_service.transcribe_video = AsyncMock(
            return_value=None
        )
        service.audio_transcription_service.last_error = "ASR API 请求超时"
        video_url = "https://www.bilibili.com/video/BV1xx411c7mD"

        (
            success,
            message,
            summary_links,
            summary_contents,
        ) = await service.summarize_videos([video_url])

        self.assertFalse(success)
        self.assertEqual(message, "所有视频总结都失败")
        self.assertEqual(summary_links, [])
        self.assertEqual(summary_contents, ["❌ 本地转写失败: ASR API 请求超时"])
        service.audio_transcription_service.transcribe_video.assert_awaited_once_with(
            video_url
        )

    async def test_summarize_video_returns_single_markdown_result(self):
        service = self.create_service()
        service.local_asr_enabled = True
        service.subtitle_fetcher.fetch_subtitle = AsyncMock(return_value=None)
        service.subtitle_fetcher.last_error_type = SubtitleErrorType.NO_SUBTITLE
        service.subtitle_fetcher.last_error = "视频无平台字幕"
        service.audio_transcription_service = AsyncMock()
        service.audio_transcription_service.transcribe_video = AsyncMock(
            return_value={
                "text": "本地ASR转写文本",
                "text_source": "local_asr",
            }
        )
        service.summary_generator.generate_summary = AsyncMock(
            return_value="## 关键信息和观点\n- 要点\n\n## 时间线总结\n- 00:00 开场"
        )
        video_url = "https://www.bilibili.com/video/BV1xx411c7mD"

        ok, message, result = await service.summarize_video(video_url)

        self.assertTrue(ok)
        self.assertEqual(message, "成功总结 1 个视频")
        self.assertIsNotNone(result)
        self.assertEqual(result.summary_source, "local_asr")
        self.assertIn("## 关键信息和观点", result.summary_markdown)
        self.assertFalse(hasattr(result, "key_points_markdown"))


if __name__ == "__main__":
    unittest.main()
