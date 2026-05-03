# 架构模式与约定

这份文档记录项目里反复出现的设计模式，帮助你在新增功能时保持一致。

## 1) 编排层与能力层分离

- 启动和依赖组装在编排层：`main.py:203`
- 业务流程在监控服务：`services/monitor.py:212`
- 具体能力由独立服务实现（飞书、知识库、AI、ASR 客户端）

## 2) 主流程优先，次级输出不阻断

- 动态通知是主流程
- 飞书知识库写入是附加能力，失败不能影响主通知：`services/monitor.py:1744`

## 3) 注册表驱动通道路由

- 通道定义集中在配置文件
- 运行时通过注册表解析并路由到 app/webhook：`services/feishu_channels.py:27`

## 4) 状态文件保证幂等

- 监控状态：`data/bilibili_state.json`，实现去重与断点续跑：`services/monitor.py:135`
- 文档状态：`data/feishu_doc_state.json`，避免重复写文档：`services/feishu_docs.py:427`

## 5) 外部 ASR 采用 API 集成

- 主服务通过 HTTP 调用 ASR，不在主进程内运行模型
- 主流程入口：`services/ai_summary/audio_transcription_service.py:13`
- 客户端实现：`services/ai_summary/sensevoice_client.py:10`

## 6) 凭证刷新后必须持久化

- 运行时刷新成功后，必须回写到 `data/bilibili_auth.json`
- 这样重启后才能复用最新登录态，避免重复扫码：`services/monitor.py:324`
