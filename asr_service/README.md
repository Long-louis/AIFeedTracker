# SenseVoice FastAPI Service

Standalone ASR service based on FunASR + SenseVoice (`iic/SenseVoiceSmall`) for NVIDIA GPU environments.

## Prerequisites

- Docker Engine with Docker Compose plugin (or legacy `docker-compose`).
- NVIDIA Container Toolkit configured on host (GPU passthrough must work).
- NVIDIA GPU driver compatible with CUDA 12.4 runtime images.
- Internet access for first model download, or pre-warmed cache under `asr_service/cache/modelscope`.

## API

- `GET /health`: service status and model readiness.
- `POST /v1/transcribe`: multipart upload with field `file`; returns `text`, and `segments` when `include_segments=true`.

Example:

```bash
curl -X POST "http://127.0.0.1:8900/v1/transcribe?include_segments=true" \
  -F "file=@/path/to/audio.wav"
```

## Docker deployment

Use an isolated folder for this service (any path you manage). Do not run it by mounting from a development workspace.

```bash
# 1) Copy asr_service/ to your deployment folder
cd <asr-service-deploy-folder>/deploy
docker compose up -d --build || docker-compose up -d --build
```

The compose file mounts `../cache/modelscope` (relative to your deployment folder), so model cache stays with the ASR service and does not depend on your source repo location.

## Runtime notes

- Container runs as non-root user `app`.
- Upload size is limited by `ASR_MAX_UPLOAD_BYTES` (default: `26214400`, 25 MiB).
- Long audio is split into chunks before inference (`ASR_SEGMENT_SECONDS`, default: `45`) to reduce memory pressure.
- `/v1/transcribe` accepts only audio MIME types (`audio/*`).
- Model cache is mounted to `/home/app/.cache/modelscope`; keep write permission for host path.
- `/health` reports readiness and a coarse error marker only; detailed failures stay in container logs.
