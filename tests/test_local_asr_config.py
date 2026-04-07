import importlib
import os
import sys
import unittest
from unittest import mock

from services.ai_summary.audio_transcription_service import AudioTranscriptionService


LOCAL_ASR_ENV_KEYS = [
    "LOCAL_ASR_ENABLED",
    "LOCAL_ASR_PROVIDER",
    "LOCAL_ASR_MODEL",
    "LOCAL_ASR_DEVICE",
    "LOCAL_ASR_COMPUTE_TYPE",
    "LOCAL_ASR_LANGUAGE",
    "LOCAL_ASR_BEAM_SIZE",
    "LOCAL_ASR_VAD_FILTER",
    "LOCAL_ASR_OUTPUT_TIMESTAMPS",
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
                "enabled": True,
                "provider": "faster_whisper",
                "model": "large-v3",
                "device": "cuda",
                "compute_type": "float16",
                "language": "zh",
                "beam_size": 5,
                "vad_filter": True,
                "output_timestamps": True,
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
                "LOCAL_ASR_MODEL": "small",
                "LOCAL_ASR_DEVICE": "cpu",
                "LOCAL_ASR_COMPUTE_TYPE": "int8",
                "LOCAL_ASR_LANGUAGE": "en",
                "LOCAL_ASR_BEAM_SIZE": "2",
                "LOCAL_ASR_VAD_FILTER": "0",
                "LOCAL_ASR_OUTPUT_TIMESTAMPS": "no",
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
                "model": "small",
                "device": "cpu",
                "compute_type": "int8",
                "language": "en",
                "beam_size": 2,
                "vad_filter": False,
                "output_timestamps": False,
                "temp_dir": "/tmp/asr",
                "max_audio_minutes": 45,
                "cleanup_temp_files": False,
            },
        )

    def test_empty_string_string_envs_fall_back_to_defaults(self):
        os.environ.update(
            {
                "LOCAL_ASR_PROVIDER": "",
                "LOCAL_ASR_MODEL": "",
                "LOCAL_ASR_TEMP_DIR": "",
            }
        )

        config = _reload_config_module()

        self.assertEqual(config.LOCAL_ASR_CONFIG["provider"], "faster_whisper")
        self.assertEqual(config.LOCAL_ASR_CONFIG["model"], "large-v3")
        self.assertEqual(config.LOCAL_ASR_CONFIG["temp_dir"], "./data/temp_asr")

    def test_empty_string_bool_and_int_envs_fall_back_to_defaults(self):
        os.environ.update(
            {
                "LOCAL_ASR_ENABLED": "",
                "LOCAL_ASR_BEAM_SIZE": "",
                "LOCAL_ASR_VAD_FILTER": "",
                "LOCAL_ASR_MAX_AUDIO_MINUTES": "",
            }
        )

        config = _reload_config_module()

        self.assertIs(config.LOCAL_ASR_CONFIG["enabled"], True)
        self.assertEqual(config.LOCAL_ASR_CONFIG["beam_size"], 5)
        self.assertIs(config.LOCAL_ASR_CONFIG["vad_filter"], True)
        self.assertEqual(config.LOCAL_ASR_CONFIG["max_audio_minutes"], 90)

    def test_invalid_non_empty_boolean_env_raises_value_error(self):
        os.environ["LOCAL_ASR_ENABLED"] = "treu"

        with self.assertRaisesRegex(ValueError, "LOCAL_ASR_ENABLED"):
            _reload_config_module()

    def test_audio_transcription_service_rejects_unsupported_provider(self):
        config = {
            "provider": "unsupported_provider",
            "model": "large-v3",
            "device": "cpu",
            "compute_type": "int8",
            "language": "zh",
            "beam_size": 5,
            "vad_filter": True,
            "output_timestamps": True,
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

    def test_audio_transcription_service_passes_output_timestamps_to_transcriber(self):
        config = {
            "provider": "faster_whisper",
            "model": "large-v3",
            "device": "cpu",
            "compute_type": "int8",
            "language": "zh",
            "beam_size": 5,
            "vad_filter": True,
            "output_timestamps": False,
            "temp_dir": "./data/temp_asr",
            "max_audio_minutes": 90,
            "cleanup_temp_files": True,
        }

        with mock.patch(
            "services.ai_summary.audio_transcription_service.LOCAL_ASR_CONFIG",
            config,
        ):
            with mock.patch(
                "services.ai_summary.audio_transcription_service.WhisperTranscriber"
            ) as whisper_transcriber:
                service = AudioTranscriptionService(fetcher=mock.Mock())

        whisper_transcriber.assert_called_once_with(
            model_name="large-v3",
            device="cpu",
            compute_type="int8",
            language="zh",
            beam_size=5,
            vad_filter=True,
            output_timestamps=False,
        )
        self.assertIs(service.transcriber, whisper_transcriber.return_value)
