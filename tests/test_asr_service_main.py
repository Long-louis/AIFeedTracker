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


if __name__ == "__main__":
    unittest.main()
