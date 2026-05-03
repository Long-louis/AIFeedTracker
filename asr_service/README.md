# SenseVoice ASR Service（可选模块）

这是主项目的可选 ASR 服务。

当视频没有字幕时，主项目可以调用这个服务继续生成总结。

## 1) 你需要准备什么

- Docker（支持 `docker compose` 或 `docker-compose`）
- 如果用 GPU：已安装 NVIDIA Container Toolkit
- 首次启动需要联网下载模型，后续会走本地缓存

## 2) API 很简单

- `GET /health`：检查服务是否可用、模型是否就绪
- `POST /v1/transcribe`：上传音频，返回识别文本

示例：

```bash
curl -X POST "http://127.0.0.1:8900/v1/transcribe?include_segments=true" \
  -F "file=@/path/to/audio.wav"
```

## 3) Docker 启动

```bash
cd asr_service/deploy
docker compose up -d --build || docker-compose up -d --build
```

说明：

- 模型缓存目录是 `asr_service/cache/modelscope`
- 容器里对应路径是 `/home/app/.cache/modelscope`
- 请保证主机目录可写

## 4) 和主项目对接

在主项目 `.env` 里设置：

```env
LOCAL_ASR_ENABLED=true
LOCAL_ASR_PROVIDER=sensevoice_api
ASR_API_URL=http://127.0.0.1:8900/v1/transcribe
ASR_API_TIMEOUT_SECONDS=300
```

## 5) 常见运行参数

- `ASR_MAX_UPLOAD_BYTES`：单次上传大小限制，默认 25 MiB
- `ASR_SEGMENT_SECONDS`：长音频分段秒数，默认 45

这两个参数用于控制稳定性和内存占用。
