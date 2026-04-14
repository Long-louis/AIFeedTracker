# AIFeedTracker Coding Agent Guide

## Project Overview

本项目监控 B 站动态，并把结果推送到飞书；对视频动态可选生成 AI 总结并写入飞书知识库。

- 编排入口：`main.py:203`
- 主流程：`services/monitor.py:212`
- 知识库写入是附加能力，失败不应阻断主推送：`services/monitor.py:1744`

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
- `services/feishu_docs.py`：飞书知识库文档写入与更新
- `services/ai_summary/`：字幕获取、ASR 调用、总结生成
- `asr_service/`：可选的独立 SenseVoice ASR API 服务
- `data/`：示例配置与运行时状态（运行时状态文件应保持忽略）
- `tests/`：`unittest` 测试

## Essential Build/Test Commands

- 初始化依赖：`uv sync --frozen`
- 初始化配置：`cp env.example .env`
- 初始化飞书通道：`cp data/feishu_channels.json.example data/feishu_channels.json`
- 初始化创作者列表：`cp data/bilibili_creators.json.example data/bilibili_creators.json`
- 持续运行：`uv run python main.py --mode service`
- 单次检查：`uv run python main.py --mode monitor --once`
- 重置并单次检查：`uv run python main.py --mode monitor --reset --once`
- 运行测试：`uv run python -m unittest discover -s tests -p "test_*.py" -q`

## Additional Documentation

- `docs/Configuration.md`：统一配置和运行入口
- `docs/architectural_patterns.md`：常见架构模式与约定
- `docs/README.md`：文档索引
