import asyncio
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool

try:
    from funasr import AutoModel
except Exception as exc:  # pragma: no cover
    AutoModel = None
    _import_error = exc
else:
    _import_error = None


LOGGER = logging.getLogger("sensevoice-asr")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

APP_TITLE = "SenseVoice ASR Service"
APP_VERSION = "0.1.0"
MODEL_ID = os.getenv("ASR_MODEL", "iic/SenseVoiceSmall")
MODEL_DEVICE = os.getenv("ASR_DEVICE", "cuda")
DEFAULT_MAX_UPLOAD_BYTES = 25 * 1024 * 1024
DEFAULT_SEGMENT_SECONDS = 45


def _get_max_upload_bytes() -> int:
    raw_value = os.getenv("ASR_MAX_UPLOAD_BYTES", str(DEFAULT_MAX_UPLOAD_BYTES)).strip()
    try:
        value = int(raw_value)
    except ValueError:
        LOGGER.warning("Invalid ASR_MAX_UPLOAD_BYTES=%r, using default", raw_value)
        return DEFAULT_MAX_UPLOAD_BYTES
    if value <= 0:
        LOGGER.warning("Non-positive ASR_MAX_UPLOAD_BYTES=%r, using default", raw_value)
        return DEFAULT_MAX_UPLOAD_BYTES
    return value


MAX_UPLOAD_BYTES = _get_max_upload_bytes()


def _get_segment_seconds() -> int:
    raw_value = os.getenv("ASR_SEGMENT_SECONDS", str(DEFAULT_SEGMENT_SECONDS)).strip()
    try:
        value = int(raw_value)
    except ValueError:
        LOGGER.warning("Invalid ASR_SEGMENT_SECONDS=%r, using default", raw_value)
        return DEFAULT_SEGMENT_SECONDS
    if value <= 0:
        LOGGER.warning("Non-positive ASR_SEGMENT_SECONDS=%r, using default", raw_value)
        return DEFAULT_SEGMENT_SECONDS
    return value


SEGMENT_SECONDS = _get_segment_seconds()


def _is_allowed_content_type(content_type: str | None) -> bool:
    if not content_type:
        return False
    normalized = content_type.strip().lower()
    return normalized.startswith("audio/")


class ASRRuntime:
    def __init__(self, model_id: str, device: str):
        self.model_id = model_id
        self.device = device
        self.model: Any | None = None
        self.ready = False
        self.last_error: str | None = None
        self._lock = asyncio.Lock()

    async def ensure_loaded(self) -> None:
        if self.ready:
            return

        async with self._lock:
            if self.ready:
                return
            if AutoModel is None:
                self.last_error = f"FunASR import failed: {_import_error}"
                raise RuntimeError(self.last_error)

            LOGGER.info("Loading ASR model %s on %s", self.model_id, self.device)

            def _load() -> Any:
                return AutoModel(
                    model=self.model_id,
                    trust_remote_code=False,
                    device=self.device,
                )

            try:
                self.model = await run_in_threadpool(_load)
            except Exception as exc:
                self.ready = False
                self.last_error = str(exc)
                raise RuntimeError(f"Model load failed: {exc}") from exc

            self.ready = True
            self.last_error = None
            LOGGER.info("ASR model is ready")

    async def transcribe(
        self,
        audio_path: str,
        *,
        language: str | None = None,
        timestamps: bool | None = None,
    ) -> dict[str, Any]:
        await self.ensure_loaded()
        assert self.model is not None

        generate_kwargs: dict[str, Any] = {}
        if language:
            generate_kwargs["language"] = language
        if timestamps is not None:
            generate_kwargs["timestamps"] = timestamps

        def _generate() -> Any:
            return self.model.generate(input=audio_path, **generate_kwargs)

        result = await run_in_threadpool(_generate)
        return _normalize_result(result)


runtime = ASRRuntime(model_id=MODEL_ID, device=MODEL_DEVICE)
app = FastAPI(title=APP_TITLE, version=APP_VERSION)


@app.on_event("startup")
async def startup_event() -> None:
    try:
        await runtime.ensure_loaded()
    except Exception as exc:
        LOGGER.error("Model pre-load failed: %s", exc)


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok" if runtime.ready else "degraded",
        "version": APP_VERSION,
        "model_ready": runtime.ready,
        "model": runtime.model_id,
        "device": runtime.device,
        "last_error": "model_unavailable" if runtime.last_error else None,
    }


@app.post("/v1/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    include_segments: bool = Query(False),
    language: str | None = Query(None),
    timestamps: bool | None = Query(None),
) -> dict[str, Any]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing upload filename")
    if not _is_allowed_content_type(file.content_type):
        raise HTTPException(status_code=415, detail="Unsupported media type")

    suffix = Path(file.filename).suffix or ".wav"
    temp_path = None
    bytes_written = 0
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            temp_path = tmp.name
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Uploaded file exceeds max size ({MAX_UPLOAD_BYTES} bytes)",
                    )
                tmp.write(chunk)

        if not temp_path or os.path.getsize(temp_path) == 0:
            raise HTTPException(status_code=400, detail="Uploaded audio file is empty")

        start_time = time.perf_counter()
        result = await _transcribe_with_chunking(
            temp_path,
            language=language,
            timestamps=timestamps,
        )
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        text = str(result.get("text") or "").strip()
        if not text:
            raise HTTPException(status_code=502, detail="ASR returned empty text")

        payload: dict[str, Any] = {
            "text": text,
            "model": runtime.model_id,
            "device": runtime.device,
            "elapsed_ms": elapsed_ms,
        }
        if include_segments or timestamps is True:
            payload["segments"] = result.get("segments") or []
        return payload
    except HTTPException:
        raise
    except RuntimeError as exc:
        LOGGER.exception("ASR runtime error")
        raise HTTPException(status_code=503, detail="ASR service unavailable") from exc
    except Exception as exc:
        LOGGER.exception("Transcription failed")
        raise HTTPException(status_code=500, detail="Transcription failed") from exc
    finally:
        await file.close()
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                LOGGER.warning("Failed to remove temp file: %s", temp_path)


