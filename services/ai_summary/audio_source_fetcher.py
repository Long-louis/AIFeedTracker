# -*- coding: utf-8 -*-

import asyncio
import logging
import re
import shutil
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

import aiohttp
from bilibili_api import video

from config import ANTI_BAN_CONFIG, build_bilibili_credential


class AudioFetchErrorType(Enum):
    NONE = "none"
    AUDIO_SOURCE_UNAVAILABLE = "audio_source_unavailable"
    AUDIO_DOWNLOAD_FAILED = "audio_download_failed"
    AUDIO_CONVERT_FAILED = "audio_convert_failed"
    AUDIO_DURATION_EXCEEDED = "audio_duration_exceeded"


@dataclass
class AudioSourceResult:
    video_id: str
    audio_path: str
    workspace: str
    duration_seconds: Optional[float]


class _AudioDownloadError(Exception):
    pass


class _AudioConvertError(Exception):
    pass


class AudioSourceFetcher:
    def __init__(self, temp_dir: str, max_audio_minutes: int, cleanup_temp_files: bool):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.temp_dir = Path(temp_dir)
        self.max_audio_minutes = max_audio_minutes
        self.cleanup_temp_files = cleanup_temp_files
        self.credential = build_bilibili_credential()
        self.last_error: Optional[str] = None
        self.last_error_type = AudioFetchErrorType.NONE

    def _reset_error(self) -> None:
        self.last_error = None
        self.last_error_type = AudioFetchErrorType.NONE

    def _set_error(self, error_type: AudioFetchErrorType, message: str) -> None:
        self.last_error = message
        self.last_error_type = error_type

    def _extract_bvid(self, video_url: str) -> Optional[str]:
        match = re.search(r"BV[a-zA-Z0-9]+", video_url)
        if match:
            return match.group(0)
        return None

    def _resolve_page_context(
        self, video_url: str, video_info: dict
    ) -> tuple[Optional[int], int]:
        pages = video_info.get("pages") or []
        cid = video_info.get("cid")
        page_index = 0

        page_values = parse_qs(urlparse(video_url).query).get("p")
        if page_values:
            try:
                requested_page = int(page_values[0])
            except (TypeError, ValueError):
                requested_page = 1
            if requested_page > 0 and requested_page <= len(pages):
                page_index = requested_page - 1
                cid = pages[page_index].get("cid", cid)
                return cid, page_index

        if pages and cid is not None:
            for index, page in enumerate(pages):
                if page.get("cid") == cid:
                    return cid, index

        if pages and cid is None:
            cid = pages[0].get("cid")

        return cid, page_index

    def _resolve_duration_seconds(
        self, video_info: dict, page_index: int
    ) -> Optional[float]:
        pages = video_info.get("pages") or []
        if 0 <= page_index < len(pages):
            page_duration = pages[page_index].get("duration")
            if isinstance(page_duration, (int, float)):
                return page_duration

        duration_seconds = video_info.get("duration")
        if isinstance(duration_seconds, (int, float)):
            return duration_seconds

        return None

    def _select_audio_source(self, download_data: dict) -> Optional[str]:
        payload = download_data.get("video_info", download_data)
        dash_audio = payload.get("dash", {}).get("audio") or []
        if dash_audio:
            best_stream = max(dash_audio, key=lambda item: item.get("id", 0))
            stream_url = best_stream.get("baseUrl") or best_stream.get("base_url")
            if stream_url:
                return self._normalize_source_url(stream_url)

        durl = payload.get("durl") or []
        if durl:
            stream_url = durl[0].get("url")
            if stream_url:
                return self._normalize_source_url(stream_url)

        return None

    def _normalize_source_url(self, source_url: str) -> str:
        if source_url.startswith("//"):
            return f"https:{source_url}"
        return source_url

    def _build_workspace(self, video_id: str) -> Path:
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        return Path(tempfile.mkdtemp(prefix=f"{video_id}-", dir=self.temp_dir))

    def _build_cookies(self) -> dict:
        cookies = {}
        if not self.credential:
            return cookies
        if self.credential.sessdata:
            cookies["SESSDATA"] = self.credential.sessdata
        if self.credential.bili_jct:
            cookies["bili_jct"] = self.credential.bili_jct
        if self.credential.buvid3:
            cookies["buvid3"] = self.credential.buvid3
        if self.credential.buvid4:
            cookies["buvid4"] = self.credential.buvid4
        if self.credential.dedeuserid:
            cookies["DedeUserID"] = self.credential.dedeuserid
        return cookies

    async def _download_media(
        self, source_url: str, destination: Path, referer: str
    ) -> Path:
        headers = {
            "User-Agent": ANTI_BAN_CONFIG["user_agent"],
            "Referer": referer,
        }
        timeout = aiohttp.ClientTimeout(total=ANTI_BAN_CONFIG.get("timeout", 30))

        try:
            async with aiohttp.ClientSession(
                headers=headers,
                cookies=self._build_cookies(),
                timeout=timeout,
            ) as session:
                async with session.get(source_url) as response:
                    response.raise_for_status()
                    with open(destination, "wb") as output_file:
                        async for chunk in response.content.iter_chunked(65536):
                            output_file.write(chunk)
        except Exception as exc:
            raise _AudioDownloadError(str(exc)) from exc

        return destination

    async def _normalize_audio(self, source_path: Path, output_path: Path) -> Path:
        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-y",
            "-i",
            str(source_path),
            "-ac",
            "1",
            "-ar",
            "16000",
            str(output_path),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            raise _AudioConvertError(stderr.decode("utf-8", errors="ignore").strip())
        if not output_path.exists():
            raise _AudioConvertError("ffmpeg 未生成音频文件")
        return output_path

    async def fetch_audio(self, video_url: str) -> Optional[AudioSourceResult]:
        self._reset_error()

        bvid = self._extract_bvid(video_url)
        if not bvid:
            self._set_error(
                AudioFetchErrorType.AUDIO_SOURCE_UNAVAILABLE,
                "无法从URL中提取BV号",
            )
            return None

        video_client = video.Video(bvid=bvid, credential=self.credential)
        try:
            video_info = await video_client.get_info()
        except Exception as exc:
            self._set_error(AudioFetchErrorType.AUDIO_SOURCE_UNAVAILABLE, str(exc))
            return None

        cid, page_index = self._resolve_page_context(video_url, video_info)
        if cid is None:
            self._set_error(
                AudioFetchErrorType.AUDIO_SOURCE_UNAVAILABLE,
                f"视频 {bvid} 缺少可用 cid",
            )
            return None

        duration_seconds = self._resolve_duration_seconds(video_info, page_index)
        if (
            isinstance(duration_seconds, (int, float))
            and duration_seconds > self.max_audio_minutes * 60
        ):
            self._set_error(
                AudioFetchErrorType.AUDIO_DURATION_EXCEEDED,
                f"视频时长 {duration_seconds} 秒超出限制",
            )
            return None

        try:
            download_data = await video_client.get_download_url(
                page_index=page_index, cid=cid
            )
        except Exception as exc:
            self._set_error(AudioFetchErrorType.AUDIO_SOURCE_UNAVAILABLE, str(exc))
            return None
        source_url = self._select_audio_source(download_data)
        if not source_url:
            self._set_error(
                AudioFetchErrorType.AUDIO_SOURCE_UNAVAILABLE,
                f"视频 {bvid} 没有可用音频流",
            )
            return None

        workspace = self._build_workspace(bvid)
        source_path = workspace / "source_media"
        output_path = workspace / "audio.wav"
        referer = f"https://www.bilibili.com/video/{bvid}"

        try:
            downloaded_path = await self._download_media(
                source_url, source_path, referer
            )
            normalized_path = await self._normalize_audio(downloaded_path, output_path)
            return AudioSourceResult(
                video_id=bvid,
                audio_path=str(normalized_path),
                workspace=str(workspace),
                duration_seconds=duration_seconds,
            )
        except _AudioDownloadError as exc:
            self._set_error(AudioFetchErrorType.AUDIO_DOWNLOAD_FAILED, str(exc))
        except _AudioConvertError as exc:
            self._set_error(AudioFetchErrorType.AUDIO_CONVERT_FAILED, str(exc))

        if self.cleanup_temp_files:
            self.cleanup_workspace(workspace)
        return None

    def cleanup_workspace(self, workspace: Path | str) -> None:
        workspace_path = Path(workspace)
        try:
            temp_root = self.temp_dir.resolve()
            resolved_workspace = workspace_path.resolve()
        except FileNotFoundError:
            return

        if (
            resolved_workspace == temp_root
            or temp_root not in resolved_workspace.parents
        ):
            self.logger.warning("拒绝清理 temp_dir 之外的目录: %s", workspace_path)
            return

        shutil.rmtree(resolved_workspace, ignore_errors=True)
