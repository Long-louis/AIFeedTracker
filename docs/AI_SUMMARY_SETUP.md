# AI 视频总结配置

项目支持通过 OpenAI 兼容接口对 B 站视频字幕生成结构化总结；当视频没有可用字幕时，可选地启用本地 ASR 回退。

## 视频总结输出结构

视频总结固定输出两个模块：

- `## 关键信息和观点`
- `## 时间线总结`

不会输出一句话总结、标题解读、风险与不确定性、可执行关注清单等额外模块。

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

运行时说明：

- 本地运行时需要可用的 `ffmpeg`，用于音频处理。
- `deploy/docker-compose.yml` 对应 CPU / 无 GPU 环境，当前 Docker 镜像已包含 `ffmpeg`，可在容器内以 CPU 方式运行 `faster_whisper`。
- `deploy/docker-compose.gpu.yml` 对应 GPU 环境，宿主机需要先安装 NVIDIA Container Toolkit。
- GPU compose 会使用 `Dockerfile.gpu` 提供 CUDA/cuDNN 运行库，但是否真正启用本地 GPU ASR，仍取决于 `.env` 中是否开启 `LOCAL_ASR_ENABLED=true` 并设置 `LOCAL_ASR_DEVICE=cuda`。
- 不要把容器运行在 GPU 主机上视为自动获得 GPU ASR；应用配置仍然需要显式打开。

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

GPU 主机示例：

```env
LOCAL_ASR_ENABLED=true
LOCAL_ASR_PROVIDER=faster_whisper
LOCAL_ASR_MODEL=large-v3
LOCAL_ASR_DEVICE=cuda
LOCAL_ASR_COMPUTE_TYPE=float16
```

如果使用容器部署，CPU 路径使用 `deploy/docker-compose.yml`；GPU 路径使用 `deploy/docker-compose.gpu.yml`。

本地 ASR 不需要额外的私有 `data/*.json` 示例文件；公开仓库中的 `env.example`、`data/feishu_channels.json.example` 和 `data/bilibili_creators.json.example` 已覆盖初始化所需示例。

## 工作方式

1. 服务检测到视频动态
2. 尝试获取视频字幕
3. 如果没有字幕且已启用本地 ASR，则使用 `faster_whisper` 转写音频
4. 调用 AI 服务生成 Markdown 总结
5. 将总结附加到飞书卡片中
6. 如已启用飞书知识库写入，则把总结写入文档，并在 `AI 总结` 区块末尾追加知识库文档链接

`AI_API_KEY` 是启用 AI 总结服务的必填项；如果未配置，`AISummaryService` 初始化时会报错，服务无法正常启用 AI 总结流程。

## 验证

配置完成后运行：

```bash
uv run python main.py --mode monitor --once
```

如果视频存在可获取字幕，或在字幕缺失时成功触发本地 ASR 回退且 AI 调用成功，推送内容中会包含总结结果。

## 飞书知识库（可选）

开启后，视频总结会写入飞书文档知识库，目录结构为：

`根 -> 博主 -> YYYY-MM -> 视频文档`

`.env` 示例：

```env
FEISHU_DOCS_ENABLED=true
FEISHU_DOCS_APP_ID=your-feishu-app-id
FEISHU_DOCS_APP_SECRET=your-feishu-app-secret
FEISHU_DOCS_WIKI_SPACE_ID=your-feishu-wiki-space-id

# 可选
# FEISHU_DOCS_ROOT_NODE_TOKEN=
# FEISHU_DOCS_ROOT_TITLE=AI视频知识库
# FEISHU_DOCS_STATE_PATH=./data/feishu_doc_state.json
```

说明：

- 知识库写入失败不会阻断原有飞书消息发送。
- 知识库写入成功时，消息中的 `AI 总结` 模块末尾会追加 `[知识库文档](...)`。
