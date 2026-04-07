# -*- coding: utf-8 -*-

import asyncio
import logging
from enum import Enum
from typing import Optional

from services.ai_summary.subtitle_fetcher import SubtitleFetcher

try:
    from faster_whisper import WhisperModel
except ImportError:  # pragma: no cover - exercised via model load failure path
    WhisperModel = None


class ASRErrorType(Enum):
    NONE = "none"
    ASR_MODEL_LOAD_FAILED = "asr_model_load_failed"
    ASR_TRANSCRIBE_FAILED = "asr_transcribe_failed"
    ASR_OUTPUT_EMPTY = "asr_output_empty"


class WhisperTranscriber:
    def __init__(
        self,
        model_name: str,
        device: str,
        compute_type: str,
        language: str,
        beam_size: int,
        vad_filter: bool,
        output_timestamps: bool,
    ):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.beam_size = beam_size
        self.vad_filter = vad_filter
        self.output_timestamps = output_timestamps
        self._model = None
        self._transcribe_lock = asyncio.Lock()
        self.last_error: Optional[str] = None
        self.last_error_type = ASRErrorType.NONE

    def _reset_error(self) -> None:
        self.last_error = None
        self.last_error_type = ASRErrorType.NONE

    def _set_error(self, error_type: ASRErrorType, message: str) -> None:
        self.last_error = message
        self.last_error_type = error_type

    def _get_model(self):
        if self._model is not None:
            return self._model
        if WhisperModel is None:
            raise RuntimeError("faster_whisper is not installed")
        self._model = WhisperModel(
            self.model_name,
            device=self.device,
            compute_type=self.compute_type,
        )
        return self._model

    @staticmethod
    def segments_to_text(segments, output_timestamps: bool = True) -> str:
        lines = []
        for segment in segments:
            content = getattr(segment, "text", "")
            if not isinstance(content, str):
                continue
            content = content.strip()
            if not content:
                continue

            start = getattr(segment, "start", None)
            if output_timestamps and isinstance(start, (int, float)):
                timestamp = SubtitleFetcher.format_timestamp(float(start))
                lines.append(f"[{timestamp}] {content}")
            else:
                lines.append(content)
        return "\n".join(lines)

    def _transcribe_sync(self, audio_path: str) -> str:
        model = self._get_model()
        segments, _ = model.transcribe(
            audio_path,
            language=self.language,
            beam_size=self.beam_size,
            vad_filter=self.vad_filter,
        )
        return self.segments_to_text(segments, output_timestamps=self.output_timestamps)

    async def transcribe(self, audio_path: str) -> Optional[str]:
        async with self._transcribe_lock:
            self._reset_error()

            try:
                text = await asyncio.to_thread(self._transcribe_sync, audio_path)
            except Exception as exc:
                error_message = str(exc)
                if self._model is None:
                    self._set_error(ASRErrorType.ASR_MODEL_LOAD_FAILED, error_message)
                else:
                    self._set_error(ASRErrorType.ASR_TRANSCRIBE_FAILED, error_message)
                self.logger.warning("Whisper transcription failed: %s", error_message)
                return None

            if not text:
                self._set_error(
                    ASRErrorType.ASR_OUTPUT_EMPTY,
                    "Whisper transcription produced empty text",
                )
                return None

            return text
