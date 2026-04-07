import unittest
import asyncio
import threading
from types import SimpleNamespace
from unittest import mock

from services.ai_summary.whisper_transcriber import (
    ASRErrorType,
    WhisperTranscriber,
)


class TestWhisperTranscriber(unittest.IsolatedAsyncioTestCase):
    def test_segments_to_text_formats_timestamps_and_skips_empty_text(self):
        segments = [
            SimpleNamespace(start=0.2, text="  开场  "),
            SimpleNamespace(start=59.8, text="   "),
            SimpleNamespace(start=3661.4, text="总结"),
        ]

        text = WhisperTranscriber.segments_to_text(segments)

        self.assertEqual(text, "[00:00] 开场\n[01:01:01] 总结")

    def test_segments_to_text_can_omit_timestamps(self):
        segments = [
            SimpleNamespace(start=0.2, text="  开场  "),
            SimpleNamespace(start=3661.4, text="总结"),
        ]

        text = WhisperTranscriber.segments_to_text(segments, output_timestamps=False)

        self.assertEqual(text, "开场\n总结")

    async def test_transcribe_reuses_loaded_model_across_calls(self):
        segments = [SimpleNamespace(start=3.0, text="第一段")]
        model_instances = []

        class FakeModel:
            def __init__(self, model_name, device, compute_type):
                self.init_args = (model_name, device, compute_type)
                self.calls = []
                model_instances.append(self)

            def transcribe(self, audio_path, language, beam_size, vad_filter):
                self.calls.append((audio_path, language, beam_size, vad_filter))
                return segments, {"language": language}

        transcriber = WhisperTranscriber(
            model_name="small",
            device="cpu",
            compute_type="int8",
            language="zh",
            beam_size=7,
            vad_filter=False,
            output_timestamps=True,
        )

        with mock.patch(
            "services.ai_summary.whisper_transcriber.WhisperModel",
            FakeModel,
        ):
            first = await transcriber.transcribe("/tmp/audio-1.wav")
            second = await transcriber.transcribe("/tmp/audio-2.wav")

        self.assertEqual(first, "[00:03] 第一段")
        self.assertEqual(second, "[00:03] 第一段")
        self.assertEqual(len(model_instances), 1)
        self.assertEqual(model_instances[0].init_args, ("small", "cpu", "int8"))
        self.assertEqual(
            model_instances[0].calls,
            [
                ("/tmp/audio-1.wav", "zh", 7, False),
                ("/tmp/audio-2.wav", "zh", 7, False),
            ],
        )
        self.assertEqual(transcriber.last_error_type, ASRErrorType.NONE)
        self.assertIsNone(transcriber.last_error)

    async def test_transcribe_classifies_empty_output(self):
        class FakeModel:
            def __init__(self, model_name, device, compute_type):
                pass

            def transcribe(self, audio_path, language, beam_size, vad_filter):
                return [SimpleNamespace(start=1.0, text="   ")], {}

        transcriber = WhisperTranscriber(
            model_name="small",
            device="cpu",
            compute_type="int8",
            language="zh",
            beam_size=5,
            vad_filter=True,
            output_timestamps=True,
        )

        with mock.patch(
            "services.ai_summary.whisper_transcriber.WhisperModel",
            FakeModel,
        ):
            result = await transcriber.transcribe("/tmp/audio.wav")

        self.assertIsNone(result)
        self.assertEqual(transcriber.last_error_type, ASRErrorType.ASR_OUTPUT_EMPTY)
        self.assertEqual(
            transcriber.last_error, "Whisper transcription produced empty text"
        )

    async def test_transcribe_classifies_model_load_failure(self):
        transcriber = WhisperTranscriber(
            model_name="missing-model",
            device="cpu",
            compute_type="int8",
            language="zh",
            beam_size=5,
            vad_filter=True,
            output_timestamps=True,
        )

        with mock.patch(
            "services.ai_summary.whisper_transcriber.WhisperModel",
            side_effect=RuntimeError("load failed"),
        ):
            with self.assertLogs(
                "services.ai_summary.whisper_transcriber.WhisperTranscriber",
                level="WARNING",
            ) as logs:
                result = await transcriber.transcribe("/tmp/audio.wav")

        self.assertIsNone(result)
        self.assertEqual(
            transcriber.last_error_type, ASRErrorType.ASR_MODEL_LOAD_FAILED
        )
        self.assertEqual(transcriber.last_error, "load failed")
        self.assertIn("Whisper transcription failed: load failed", logs.output[0])

    async def test_transcribe_classifies_transcribe_failure(self):
        class FakeModel:
            def __init__(self, model_name, device, compute_type):
                pass

            def transcribe(self, audio_path, language, beam_size, vad_filter):
                raise RuntimeError("transcribe failed")

        transcriber = WhisperTranscriber(
            model_name="small",
            device="cpu",
            compute_type="int8",
            language="zh",
            beam_size=5,
            vad_filter=True,
            output_timestamps=True,
        )

        with mock.patch(
            "services.ai_summary.whisper_transcriber.WhisperModel",
            FakeModel,
        ):
            with self.assertLogs(
                "services.ai_summary.whisper_transcriber.WhisperTranscriber",
                level="WARNING",
            ) as logs:
                result = await transcriber.transcribe("/tmp/audio.wav")

        self.assertIsNone(result)
        self.assertEqual(
            transcriber.last_error_type, ASRErrorType.ASR_TRANSCRIBE_FAILED
        )
        self.assertEqual(transcriber.last_error, "transcribe failed")
        self.assertIn("Whisper transcription failed: transcribe failed", logs.output[0])

    async def test_transcribe_serializes_shared_instance_calls(self):
        entered = threading.Event()
        release = threading.Event()
        state = {"active": 0, "max_active": 0, "calls": []}

        class FakeModel:
            def __init__(self, model_name, device, compute_type):
                pass

            def transcribe(self, audio_path, language, beam_size, vad_filter):
                state["active"] += 1
                state["max_active"] = max(state["max_active"], state["active"])
                state["calls"].append(audio_path)
                entered.set()
                try:
                    release.wait(timeout=1)
                    return [SimpleNamespace(start=0.0, text=audio_path)], {}
                finally:
                    state["active"] -= 1

        transcriber = WhisperTranscriber(
            model_name="small",
            device="cpu",
            compute_type="int8",
            language="zh",
            beam_size=5,
            vad_filter=True,
            output_timestamps=True,
        )

        with mock.patch(
            "services.ai_summary.whisper_transcriber.WhisperModel",
            FakeModel,
        ):
            first_task = asyncio.create_task(transcriber.transcribe("first"))

            for _ in range(50):
                if entered.is_set():
                    break
                await asyncio.sleep(0.01)

            self.assertTrue(entered.is_set(), "first transcription never started")

            second_task = asyncio.create_task(transcriber.transcribe("second"))
            await asyncio.sleep(0.05)

            self.assertEqual(state["calls"], ["first"])
            self.assertEqual(state["max_active"], 1)

            release.set()

            first_result = await first_task
            second_result = await second_task

        self.assertEqual(first_result, "[00:00] first")
        self.assertEqual(second_result, "[00:00] second")
        self.assertEqual(state["calls"], ["first", "second"])
        self.assertEqual(state["max_active"], 1)

    async def test_transcribe_omits_timestamps_when_disabled(self):
        class FakeModel:
            def __init__(self, model_name, device, compute_type):
                pass

            def transcribe(self, audio_path, language, beam_size, vad_filter):
                return [SimpleNamespace(start=3.0, text="第一段")], {}

        transcriber = WhisperTranscriber(
            model_name="small",
            device="cpu",
            compute_type="int8",
            language="zh",
            beam_size=5,
            vad_filter=True,
            output_timestamps=False,
        )

        with mock.patch(
            "services.ai_summary.whisper_transcriber.WhisperModel",
            FakeModel,
        ):
            result = await transcriber.transcribe("/tmp/audio.wav")

        self.assertEqual(result, "第一段")


if __name__ == "__main__":
    unittest.main()
