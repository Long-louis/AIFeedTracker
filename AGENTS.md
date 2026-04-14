# AIFeedTracker Coding Agent Guide

## Project Overview

本项目用于监控 B 站动态，并把结果推送到飞书卡片；对视频动态可选生成 AI 总结并写入飞书知识库。

- 监控与编排入口在 `main.py:203`，统一组装 Feishu、Monitor、AI Summary 服务。
- 动态处理主流程在 `services/monitor.py:212`，包含去重、评论抓取、消息推送、状态持久化。
- 飞书知识库写入是附加能力，不应阻断主推送流程（见 `services/monitor.py:1744`）。

## Tech Stack

- Python 3.11+（asyncio）
- 依赖管理：`uv` + `uv.lock`
- 关键库：`bilibili-api-python`、`aiohttp`、`python-dotenv`、`openai`
- 部署文件：`Dockerfile`、`Dockerfile.gpu`、`deploy/docker-compose*.yml`

## Key Directories and Purposes

- `main.py`：CLI 与服务生命周期（`--mode monitor|service|test`、`--once`、`--reset`）。
- `config.py`：配置中心；import 时加载 `.env`（`config.py:22`），并组装 AI/ASR/飞书知识库配置。
- `services/monitor.py`：核心编排层；读取创作者、拉取动态、调用 AI、写入状态文件。
- `services/feishu.py`：飞书发送实现（app/webhook 双通道）。
- `services/feishu_channels.py`：通道注册表与路由解析（`defaults` + `apps` + `webhooks`）。
- `services/feishu_docs.py`：飞书知识库写入、目录组织与文档更新。
- `services/ai_summary/`：字幕获取、ASR 回退、AI 总结生成。
- `data/`：示例配置与运行时状态。
  - 示例：`data/feishu_channels.json.example`、`data/bilibili_creators.json.example`
  - 运行时：`data/bilibili_state.json`、`data/feishu_doc_state.json`（应保持忽略）
- `tests/`：`unittest` 测试集（含异步测试）。

## Essential Build/Test Commands

初始化依赖：

```bash
uv sync --frozen
```

初始化本地配置：

```bash
cp env.example .env
cp data/feishu_channels.json.example data/feishu_channels.json
cp data/bilibili_creators.json.example data/bilibili_creators.json
```

本地运行（持续服务）：

```bash
uv run python main.py --mode service
```

单次监控检查：

```bash
uv run python main.py --mode monitor --once
```

重置运行状态并单次检查：

```bash
uv run python main.py --mode monitor --reset --once
```

运行测试（必须用 discover）：

```bash
uv run python -m unittest discover -s tests -p "test_*.py" -q
```

## Additional Documentation (Progressive Disclosure)

- `docs/Configuration.md`：统一配置入口（`.env`、飞书通道、创作者、AI 总结、ASR、飞书知识库）
- `docs/README.md`：文档总索引
