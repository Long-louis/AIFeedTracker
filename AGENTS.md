# AIFeedTracker（AI Feed Tracker）— Coding Agent 上手指南

## 这是什么仓库

本项目是一个 **B 站动态监控 + 飞书卡片推送 +（可选）AI 视频总结** 的机器人服务：

- 定期拉取指定 UP 的动态（视频/图文等），做去重与状态记录
- 将动态内容以「飞书模板卡片」推送到群或应用通道
- 对视频动态可抽取字幕并调用 OpenAI 兼容接口生成结构化摘要
- 支持 B 站 Cookie/凭证刷新相关工具与 Docker 部署

## 技术栈 / 运行时

- 语言：Python（异步 asyncio）
- 运行时：Python 3.11+（本地已验证可用）
- 依赖管理：`uv`（推荐，仓库有 `uv.lock`）
- 关键依赖：
	- `bilibili-api-python`（动态/评论/凭证）
	- `aiohttp`（HTTP）
	- `python-dotenv`（读取 `.env`）
	- `openai`（兼容 DeepSeek/智谱/通义等 OpenAI 接口）

## 重要约束（减少返工）

- **B 站相关实现**：优先参考 `bilibili-api-python` 文档（需要查询时请用 deepwiki）。
- **敏感信息**：`.env` 不进 Git；运行时状态文件位于 `data/` 且应保持在 `.gitignore`。
- **配置读取时机**：`config.py` 在 import 时读取 `.env`；测试里若修改环境变量，通常需要 reload 模块（见现有单测）。

## 项目结构（找代码别到处 grep）

- 入口：`main.py`
	- CLI：`--mode monitor|service|test`，以及 `--once`、`--reset`
	- 组合服务：`FeishuBot`、`AISummaryService`、`MonitorService`
- 配置：`config.py`
	- 读取 `.env`（如存在）
	- 飞书模板与通道注册表路径、B 站凭证、AI 配置等
- 动态监控：`services/monitor.py`
	- `MonitorService`：拉动态、去重、推送、写入 `data/bilibili_state.json`
	- 订阅列表：`data/bilibili_creators.json`（从 `.example` 复制）
- 飞书推送：`services/feishu.py` + `services/feishu_channels.py`
	- registry-driven：`data/feishu_channels.json`（从 `.example` 复制）
	- 内容推送 vs 告警推送的默认路由在 registry 的 `defaults` 中
- 评论获取：`services/comment_fetcher.py`
- AI 总结：`services/ai_summary/`（字幕抓取、生成器、客户端等）
- B 站认证/刷新：`services/bilibili_auth.py` 与 `tools/` 下脚本
- 部署：`deploy/docker-compose.yml`、`Dockerfile`、`scripts/*.sh`
- 测试：`tests/`（unittest / IsolatedAsyncioTestCase）

## 配置文件（必看）

本地开发通常需要：

1) 复制并填写 `.env`

```bash
cp env.example .env
```

2) 复制业务配置

```bash
cp data/feishu_channels.json.example data/feishu_channels.json
cp data/bilibili_creators.json.example data/bilibili_creators.json
```

说明：

- 飞书模板：`.env` 里 `FEISHU_TEMPLATE_ID`、`FEISHU_TEMPLATE_VERSION`
- 飞书通道注册表：默认 `data/feishu_channels.json`（可用 `FEISHU_CHANNELS_CONFIG` 覆盖）
- B 站凭证：`.env` 里 `SESSDATA` 等（详见 `docs/BILIBILI_SETUP.md`）
- AI：`.env` 里 `AI_SERVICE`、`AI_API_KEY`（详见 `docs/AI_SUMMARY_SETUP.md`）

## 安装 / 构建 / 运行（已验证命令）

### 依赖安装（bootstrap）

前置：确保安装 `uv`。

已在 macOS 上验证：`uv 0.7.2` 可用。

```bash
uv sync --frozen
```

说明：

- 仓库使用 `uv.lock` 锁定依赖；**优先使用 `--frozen`** 保持一致性。

### 本地运行（run）

持续服务模式：

```bash
uv run python main.py --mode service
```

单次检查（调试用）：

```bash
uv run python main.py --mode monitor --once
```

重置运行时状态（会备份并清空 `data/bilibili_state.json`）：

```bash
uv run python main.py --mode monitor --reset --once
```

### 测试（test）

本仓库使用 `unittest`，**必须用 discover** 才能发现 `tests/` 下用例：

```bash
uv run python -m unittest discover -s tests -p "test_*.py" -q
```

已验证：该命令会运行 7 个测试并通过。

注意：直接运行 `uv run python -m unittest -q` 会出现 “Ran 0 tests”。

### Lint / Format

仓库当前未内置 ruff/black/flake8 配置与命令。变更时请尽量遵循现有代码风格，并优先添加/更新单测来防回归。

## Docker/服务器部署（可选）

- Dockerfile：两阶段构建，镜像内自带 `.venv`，默认命令 `python main.py --mode service`
- Compose：`deploy/docker-compose.yml`
	- 运行时环境变量来自 `deploy/.env`（从 `deploy/.env.example` 复制）
	- `../data`、`../log` 挂载到容器 `/app/data`、`/app/log`

仓库提供脚本：

- `scripts/deploy.sh`：`scp` 同步本地 `.env` → 服务器 `deploy/.env`，然后远端 `git pull` + `docker compose up`
- `scripts/commit-and-deploy.sh`：`git add/commit/push` 后调用 `deploy.sh`

注意：脚本内服务器别名默认为 `huaweicloud`，并假设部署目录 `/opt/aifeedtracker`；本地机器已配置免密登录该服务器。当前已经完成初次部署，使用deploy.sh脚本进行compose的重新运行。

## CI/校验流水线

- `.github/workflows/` 当前为空（未发现 GitHub Actions）。
- 提交前建议至少跑：
	- `uv sync --frozen`
	- `uv run python -m unittest discover -s tests -p "test_*.py" -q`

## 常改动区域（按需求快速定位）

- B 站动态/去重/状态：`services/monitor.py`，状态文件 `data/bilibili_state.json`
- 飞书卡片与路由：`services/feishu.py`、`services/feishu_channels.py`
- 评论：`services/comment_fetcher.py`
- AI 总结：`services/ai_summary/`
- Cookie/凭证刷新与工具：`services/bilibili_auth.py`、`tools/*.py`

## 文档入口（遇到配置/概念问题先看这里）

- 总览：`README.md`、`docs/README.md`
- 飞书：`docs/FEISHU_CARD_SETUP.md`
- B 站凭证：`docs/BILIBILI_SETUP.md`
- AI 总结：`docs/AI_SUMMARY_SETUP.md`
- 部署：`docs/DEPLOY_AUTOMATION.md`

---

请优先信任本文件中的路径与命令；仅当信息缺失或与仓库现状不符时，再进行搜索与探索。