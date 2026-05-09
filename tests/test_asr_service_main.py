import unittest
import types
import sys
from unittest.mock import patch


def _load_asr_main_module():
    fake_fastapi = types.ModuleType("fastapi")

    class _FakeFastAPI:
        def __init__(self, *args, **kwargs):
            pass

        def on_event(self, *_args, **_kwargs):
            def _decorator(func):
                return func

            return _decorator

        def get(self, *_args, **_kwargs):
            def _decorator(func):
                return func

            return _decorator

        def post(self, *_args, **_kwargs):
            def _decorator(func):
                return func

            return _decorator

    class _FakeUploadFile:
        pass

    class _FakeHTTPException(Exception):
        def __init__(self, status_code=None, detail=None):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    def _fake_file(*_args, **_kwargs):
        return None

    def _fake_query(default=None, **_kwargs):
        return default

    fake_fastapi.FastAPI = _FakeFastAPI
    fake_fastapi.File = _fake_file
    fake_fastapi.HTTPException = _FakeHTTPException
    fake_fastapi.Query = _fake_query
    fake_fastapi.UploadFile = _FakeUploadFile

    fake_concurrency = types.ModuleType("fastapi.concurrency")

    async def _fake_run_in_threadpool(func, *args, **kwargs):
        return func(*args, **kwargs)

    fake_concurrency.run_in_threadpool = _fake_run_in_threadpool

    sys.modules.setdefault("fastapi", fake_fastapi)
    sys.modules.setdefault("fastapi.concurrency", fake_concurrency)

    import importlib

    return importlib.import_module("asr_service.main")


asr_main = _load_asr_main_module()


class ProbeDurationTests(unittest.TestCase):
    @patch("asr_service.main.subprocess.check_output")
    def test_probe_duration_seconds_float_parses_number(self, mock_check_output):
        mock_check_output.return_value = "12.5\n"

        self.assertEqual(asr_main._probe_duration_seconds_float("dummy.wav"), 12.5)

    @patch("asr_service.main.subprocess.check_output")
    def test_probe_duration_seconds_float_na_returns_zero(self, mock_check_output):
        mock_check_output.return_value = "N/A\n"

        self.assertEqual(asr_main._probe_duration_seconds_float("dummy.wav"), 0.0)


class UploadLimitConfigTests(unittest.TestCase):
    def test_default_max_upload_bytes_is_200mib(self):
        self.assertEqual(asr_main.DEFAULT_MAX_UPLOAD_BYTES, 200 * 1024 * 1024)

    def test_default_segment_seconds_is_20(self):
        self.assertEqual(asr_main.DEFAULT_SEGMENT_SECONDS, 20)

    def test_default_segment_temp_dir_uses_home_cache(self):
        self.assertEqual(asr_main.DEFAULT_SEGMENT_TEMP_DIR, "/home/app/.cache/segments")

    def test_default_upload_temp_dir_uses_home_cache(self):
        self.assertEqual(asr_main.DEFAULT_UPLOAD_TEMP_DIR, "/home/app/.cache/uploads")


class VADFallbackTests(unittest.IsolatedAsyncioTestCase):
    def test_should_fallback_for_oom(self):
        self.assertTrue(
            asr_main._should_fallback_to_chunking(RuntimeError("CUDA out of memory"))
        )

    def test_should_not_fallback_for_generic_error(self):
        self.assertFalse(
            asr_main._should_fallback_to_chunking(RuntimeError("unexpected failure"))
        )

    async def test_vad_failure_falls_back_to_manual_chunking(self):
        async def _fake_runtime_transcribe(*_args, **_kwargs):
            raise RuntimeError("CUDA out of memory")

        async def _fake_chunking(*_args, **_kwargs):
            return {"text": "ok", "segments": []}

        with patch.object(asr_main.runtime, "transcribe", side_effect=_fake_runtime_transcribe):
            with patch("asr_service.main._transcribe_with_chunking", side_effect=_fake_chunking):
                result = await asr_main._transcribe_with_vad_fallback(
                    "dummy.wav", language=None, timestamps=None
                )
        self.assertEqual(result["text"], "ok")

    async def test_vad_failure_clears_cuda_cache_before_chunking(self):
        async def _fake_runtime_transcribe(*_args, **_kwargs):
            raise RuntimeError("CUDA out of memory")

        async def _fake_chunking(*_args, **_kwargs):
            return {"text": "ok", "segments": []}

        with patch.object(asr_main.runtime, "transcribe", side_effect=_fake_runtime_transcribe):
            with patch("asr_service.main._transcribe_with_chunking", side_effect=_fake_chunking):
                with patch("asr_service.main._clear_cuda_cache") as mock_clear:
                    result = await asr_main._transcribe_with_vad_fallback(
                        "dummy.wav", language=None, timestamps=None
                    )
        mock_clear.assert_called_once()
        self.assertEqual(result["text"], "ok")


if __name__ == "__main__":
    unittest.main()
