# -*- coding: utf-8 -*-

import asyncio
import logging
from enum import Enum
from pathlib import Path
from typing import Optional

import aiohttp


class ASRErrorType(Enum):
    NONE = "none"
    ASR_API_TIMEOUT = "asr_api_timeout"
    ASR_API_REQUEST_FAILED = "asr_api_request_failed"
    ASR_API_OUTPUT_EMPTY = "asr_api_output_empty"
    ASR_OUTPUT_EMPTY = ASR_API_OUTPUT_EMPTY


class LocalAudioFileOpenError(Exception):
    pass


class SenseVoiceClient:
    def __init__(self, api_url: str, timeout_seconds: int):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.api_url = api_url
        self.timeout_seconds = timeout_seconds
        self.last_error: Optional[str] = None
        self.last_error_type = ASRErrorType.NONE

    async def transcribe(self, audio_path: str) -> Optional[str]:
        self.last_error = None
        self.last_error_type = ASRErrorType.NONE

        try:
            payload = await self._post_audio(audio_path)
        except asyncio.TimeoutError:
            self.last_error_type = ASRErrorType.ASR_API_TIMEOUT
            self.last_error = "ASR API 请求超时"
            return None
        except LocalAudioFileOpenError as exc:
            self.last_error_type = ASRErrorType.ASR_API_REQUEST_FAILED
            self.last_error = str(exc)
            return None
        except Exception as exc:
            self.last_error_type = ASRErrorType.ASR_API_REQUEST_FAILED
            self.last_error = f"ASR API 调用失败: {exc}"
            return None

        text = str(payload.get("text") or "").strip()
        if not text:
            self.last_error_type = ASRErrorType.ASR_API_OUTPUT_EMPTY
            self.last_error = "ASR API 输出为空"
            return None

        return text

    async def _post_audio(self, audio_path: str) -> dict:
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        form = aiohttp.FormData()
        path = Path(audio_path)

        try:
            file_obj = path.open("rb")
        except OSError as exc:
            raise LocalAudioFileOpenError(f"本地音频文件读取失败: {exc}") from exc

        with file_obj:
            form.add_field(
                "file",
                file_obj,
                filename=path.name,
                content_type="audio/wav",
            )
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(self.api_url, data=form) as response:
                    response.raise_for_status()
                    return await response.json()
