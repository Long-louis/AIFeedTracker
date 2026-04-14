# 配置总入口（Configuration）

这份文档只做一件事：帮你把项目跑起来。

## 1) 先初始化

```bash
uv sync --frozen
cp env.example .env
cp data/feishu_channels.json.example data/feishu_channels.json
cp data/bilibili_creators.json.example data/bilibili_creators.json
```

本仓库开发和 E2E 使用同一个根目录 `.env`，不需要拆成多个 dotenv 文件。

## 2) `.env` 里最重要的字段

### B 站登录

- 必填：`SESSDATA`
- 强烈建议：`bili_jct`、`buvid3`、`DedeUserID`、`ac_time_value`

`ac_time_value` 可在已登录 B 站页面控制台执行 `window.localStorage.ac_time_value` 获取。

### 飞书卡片

- `FEISHU_TEMPLATE_ID`
- `FEISHU_TEMPLATE_VERSION`

卡片模板文件在：`docs/博主更新订阅.card`。

### AI 总结

- `AI_API_KEY`（必填）
- `AI_SERVICE`（可选，默认 `deepseek`）

注意：`AI_API_KEY` 缺失时，`AISummaryService` 会直接报错，不会静默跳过。

## 3) `data/` 里的两个配置文件

### `data/feishu_channels.json`

- 推荐使用 `app:*` 通道
- 也支持 `webhook:*`
- 示例默认：`defaults.content = app:default`，`defaults.alert = app:alerts`

`apps.<name>` 里最关键的字段：`app_id`、`app_secret`、`receive_id_type`、`receive_id`。

### `data/bilibili_creators.json`

每个 UP 至少要有：

- `uid`
- `name`

可选字段：`crons`、`check_interval`、`feishu_channel`。

## 4) 可选能力 A：ASR 回退（高级）

默认流程先用 B 站字幕。

如果你想在“无字幕视频”场景继续生成总结，再开启 ASR 回退：

- `LOCAL_ASR_ENABLED=true`
- `LOCAL_ASR_PROVIDER=sensevoice_api`
- `ASR_API_URL=http://127.0.0.1:8900/v1/transcribe`
- `ASR_API_TIMEOUT_SECONDS=300`

主服务通过 HTTP 调用外部 ASR，不在主进程内跑 Whisper。

- 主服务 Docker：`deploy/docker-compose.yml`、`deploy/docker-compose.gpu.yml`
- ASR 服务 Docker：`asr_service/deploy/docker-compose.yml`
- ASR 详细部署：`asr_service/README.md`

## 5) 可选能力 B：飞书知识库写入

开启所需字段：

- `FEISHU_DOCS_ENABLED=true`
- `FEISHU_DOCS_APP_ID`
- `FEISHU_DOCS_APP_SECRET`
- `FEISHU_DOCS_WIKI_SPACE_ID`

目录结构是：`根 -> 博主 -> YYYY-MM -> 视频文档`。

关键行为：

- 写入失败不阻断消息推送
- 写入成功后，会在消息 `AI 总结` 末尾追加知识库链接
- 开通 `docx:document.block:convert` 后，Markdown 会转成带样式的文档块

## 6) 常用运行命令

- 持续运行：`uv run python main.py --mode service`
- 单次检查：`uv run python main.py --mode monitor --once`
- 重置状态并单次检查：`uv run python main.py --mode monitor --reset --once`
- 全量测试：`uv run python -m unittest discover -s tests -p "test_*.py" -q`

## 7) 升级时要做的事

每次升级后，请对照示例文件刷新本地配置：

- `env.example`
- `data/feishu_channels.json.example`
- `data/bilibili_creators.json.example`

## 8) 二次开发建议阅读

- 架构模式：`docs/architectural_patterns.md`
- 文档索引：`docs/README.md`
