import importlib
import os
import sys
import unittest
from unittest import mock

from services.ai_summary.audio_transcription_service import AudioTranscriptionService


LOCAL_ASR_ENV_KEYS = [
    "LOCAL_ASR_ENABLED",
    "LOCAL_ASR_PROVIDER",
    "ASR_API_URL",
    "ASR_API_TIMEOUT_SECONDS",
    "LOCAL_ASR_TEMP_DIR",
    "LOCAL_ASR_MAX_AUDIO_MINUTES",
    "LOCAL_ASR_CLEANUP_TEMP_FILES",
]


def _reload_config_module():
    with mock.patch("dotenv.load_dotenv", return_value=False):
        sys.modules.pop("config", None)
        import config

        return importlib.reload(config)


class TestLocalAsrConfig(unittest.TestCase):
    def setUp(self):
        self._env_patch = mock.patch.dict(os.environ, {}, clear=False)
        self._env_patch.start()
        for key in LOCAL_ASR_ENV_KEYS:
            os.environ.pop(key, None)

    def tearDown(self):
        self._env_patch.stop()

    def test_loads_default_local_asr_config(self):
        config = _reload_config_module()

        self.assertEqual(
            config.LOCAL_ASR_CONFIG,
            {
                "enabled": False,
                "provider": "sensevoice_api",
                "api_url": "http://127.0.0.1:8900/v1/transcribe",
                "api_timeout_seconds": 300,
                "temp_dir": "./data/temp_asr",
                "max_audio_minutes": 90,
                "cleanup_temp_files": True,
            },
        )

    def test_reads_local_asr_env_overrides(self):
        os.environ.update(
            {
                "LOCAL_ASR_ENABLED": "false",
                "LOCAL_ASR_PROVIDER": "custom_asr",
                "ASR_API_URL": "http://asr.internal/v1/transcribe",
                "ASR_API_TIMEOUT_SECONDS": "45",
                "LOCAL_ASR_TEMP_DIR": "/tmp/asr",
                "LOCAL_ASR_MAX_AUDIO_MINUTES": "45",
                "LOCAL_ASR_CLEANUP_TEMP_FILES": "False",
            }
        )

        config = _reload_config_module()

        self.assertEqual(
            config.LOCAL_ASR_CONFIG,
            {
                "enabled": False,
                "provider": "custom_asr",
                "api_url": "http://asr.internal/v1/transcribe",
                "api_timeout_seconds": 45,
                "temp_dir": "/tmp/asr",
                "max_audio_minutes": 45,
                "cleanup_temp_files": False,
            },
        )

    def test_empty_string_string_envs_fall_back_to_defaults(self):
        os.environ.update(
            {
                "LOCAL_ASR_PROVIDER": "",
                "ASR_API_URL": "",
                "LOCAL_ASR_TEMP_DIR": "",
            }
        )

        config = _reload_config_module()

        self.assertEqual(config.LOCAL_ASR_CONFIG["provider"], "sensevoice_api")
        self.assertEqual(
            config.LOCAL_ASR_CONFIG["api_url"],
            "http://127.0.0.1:8900/v1/transcribe",
        )
        self.assertEqual(config.LOCAL_ASR_CONFIG["temp_dir"], "./data/temp_asr")

    def test_empty_string_bool_and_int_envs_fall_back_to_defaults(self):
        os.environ.update(
            {
                "LOCAL_ASR_ENABLED": "",
                "ASR_API_TIMEOUT_SECONDS": "",
                "LOCAL_ASR_MAX_AUDIO_MINUTES": "",
            }
        )

        config = _reload_config_module()

        self.assertIs(config.LOCAL_ASR_CONFIG["enabled"], False)
        self.assertEqual(config.LOCAL_ASR_CONFIG["api_timeout_seconds"], 300)
        self.assertEqual(config.LOCAL_ASR_CONFIG["max_audio_minutes"], 90)

    def test_invalid_non_empty_boolean_env_raises_value_error(self):
        os.environ["LOCAL_ASR_ENABLED"] = "treu"

        with self.assertRaisesRegex(ValueError, "LOCAL_ASR_ENABLED"):
            _reload_config_module()

    def test_audio_transcription_service_rejects_unsupported_provider(self):
        config = {
            "provider": "unsupported_provider",
            "api_url": "http://127.0.0.1:8900/v1/transcribe",
            "api_timeout_seconds": 300,
            "temp_dir": "./data/temp_asr",
            "max_audio_minutes": 90,
            "cleanup_temp_files": True,
        }

        with mock.patch(
            "services.ai_summary.audio_transcription_service.LOCAL_ASR_CONFIG",
            config,
        ):
            with self.assertRaisesRegex(ValueError, "LOCAL_ASR_PROVIDER"):
                AudioTranscriptionService(fetcher=mock.Mock())

    def test_audio_transcription_service_uses_sensevoice_client(self):
        config = {
            "provider": "sensevoice_api",
            "api_url": "http://127.0.0.1:8900/v1/transcribe",
            "api_timeout_seconds": 123,
            "temp_dir": "./data/temp_asr",
            "max_audio_minutes": 90,
            "cleanup_temp_files": True,
        }

        with mock.patch(
            "services.ai_summary.audio_transcription_service.LOCAL_ASR_CONFIG",
            config,
        ):
            with mock.patch(
                "services.ai_summary.audio_transcription_service.SenseVoiceClient"
            ) as sensevoice_client:
                service = AudioTranscriptionService(fetcher=mock.Mock())

        sensevoice_client.assert_called_once_with(
            api_url="http://127.0.0.1:8900/v1/transcribe",
            timeout_seconds=123,
        )
        self.assertIs(service.transcriber, sensevoice_client.return_value)
