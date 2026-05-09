# AIFeedTracker Coding Agent Guide

## Project Overview

本项目监控 B 站动态，并把结果推送到飞书；对视频动态可选生成 AI 总结并写入飞书知识库。

- 编排入口：`main.py:203`，支持 `--mode monitor|service|test`。
- 主流程：`services/monitor.py:212`，状态去重由 `JsonState` 管理：`services/monitor.py:135`。
- 知识库写入是附加能力，失败不应阻断主推送：`services/monitor.py:1765`。

## Tech Stack

- Python 3.11+（asyncio）
- 依赖管理：`uv`（锁文件：`uv.lock`）
- 核心库：`bilibili-api-python`、`aiohttp`、`python-dotenv`、`openai`
- 部署文件：`Dockerfile`、`Dockerfile.gpu`、`deploy/docker-compose.yml`、`deploy/docker-compose.gpu.yml`

## Key Directories and Purposes

- `main.py`：CLI 和服务生命周期（`--mode monitor|service|test`）
- `config.py`：统一配置装配，导入时加载 `.env`：`config.py:22`
- `services/monitor.py`：动态监控编排、去重、消息推送、状态持久化
- `services/feishu.py`：飞书消息发送实现
- `services/feishu_channels.py`：通道注册与路由解析：`services/feishu_channels.py:27`
- `services/feishu_docs.py`：飞书知识库文档写入与更新；DocX block 写入需保持真实文档格式，不能把 Markdown 标记当 raw text 写入
- `services/ai_summary/`：字幕获取、ASR 调用、总结生成
- `asr_service/`：可选的独立 SenseVoice ASR API 服务
- `data/`：只提交 `.example` 和说明；真实配置、登录态、状态文件是本地运行时文件
- `tests/`：`unittest` 测试

## Essential Build/Test Commands

- 初始化依赖：`uv sync --frozen`
- 初始化配置：`cp env.example .env`
- 初始化飞书通道：`cp data/feishu_channels.json.example data/feishu_channels.json`
- 初始化创作者列表：`cp data/bilibili_creators.json.example data/bilibili_creators.json`
- 持续运行：`uv run python main.py --mode service`
- 单次检查：`uv run python main.py --mode monitor --once`
- 重置并单次检查：`uv run python main.py --mode monitor --reset --once`
- 手动测试单个视频总结：`uv run python main.py --mode test --video <URL>`
- 运行测试：`uv run python -m unittest discover -s tests -p "test_*.py" -q`
- 单文件测试：`uv run python -m unittest tests.test_feishu_docs_service -q`

## Repo-Specific Constraints

- 改 Python 依赖用 `uv add` 或 `uv remove`；不要手改 `pyproject.toml` 或 `uv.lock`。
- 本仓库开发和 E2E 共用根目录 `.env`；不要引入第二套开发 dotenv。
- `AI_API_KEY` 缺失时 `AISummaryService` 应直接报错，不要静默禁用总结。
- 飞书通知通道约定：告警走 `webhook:*`，视频内容通知走 `app:*`。
- 飞书知识库文档只保留正文总结内容；写入失败只记录错误，不能影响卡片发送。
- ASR 回退默认通过外部 SenseVoice API：主服务配置 `LOCAL_ASR_PROVIDER=sensevoice_api`、`ASR_API_URL=.../v1/transcribe`。
- `data/bilibili_state.json`、`data/feishu_doc_state.json`、`data/bilibili_auth.json`、`data/bilibili_creators.json`、`data/feishu_channels.json`、`.env` 不应被提交。
- `opencode.jsonc` 和 `.opencode/` 是本机 OpenCode 配置，已忽略；不要作为项目运行时代码提交。
- Docker 镜像内依赖安装走 `uv export` 生成 requirements 的模式，见 `Dockerfile:43` 和 `Dockerfile.gpu:49`。

## Additional Documentation

- `docs/Configuration.md`：统一配置和运行入口
- `docs/architectural_patterns.md`：常见架构模式与约定
- `docs/README.md`：文档索引
- `asr_service/README.md`：独立 SenseVoice ASR 服务部署与 API