def _normalize_result(result: Any) -> dict[str, Any]:
    if isinstance(result, list):
        item = result[0] if result else {}
    elif isinstance(result, dict):
        item = result
    else:
        item = {}

    text = (
        item.get("text")
        or item.get("pred_text")
        or item.get("raw_text")
        or item.get("asr_result")
        or ""
    )

    segments = []
    sentence_info = item.get("sentence_info") or item.get("segments") or []
    if isinstance(sentence_info, list):
        for seg in sentence_info:
            if not isinstance(seg, dict):
                continue
            start = seg.get("start")
            if start is None:
                start = seg.get("start_ms")

            end = seg.get("end")
            if end is None:
                end = seg.get("end_ms")

            segments.append(
                {
                    "start": start,
                    "end": end,
                    "text": seg.get("text") or seg.get("sentence") or "",
                }
            )

    return {"text": str(text).strip(), "segments": segments}


async def _transcribe_with_chunking(
    audio_path: str,
    *,
    language: str | None,
    timestamps: bool | None,
) -> dict[str, Any]:
    segment_paths: list[str] = []
    segment_dir: str | None = None
    try:
        duration_seconds = _probe_duration_seconds(audio_path)
        if duration_seconds > SEGMENT_SECONDS:
            segment_dir, segment_paths = _split_audio_segments(
                audio_path,
                segment_seconds=SEGMENT_SECONDS,
            )
        else:
            segment_paths = [audio_path]

        merged_texts: list[str] = []
        merged_segments: list[dict[str, Any]] = []
        segment_index = 0
        for segment_path in segment_paths:
            try:
                chunk_result = await runtime.transcribe(
                    segment_path,
                    language=language,
                    timestamps=timestamps,
                )
            except Exception as exc:
                if _is_empty_waveform_error(exc):
                    LOGGER.warning("Skipping empty audio segment: %s", segment_path)
                    segment_index += 1
                    continue
                raise
            text = str(chunk_result.get("text") or "").strip()
            if text:
                merged_texts.append(text)

            if timestamps is True:
                offset_ms = int(segment_index * SEGMENT_SECONDS * 1000)
                for seg in chunk_result.get("segments") or []:
                    if not isinstance(seg, dict):
                        continue
                    start = seg.get("start")
                    end = seg.get("end")
                    merged_segments.append(
                        {
                            "start": _offset_number(start, offset_ms),
                            "end": _offset_number(end, offset_ms),
                            "text": seg.get("text") or "",
                        }
                    )
            segment_index += 1

        return {
            "text": "\n".join(merged_texts).strip(),
            "segments": merged_segments,
        }
    finally:
        if segment_dir and os.path.isdir(segment_dir):
            shutil.rmtree(segment_dir, ignore_errors=True)


def _probe_duration_seconds(audio_path: str) -> int:
    duration = _probe_duration_seconds_float(audio_path)
    return max(0, int(duration))


def _probe_duration_seconds_float(audio_path: str) -> float:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        audio_path,
    ]
    try:
        output = subprocess.check_output(
            command, text=True, stderr=subprocess.STDOUT
        ).strip()
        if not output:
            return 0.0

        normalized = output.strip()
        if normalized.lower() in {"n/a", "nan", "inf", "-inf"}:
            return 0.0

        try:
            duration = float(normalized)
        except ValueError:
            matches = re.findall(r"[-+]?\d+(?:\.\d+)?", normalized)
            if matches:
                duration = float(matches[-1])
            elif "n/a" in normalized.lower():
                return 0.0
            else:
                raise
    except Exception as exc:
        raise RuntimeError(f"Probe duration failed: {exc}") from exc
    return max(0.0, duration)


def _split_audio_segments(
    audio_path: str, segment_seconds: int
) -> tuple[str, list[str]]:
    segment_dir = tempfile.mkdtemp(prefix="sensevoice-segments-")
    segment_paths: list[str] = []
    segment_index = 0
    start_seconds = 0

    while True:
        segment_path = os.path.join(segment_dir, f"segment-{segment_index:04d}.wav")
        command = [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-ss",
            str(start_seconds),
            "-t",
            str(segment_seconds),
            "-i",
            audio_path,
            "-ac",
            "1",
            "-ar",
            "16000",
            segment_path,
        ]
        try:
            subprocess.check_output(command, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as exc:
            if segment_index == 0:
                raise RuntimeError(
                    f"Audio split failed: {exc.output.decode(errors='ignore')}"
                ) from exc
            break

        if not os.path.exists(segment_path) or os.path.getsize(segment_path) == 0:
            break

        segment_duration = _probe_duration_seconds_float(segment_path)
        if segment_duration < 0.2:
            break

        segment_paths.append(segment_path)
        segment_index += 1
        start_seconds += segment_seconds

        if segment_index > 1000:
            raise RuntimeError("Audio split created too many segments")

        if segment_duration < float(segment_seconds):
            break

    if not segment_paths:
        raise RuntimeError("Audio split produced no segments")

    return segment_dir, segment_paths


def _offset_number(value: Any, offset_ms: int) -> Any:
    if value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return value
    return number + offset_ms


def _is_empty_waveform_error(exc: Exception) -> bool:
    message = str(exc)
    return "choose a window size" in message and "[2, 0]" in message
