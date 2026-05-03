import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import aiohttp

from services.ai_summary.sensevoice_client import ASRErrorType, SenseVoiceClient


class TestSenseVoiceClient(unittest.IsolatedAsyncioTestCase):
    def test_exposes_backward_compatible_empty_output_enum_name(self):
        self.assertIs(ASRErrorType.ASR_OUTPUT_EMPTY, ASRErrorType.ASR_API_OUTPUT_EMPTY)

    async def test_returns_text_when_api_ok(self):
        client = SenseVoiceClient("http://asr/v1/transcribe", timeout_seconds=30)

        with patch.object(
            client,
            "_post_audio",
            AsyncMock(return_value={"text": "  你好世界  "}),
        ):
            result = await client.transcribe("/tmp/a.wav")

        self.assertEqual(result, "你好世界")
        self.assertEqual(client.last_error_type, ASRErrorType.NONE)
        self.assertIsNone(client.last_error)

    async def test_sets_error_on_timeout(self):
        client = SenseVoiceClient("http://asr/v1/transcribe", timeout_seconds=30)

        with patch.object(
            client, "_post_audio", AsyncMock(side_effect=asyncio.TimeoutError)
        ):
            result = await client.transcribe("/tmp/a.wav")

        self.assertIsNone(result)
        self.assertEqual(client.last_error_type, ASRErrorType.ASR_API_TIMEOUT)
        self.assertIn("超时", client.last_error)

    async def test_sets_error_on_request_failure(self):
        client = SenseVoiceClient("http://asr/v1/transcribe", timeout_seconds=30)

        with patch.object(
            client,
            "_post_audio",
            AsyncMock(side_effect=aiohttp.ClientError("server error")),
        ):
            result = await client.transcribe("/tmp/a.wav")

        self.assertIsNone(result)
        self.assertEqual(client.last_error_type, ASRErrorType.ASR_API_REQUEST_FAILED)
        self.assertIn("调用失败", client.last_error)

    async def test_sets_error_on_empty_text(self):
        client = SenseVoiceClient("http://asr/v1/transcribe", timeout_seconds=30)

        with patch.object(client, "_post_audio", AsyncMock(return_value={"text": ""})):
            result = await client.transcribe("/tmp/a.wav")

        self.assertIsNone(result)
        self.assertEqual(client.last_error_type, ASRErrorType.ASR_API_OUTPUT_EMPTY)
        self.assertIn("输出为空", client.last_error)

    async def test_sets_error_on_local_audio_open_failure(self):
        client = SenseVoiceClient("http://asr/v1/transcribe", timeout_seconds=30)

        with patch(
            "services.ai_summary.sensevoice_client.Path.open",
            side_effect=OSError("permission denied"),
        ):
            result = await client.transcribe("/tmp/a.wav")

        self.assertIsNone(result)
        self.assertEqual(client.last_error_type, ASRErrorType.ASR_API_REQUEST_FAILED)
        self.assertIn("本地音频文件读取失败", client.last_error)


if __name__ == "__main__":
    unittest.main()
