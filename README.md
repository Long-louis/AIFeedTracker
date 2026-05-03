# AI Feed Tracker

![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

一个用于监控 B 站动态、推送飞书卡片，并生成 AI 视频总结的机器人服务。

## 功能概览

- B 站动态监控，支持视频、图文、文字、直播等常见动态类型
- 飞书模板卡片推送，支持 `app:*` / `webhook:*` 通道路由（示例默认 `app:default`）
- AI 视频总结能力（当前运行时会初始化 `AISummaryService`，需配置 `AI_API_KEY`，否则启动时报错）
- 可选外部 ASR 回退：当视频字幕缺失时，可启用 SenseVoice API 服务进行转写回退（由主应用通过 HTTP 调用）
- 可选飞书知识库写入：视频总结可写入飞书文档，并在消息 `AI 总结` 区块末尾附文档链接
- B 站凭证刷新与二维码登录辅助

## 快速开始

### 环境要求

- Python 3.11+
- [uv](https://github.com/astral-sh/uv)

### 安装与初始化

```bash
git clone https://github.com/Long-louis/AIFeedTracker.git
cd AIFeedTracker
uv sync --frozen
cp env.example .env
cp data/feishu_channels.json.example data/feishu_channels.json
cp data/bilibili_creators.json.example data/bilibili_creators.json
```

填写 `.env`、`data/feishu_channels.json` 和 `data/bilibili_creators.json` 后运行：

```bash
uv run python main.py --mode service
```

## Docker 部署

仓库提供两条公开部署路径：

- CPU / 无 GPU 环境：使用 `deploy/docker-compose.yml`
- GPU 环境：使用 `deploy/docker-compose.gpu.yml`，宿主机需先安装 NVIDIA Container Toolkit

如果你使用的是新的 Docker Compose 插件，可以把下面的 `docker-compose` 命令替换成 `docker compose`。

CPU 部署：

```bash
cp env.example .env
cp data/feishu_channels.json.example data/feishu_channels.json
cp data/bilibili_creators.json.example data/bilibili_creators.json
docker-compose -f deploy/docker-compose.yml up -d --build
```

GPU 部署：

```bash
cp env.example .env
cp data/feishu_channels.json.example data/feishu_channels.json
cp data/bilibili_creators.json.example data/bilibili_creators.json
docker-compose -f deploy/docker-compose.gpu.yml up -d --build
```

如果启用 ASR 回退，主应用改为调用外部 SenseVoice API 服务；在 `.env` 中至少配置：

```env
LOCAL_ASR_ENABLED=true
LOCAL_ASR_PROVIDER=sensevoice_api
ASR_API_URL=http://127.0.0.1:8900/v1/transcribe
ASR_API_TIMEOUT_SECONDS=300
```

可选部署 SenseVoice ASR 服务：`asr_service/deploy/docker-compose.yml`。
若使用 GPU 推理，请先在宿主机安装 NVIDIA Container Toolkit。

## 配置说明

- 统一配置与运行说明（推荐先看）：`docs/Configuration.md`
- 文档索引：`docs/README.md`

### 飞书知识库权限说明

如果开启飞书知识库写入（`FEISHU_DOCS_ENABLED=true`），建议为应用开通 Markdown 转文档块所需权限：

- `docx:document.block:convert`

如果缺少该权限，系统会自动回退为纯文本块写入，不会阻断主消息推送。

## 升级提醒

升级到新版本后，请同步检查 `.env` 与 `data/*.json` 配置文件是否仍与最新示例文件一致；如示例文件结构有变化，请手动更新你的本地配置文件。
建议优先对照 `env.example`、`data/feishu_channels.json.example`、`data/bilibili_creators.json.example` 逐项刷新。

## 许可证

本项目采用 [MIT License](LICENSE) 开源协议。
