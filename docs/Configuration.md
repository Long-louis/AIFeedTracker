# 配置总入口（Configuration）

## 1) 初始化项目

```bash
uv sync --frozen
cp env.example .env
cp data/feishu_channels.json.example data/feishu_channels.json
cp data/bilibili_creators.json.example data/bilibili_creators.json
```

## 2) `.env` 必填项

### B 站凭证

硬性必填：

- `SESSDATA`

按刷新/兼容场景建议配置：

- `bili_jct`
- `buvid3`
- `DedeUserID`
- `ac_time_value`

可选：`buvid4`、`refresh_token`、`USER_AGENT`。

`ac_time_value` 可在已登录 B 站页面控制台执行 `window.localStorage.ac_time_value` 获取。

### 飞书卡片模板

- `FEISHU_TEMPLATE_ID`
- `FEISHU_TEMPLATE_VERSION`

可直接使用仓库卡片模板文件：`docs/博主更新订阅.card`。

### AI 总结

- `AI_SERVICE`（可选，默认 `deepseek`；支持 `deepseek` / `zhipu` / `qwen`）
- `AI_API_KEY`（必填）

当前运行时会初始化 `AISummaryService`；未设置 `AI_API_KEY` 时会初始化失败并导致启动报错。

## 3) 飞书消息通道配置（`data/feishu_channels.json`）

支持两类通道：

- `app:<name>`（推荐）
- `webhook:<name>`

示例默认走应用通道：

- `defaults.content = app:default`
- `defaults.alert = app:alerts`

`apps.<name>` 关键字段：

- `app_id`
- `app_secret`
- `receive_id_type`（`chat_id` / `open_id` / `user_id` / `union_id` / `email`）
- `receive_id`

如果从旧版本升级，请按示例文件刷新本地配置；旧字段 `user_open_id` 不再使用。

## 4) 监控对象配置（`data/bilibili_creators.json`）

每个条目至少包含：

- `uid`
- `name`

`crons` 为可选；未配置时回退为 `check_interval` 间隔轮询模式（默认 300 秒）。

可选：`feishu_channel`，用于按博主覆盖默认通道（支持 `app:*` / `webhook:*`）。

## 5) AI 总结与 ASR 回退（SenseVoice API）

视频总结固定输出两个模块：

- `## 关键信息和观点`
- `## 时间线总结`

ASR 回退为可选能力，主应用通过 HTTP 调用外部 SenseVoice API 服务：

- `LOCAL_ASR_ENABLED=false`：关闭
- `LOCAL_ASR_ENABLED=true`：在字幕缺失时启用回退
- `LOCAL_ASR_PROVIDER=sensevoice_api`
- `ASR_API_URL`：SenseVoice API 地址（例如 `http://127.0.0.1:8900/v1/transcribe`）
- `ASR_API_TIMEOUT_SECONDS`：ASR 请求超时秒数

主应用容器路径：`deploy/docker-compose.yml` / `deploy/docker-compose.gpu.yml`

ASR 服务容器路径：`asr_service/deploy/docker-compose.yml`

若 ASR 服务使用 GPU 推理，宿主机需先安装 NVIDIA Container Toolkit。

## 6) 飞书知识库写入（可选）

开启项：

- `FEISHU_DOCS_ENABLED=true`
- `FEISHU_DOCS_APP_ID`
- `FEISHU_DOCS_APP_SECRET`
- `FEISHU_DOCS_WIKI_SPACE_ID`

可选：`FEISHU_DOCS_ROOT_NODE_TOKEN`、`FEISHU_DOCS_ROOT_TITLE`、`FEISHU_DOCS_STATE_PATH`。

知识库目录结构：`根 -> 博主 -> YYYY-MM -> 视频文档`。

说明：

- 文档写入失败不会阻断飞书消息发送。
- 写入成功时，会在消息 `AI 总结` 末尾追加知识库链接。
- 开通 `docx:document.block:convert` 可将 Markdown 转为带样式文档块；未开通会回退为纯文本块。

## 7) 运行与排查

单次验证：

```bash
uv run python main.py --mode monitor --once
```

持续运行：

```bash
uv run python main.py --mode service
```

若出现登录失效，服务会尝试刷新凭证，必要时触发二维码登录。

## 8) 升级配置刷新

当 `env.example` 或 `data/*.json.example` 结构变化时，请手动同步本地：

- `.env`
- `data/feishu_channels.json`
- `data/bilibili_creators.json`

## 9) 架构模式速览（便于二次开发）

- 编排层与能力层分离：`main.py:203`、`services/monitor.py:212`
- 配置集中构建并在 import 时加载：`config.py:22`
- 注册表驱动通道路由：`services/feishu_channels.py:27`
- 状态文件保证幂等：`services/monitor.py:135`、`services/feishu_docs.py:427`
- 次级输出非阻断：`services/monitor.py:1744`
- 失败时自动降级（如文档块转换失败回退纯文本）：`services/feishu_docs.py:237`
