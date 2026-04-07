# AI 视频总结配置

项目支持通过 OpenAI 兼容接口对 B 站视频字幕生成结构化总结；当视频没有可用字幕时，可选地启用本地 ASR 回退。

## 支持的服务

- `deepseek`
- `zhipu`
- `qwen`

默认推荐 `deepseek`。

## 最小配置

在 `.env` 中填写：

```env
AI_SERVICE=deepseek
AI_API_KEY=your-api-key
```

可选配置：

```env
# AI_BASE_URL=https://api.deepseek.com
# AI_MODEL=deepseek-chat
```

## 本地 ASR 回退

本地 ASR 只在视频字幕不可用时才会参与处理。

- `LOCAL_ASR_ENABLED=false` 会完全禁用本地 ASR 回退。
- `LOCAL_ASR_PROVIDER` 当前只支持 `faster_whisper`。
- `LOCAL_ASR_DEVICE=cpu` 是无 GPU 环境的配置方式。

示例配置：

```env
# 关闭本地 ASR 回退
# LOCAL_ASR_ENABLED=false

# 启用本地 ASR 回退（仅支持 faster_whisper）
LOCAL_ASR_ENABLED=true
LOCAL_ASR_PROVIDER=faster_whisper
LOCAL_ASR_MODEL=large-v3
LOCAL_ASR_DEVICE=cpu
LOCAL_ASR_COMPUTE_TYPE=int8
LOCAL_ASR_LANGUAGE=zh
LOCAL_ASR_BEAM_SIZE=5
LOCAL_ASR_VAD_FILTER=true
LOCAL_ASR_OUTPUT_TIMESTAMPS=true
LOCAL_ASR_TEMP_DIR=./data/temp_asr
LOCAL_ASR_MAX_AUDIO_MINUTES=90
LOCAL_ASR_CLEANUP_TEMP_FILES=true
```

本地 ASR 不需要额外的私有 `data/*.json` 示例文件；公开仓库中的 `env.example`、`data/feishu_channels.json.example` 和 `data/bilibili_creators.json.example` 已覆盖初始化所需示例。

## 工作方式

1. 服务检测到视频动态
2. 尝试获取视频字幕
3. 如果没有字幕且已启用本地 ASR，则使用 `faster_whisper` 转写音频
4. 调用 AI 服务生成 Markdown 总结
5. 将总结附加到飞书卡片中

如果没有配置 `AI_API_KEY`，服务仍可运行，只是不会生成 AI 总结。

## 验证

配置完成后运行：

```bash
uv run python main.py --mode monitor --once
```

如果视频存在可获取字幕，或在字幕缺失时成功触发本地 ASR 回退且 AI 调用成功，推送内容中会包含总结结果。
