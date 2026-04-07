# -*- coding: utf-8 -*-

import logging
from typing import Optional

from config import LOCAL_ASR_CONFIG

from .audio_source_fetcher import AudioSourceFetcher
from .whisper_transcriber import WhisperTranscriber


class AudioTranscriptionService:
    def __init__(self, fetcher=None, transcriber=None):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        provider = LOCAL_ASR_CONFIG["provider"]
        if provider != "faster_whisper":
            raise ValueError(
                f"Unsupported LOCAL_ASR_PROVIDER: {provider}. Only 'faster_whisper' is supported."
            )

        if fetcher is None:
            fetcher = AudioSourceFetcher(
                temp_dir=LOCAL_ASR_CONFIG["temp_dir"],
                max_audio_minutes=LOCAL_ASR_CONFIG["max_audio_minutes"],
                cleanup_temp_files=LOCAL_ASR_CONFIG["cleanup_temp_files"],
            )
        if transcriber is None:
            transcriber = WhisperTranscriber(
                model_name=LOCAL_ASR_CONFIG["model"],
                device=LOCAL_ASR_CONFIG["device"],
                compute_type=LOCAL_ASR_CONFIG["compute_type"],
                language=LOCAL_ASR_CONFIG["language"],
                beam_size=LOCAL_ASR_CONFIG["beam_size"],
                vad_filter=LOCAL_ASR_CONFIG["vad_filter"],
                output_timestamps=LOCAL_ASR_CONFIG["output_timestamps"],
            )

        self.fetcher = fetcher
        self.transcriber = transcriber
        self.last_error: Optional[str] = None
        self.last_error_type = None

    async def transcribe_video(self, video_url: str) -> dict | None:
        self.last_error = None
        self.last_error_type = None
        audio_result = None

        try:
            audio_result = await self.fetcher.fetch_audio(video_url)
            if audio_result is None:
                self.last_error = self.fetcher.last_error or "音频获取失败"
                self.last_error_type = getattr(self.fetcher, "last_error_type", None)
                return None

            text = await self.transcriber.transcribe(audio_result.audio_path)
            if text is None:
                self.last_error = self.transcriber.last_error or "音频转写失败"
                self.last_error_type = getattr(
                    self.transcriber, "last_error_type", None
                )
                return None

            return {
                "text": text,
                "text_source": "local_asr",
                "video_id": audio_result.video_id,
                "duration_seconds": audio_result.duration_seconds,
            }
        finally:
            if audio_result is not None and self.fetcher.cleanup_temp_files:
                try:
                    self.fetcher.cleanup_workspace(audio_result.workspace)
                except Exception:
                    self.logger.exception(
                        "Failed to cleanup transcription workspace: %s",
                        audio_result.workspace,
                    )
