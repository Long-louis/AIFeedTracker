import unittest

from services.ai_summary import (
    ASRErrorType,
    AudioFetchErrorType,
    AudioTranscriptionService,
)
from services.ai_summary.audio_source_fetcher import AudioSourceResult


class FakeFetcher:
    def __init__(
        self,
        result=None,
        last_error=None,
        last_error_type=AudioFetchErrorType.NONE,
        cleanup_temp_files=True,
        cleanup_error=None,
    ):
        self.result = result
        self.last_error = last_error
        self.last_error_type = last_error_type
        self.cleanup_temp_files = cleanup_temp_files
        self.cleanup_error = cleanup_error
        self.fetch_calls = []
        self.cleanup_calls = []

    async def fetch_audio(self, video_url):
        self.fetch_calls.append(video_url)
        return self.result

    def cleanup_workspace(self, workspace):
        self.cleanup_calls.append(workspace)
        if self.cleanup_error is not None:
            raise self.cleanup_error


class FakeTranscriber:
    def __init__(self, result=None, last_error=None, last_error_type=ASRErrorType.NONE):
        self.result = result
        self.last_error = last_error
        self.last_error_type = last_error_type
        self.calls = []

    async def transcribe(self, audio_path):
        self.calls.append(audio_path)
        return self.result


class TestAudioTranscriptionService(unittest.IsolatedAsyncioTestCase):
    async def test_transcribe_video_returns_local_asr_result_and_cleans_workspace(self):
        audio_result = AudioSourceResult(
            video_id="BV1xx411c7mD",
            audio_path="/tmp/audio.wav",
            workspace="/tmp/asr-workspace",
            duration_seconds=123.0,
        )
        fetcher = FakeFetcher(result=audio_result, cleanup_temp_files=True)
        transcriber = FakeTranscriber(result="[00:00] 测试转写")
        service = AudioTranscriptionService(fetcher=fetcher, transcriber=transcriber)

        result = await service.transcribe_video(
            "https://www.bilibili.com/video/BV1xx411c7mD"
        )

        self.assertEqual(
            result,
            {
                "text": "[00:00] 测试转写",
                "text_source": "local_asr",
                "video_id": "BV1xx411c7mD",
                "duration_seconds": 123.0,
            },
        )
        self.assertEqual(
            fetcher.fetch_calls, ["https://www.bilibili.com/video/BV1xx411c7mD"]
        )
        self.assertEqual(transcriber.calls, ["/tmp/audio.wav"])
        self.assertEqual(fetcher.cleanup_calls, ["/tmp/asr-workspace"])
        self.assertIsNone(service.last_error)
        self.assertIsNone(service.last_error_type)

    async def test_transcribe_video_returns_none_on_asr_failure_and_still_cleans_workspace(
        self,
    ):
        audio_result = AudioSourceResult(
            video_id="BV1xx411c7mD",
            audio_path="/tmp/audio.wav",
            workspace="/tmp/asr-workspace",
            duration_seconds=123.0,
        )
        fetcher = FakeFetcher(result=audio_result, cleanup_temp_files=True)
        transcriber = FakeTranscriber(result=None, last_error="whisper failed")
        service = AudioTranscriptionService(fetcher=fetcher, transcriber=transcriber)

        result = await service.transcribe_video(
            "https://www.bilibili.com/video/BV1xx411c7mD"
        )

        self.assertIsNone(result)
        self.assertEqual(service.last_error, "whisper failed")
        self.assertEqual(service.last_error_type, ASRErrorType.NONE)
        self.assertEqual(fetcher.cleanup_calls, ["/tmp/asr-workspace"])

    async def test_transcribe_video_returns_none_on_fetch_failure_without_cleanup(self):
        fetcher = FakeFetcher(
            result=None,
            last_error="audio fetch failed",
            last_error_type=AudioFetchErrorType.AUDIO_DOWNLOAD_FAILED,
            cleanup_temp_files=True,
        )
        transcriber = FakeTranscriber(result="should not run")
        service = AudioTranscriptionService(fetcher=fetcher, transcriber=transcriber)

        result = await service.transcribe_video(
            "https://www.bilibili.com/video/BV1xx411c7mD"
        )

        self.assertIsNone(result)
        self.assertEqual(service.last_error, "audio fetch failed")
        self.assertEqual(
            service.last_error_type, AudioFetchErrorType.AUDIO_DOWNLOAD_FAILED
        )
        self.assertEqual(transcriber.calls, [])
        self.assertEqual(fetcher.cleanup_calls, [])

    async def test_transcribe_video_propagates_transcriber_error_type(self):
        audio_result = AudioSourceResult(
            video_id="BV1xx411c7mD",
            audio_path="/tmp/audio.wav",
            workspace="/tmp/asr-workspace",
            duration_seconds=123.0,
        )
        fetcher = FakeFetcher(result=audio_result, cleanup_temp_files=True)
        transcriber = FakeTranscriber(
            result=None,
            last_error="empty transcript",
            last_error_type=ASRErrorType.ASR_OUTPUT_EMPTY,
        )
        service = AudioTranscriptionService(fetcher=fetcher, transcriber=transcriber)

        result = await service.transcribe_video(
            "https://www.bilibili.com/video/BV1xx411c7mD"
        )

        self.assertIsNone(result)
        self.assertEqual(service.last_error, "empty transcript")
        self.assertEqual(service.last_error_type, ASRErrorType.ASR_OUTPUT_EMPTY)
        self.assertEqual(fetcher.cleanup_calls, ["/tmp/asr-workspace"])

    async def test_transcribe_video_cleanup_failure_does_not_mask_success(self):
        audio_result = AudioSourceResult(
            video_id="BV1xx411c7mD",
            audio_path="/tmp/audio.wav",
            workspace="/tmp/asr-workspace",
            duration_seconds=123.0,
        )
        fetcher = FakeFetcher(
            result=audio_result,
            cleanup_temp_files=True,
            cleanup_error=RuntimeError("cleanup failed"),
        )
        transcriber = FakeTranscriber(result="[00:00] 测试转写")
        service = AudioTranscriptionService(fetcher=fetcher, transcriber=transcriber)

        result = await service.transcribe_video(
            "https://www.bilibili.com/video/BV1xx411c7mD"
        )

        self.assertEqual(
            result,
            {
                "text": "[00:00] 测试转写",
                "text_source": "local_asr",
                "video_id": "BV1xx411c7mD",
                "duration_seconds": 123.0,
            },
        )
        self.assertIsNone(service.last_error)
        self.assertIsNone(service.last_error_type)
        self.assertEqual(fetcher.cleanup_calls, ["/tmp/asr-workspace"])

    def test_package_exports_local_asr_types(self):
        self.assertEqual(AudioFetchErrorType.__name__, "AudioFetchErrorType")
        self.assertEqual(ASRErrorType.__name__, "ASRErrorType")
        self.assertEqual(
            AudioTranscriptionService.__name__, "AudioTranscriptionService"
        )


if __name__ == "__main__":
    unittest.main()
