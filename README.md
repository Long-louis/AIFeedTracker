# AI Feed Tracker

![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

AI Feed Tracker 用来做三件事：

- 监控 B 站动态
- 发送飞书通知卡片
- 为视频生成 AI 总结（可选写入飞书知识库）

## 你可以先从这里开始

1. 安装依赖
2. 填写配置
3. 启动服务

```bash
git clone https://github.com/Long-louis/AIFeedTracker.git
cd AIFeedTracker
uv sync --frozen
cp env.example .env
cp data/feishu_channels.json.example data/feishu_channels.json
cp data/bilibili_creators.json.example data/bilibili_creators.json
uv run python main.py --mode service
```

## 主要功能

- 监控常见动态类型：视频、图文、文字、直播
- 飞书通道支持 `app:*` 和 `webhook:*`（示例默认 `app:default`）
- AI 总结需要 `AI_API_KEY`，未配置时启动会直接报错
- 飞书知识库写入为可选能力，写入失败不会阻断消息发送

## Docker 部署（主服务）

仓库提供两条公开部署路径：

- CPU：`deploy/docker-compose.yml`
- GPU：`deploy/docker-compose.gpu.yml`（宿主机先安装 NVIDIA Container Toolkit）

CPU：

```bash
cp env.example .env
cp data/feishu_channels.json.example data/feishu_channels.json
cp data/bilibili_creators.json.example data/bilibili_creators.json
docker-compose -f deploy/docker-compose.yml up -d --build
```

GPU：

```bash
cp env.example .env
cp data/feishu_channels.json.example data/feishu_channels.json
cp data/bilibili_creators.json.example data/bilibili_creators.json
docker-compose -f deploy/docker-compose.gpu.yml up -d --build
```

如果你使用 Docker Compose 插件，可把 `docker-compose` 替换为 `docker compose`。

## 高级可选模块：外部 ASR 服务

默认情况下，主服务先使用 B 站字幕。

当你希望在“无字幕视频”场景也继续生成总结时，可接入 `asr_service/`。

- ASR 部署文档：`asr_service/README.md`
- 主服务最少配置：`LOCAL_ASR_ENABLED=true`、`LOCAL_ASR_PROVIDER=sensevoice_api`、`ASR_API_URL=http://127.0.0.1:8900/v1/transcribe`

## 配置与文档

- 统一配置入口：`docs/Configuration.md`
- 文档索引：`docs/README.md`
- 飞书卡片模板文件：`docs/博主更新订阅.card`

## 升级提醒

每次升级后，请对照以下示例文件刷新本地配置：

- `env.example`
- `data/feishu_channels.json.example`
- `data/bilibili_creators.json.example`

## 许可证

本项目使用 [MIT License](LICENSE)。
