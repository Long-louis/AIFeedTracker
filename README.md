# AI Feed Tracker

![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

一个用于监控 B 站动态、推送飞书卡片，并可选生成 AI 视频总结的机器人服务。

## 功能概览

- B 站动态监控，支持视频、图文、文字、直播等常见动态类型
- 飞书模板卡片推送，支持多通道路由
- 可选 AI 视频总结能力
- 可选本地 ASR 回退：当视频字幕缺失时，可启用 `faster_whisper` 作为本地转写回退；`LOCAL_ASR_ENABLED=false` 可完全禁用，`LOCAL_ASR_DEVICE=cpu` 适用于无 GPU 环境
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

## 配置说明

- B 站凭证配置：`docs/BILIBILI_SETUP.md`
- 飞书卡片模板与通道配置：`docs/FEISHU_CARD_SETUP.md`
- AI 总结配置：`docs/AI_SUMMARY_SETUP.md`

## 升级提醒

升级到新版本后，请同步检查 `.env` 与 `data/*.json` 配置文件是否仍与最新示例文件一致；如示例文件结构有变化，请手动更新你的本地配置文件。

## 许可证

本项目采用 [MIT License](LICENSE) 开源协议。
