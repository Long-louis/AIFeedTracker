# AIFeedTracker Coding Agent Guide

## Project Overview

监控 B 站动态并推送飞书；对视频动态可选生成 AI 总结并写入飞书知识库。

- CLI 与服务生命周期：`main.py:203`，支持 `--mode monitor|service|test`。
- 监控编排：`MonitorService`（`services/monitor.py:267`），状态去重 `JsonState`（`services/monitor.py:146`）。
- 知识库写入是附加能力，失败只记录、不阻断卡片发送：`services/monitor.py:2075`（`_process_video_dynamic`）。

## 监控架构（两种模式，由 `FEED_MODE` 决定）

- `aggregated`（默认，推荐）：单轮询器调聚合接口 `/feed/all`（`fetch_aggregated_feed` `services/monitor.py:1623`），**一次请求拉全部关注博主动态**，按 UID 过滤后复用 `_process_dynamic_item` 派发。调用数与博主数解耦。
- `legacy`：逐博主 cron 轮询个人空间接口 `/feed/space`（风控更严，社区 issue #1012 明确推荐多 UID 用聚合流）。
- 轮询周期纯按时间窗口：盘中快（~300s）/ 收盘正常 / 深夜静默，并叠加 ±25% 随机抖动降风控：`compute_poll_interval` `services/monitor.py:1873`。
- 聚合流分页：`process_aggregated_feed` 翻页直到关注博主新动态收齐（`feed_max_pages` 上限），避免被非关注动态挤出首页漏检。
- 全局限流器 `services/bilibili_rate_limiter.py`：令牌桶 + 并发信号量 + 风控码(-352/-101/-403/412)退避 + 熔断，覆盖聚合流/空间流/评论接口。

- 评论轮询已解耦为独立慢循环（`_comment_poll_loop`），仅针对 `enable_comments` 博主按自身节奏单独拉动态+轮询，与聚合流动态检测互不影响（聚合流单页可能不含该博主完整动态）。

## Tech Stack

- Python 3.11+（asyncio）；依赖管理 `uv`（锁文件 `uv.lock`）
- 核心库：`bilibili-api-python`、`aiohttp`、`python-dotenv`、`openai`
- 部署：`Dockerfile`、`Dockerfile.gpu`、`deploy/docker-compose*.yml`

## Key Directories

- `config.py`：统一配置装配，导入即加载 `.env`（`config.py:14`）
- `services/monitor.py`：监控编排、去重、推送、状态持久化
- `services/bilibili_rate_limiter.py`：B 站 API 全局限流/退避/熔断
- `services/feishu.py` / `services/feishu_channels.py:27`：飞书发送与通道路由
- `services/feishu_docs.py`：飞书知识库 DocX 写入（须保持真实文档格式，禁把 Markdown 标记当 raw text 写）
- `services/comment_fetcher.py`：评论获取，3 处调用经限流器 `_guarded_get_comments`
- `services/ai_summary/`：字幕获取、ASR、总结生成
- `asr_service/`：可选独立 SenseVoice ASR API 服务
- `data/`：只提交 `.example`；真实配置/登录态/状态文件是本地运行时文件

## Essential Commands

- 初始化：`uv sync --frozen`；`cp env.example .env`；`cp data/feishu_channels.json.example data/feishu_channels.json`；`cp data/bilibili_creators.json.example data/bilibili_creators.json`
- 持续运行：`uv run python main.py --mode service`
- 单次检查：`uv run python main.py --mode monitor --once`
- 重置并补发：`uv run python main.py --mode monitor --reset --once`
- 测单视频总结：`uv run python main.py --mode test --video <URL>`
- 测试：`uv run python -m unittest discover -s tests -p "test_*.py" -q`（注意 plain `unittest -q` 发现不到本仓库测试套件）
- 单文件测试：`uv run python -m unittest tests.test_feishu_docs_service -q`

## 部署流程（dev 是唯一代码源，prod 只读）

- 开发库 `/home/long/AIFeedTracker-private` 是单一源；生产 `/opt/aifeedtracker` 是经由本地 bare repo `/opt/aifeedtracker.git` 的 `post-receive` hook 自动部署的只读检出。
- 部署：dev 内 `git push prod-local HEAD:main` → hook 自动 `checkout` + `uv sync --frozen --no-dev` + `systemctl restart aifeedtracker.service`。
- 回滚到指定 commit：`git push prod-local +<commit>:main`（向后是非快进，用 `+`，仍走 hook）。
- 禁止 `rsync`/`cp`/`git pull`/`git reset --hard`/直接改 `/opt` 代码部署——一律走 `prod-local` push。
- prod 的运行时文件（`.env`、`data/*.json`、`data/models/`、`temp/`）未跟踪，部署 checkout 不动它们，须保留。
- 生产若 dirty（tracked 文件改动）必须先分类处理再部署；hook 会拒绝 dirty 部署。

## Repo-Specific Constraints

- 改依赖用 `uv add`/`uv remove`，不要手改 `pyproject.toml` 或 `uv.lock`；`uv.lock` 冲突用 `uv lock` 重生成。
- 开发与 E2E 共用根目录 `.env`，不要引入第二套 dotenv。
- `AI_API_KEY` 缺失时 `AISummaryService` 直接报错，不要静默禁用总结。
- 飞书通道约定：告警 `webhook:*`，视频内容通知 `app:*`。
- 飞书知识库文档只保留正文总结；DocX block 写入保持真实格式。
- ASR 回退默认外部 SenseVoice API：`LOCAL_ASR_PROVIDER=sensevoice_api`、`ASR_API_URL=.../v1/transcribe`。
- 不提交：`data/bilibili_state.json`、`data/feishu_doc_state.json`、`data/bilibili_auth.json`、`data/bilibili_creators.json`、`data/feishu_channels.json`、`.env`。
- `opencode.jsonc` 和 `.opencode/` 是本机 OpenCode 配置（已忽略），不作运行时代码提交。
- Docker 镜像依赖安装走 `uv export` 生成 requirements：`Dockerfile:44`、`Dockerfile.gpu:50`。
- 热重载：`services/monitor.py` 用 `ConfigFileWatcher` 每 10 秒热重载 `data/bilibili_creators.json`。

## Additional Documentation

- `docs/Configuration.md`：统一配置和运行入口
- `docs/monitor_aggregated_feed.md`：监控聚合流改造实现文档（档位 A/C + 分层延迟）
- `docs/architectural_patterns.md`：架构模式与约定
- `docs/README.md`：文档索引
- `asr_service/README.md`：独立 SenseVoice ASR 服务
