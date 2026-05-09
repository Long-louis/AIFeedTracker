import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

import aiohttp


def _load_sensevoice_client_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "ai_summary"
        / "sensevoice_client.py"
    )
    spec = importlib.util.spec_from_file_location(
        "test_sensevoice_client_module", module_path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


_sensevoice_client = _load_sensevoice_client_module()
ASRErrorType = _sensevoice_client.ASRErrorType
SenseVoiceClient = _sensevoice_client.SenseVoiceClient


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

    async def test_retries_transient_asr_api_failures_until_success(self):
        client = SenseVoiceClient("http://asr/v1/transcribe", timeout_seconds=30)

        responses = [
            aiohttp.ClientResponseError(
                request_info=SimpleNamespace(real_url="http://asr/v1/transcribe"),
                history=(),
                status=503,
                message="Service Unavailable",
                headers=None,
            ),
            {"text": "重试成功"},
        ]

        async def _fake_post_audio(_audio_path):
            value = responses.pop(0)
            if isinstance(value, Exception):
                raise value
            return value

        with patch.object(client, "_post_audio", AsyncMock(side_effect=_fake_post_audio)):
            with patch.object(_sensevoice_client.asyncio, "sleep", AsyncMock()):
                result = await client.transcribe("/tmp/a.wav")

        self.assertEqual(result, "重试成功")
        self.assertEqual(client.last_error_type, ASRErrorType.NONE)
        self.assertIsNone(client.last_error)

    async def test_sets_error_on_empty_text(self):
        client = SenseVoiceClient("http://asr/v1/transcribe", timeout_seconds=30)

        with patch.object(client, "_post_audio", AsyncMock(return_value={"text": ""})):
            result = await client.transcribe("/tmp/a.wav")

        self.assertIsNone(result)
        self.assertEqual(client.last_error_type, ASRErrorType.ASR_API_OUTPUT_EMPTY)
        self.assertIn("输出为空", client.last_error)

    async def test_sets_error_on_local_audio_open_failure(self):
        client = SenseVoiceClient("http://asr/v1/transcribe", timeout_seconds=30)

        with patch.object(_sensevoice_client.Path, "open", side_effect=OSError("permission denied")):
            result = await client.transcribe("/tmp/a.wav")

        self.assertIsNone(result)
        self.assertEqual(client.last_error_type, ASRErrorType.ASR_API_REQUEST_FAILED)
        self.assertIn("本地音频文件读取失败", client.last_error)


if __name__ == "__main__":
    unittest.main()
