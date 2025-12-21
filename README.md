# AI Feed Tracker

![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

一个智能视频监控与 AI 总结机器人，支持 B 站动态监控并自动推送到飞书。

## 🌟 功能特性

- **B 站动态监控**：实时监控博主动态，支持视频、图文等多种类型。
- **AI 视频总结**：自动提取视频字幕并生成结构化摘要（支持 DeepSeek, Qwen, Zhipu 等）。
- **飞书集成**：通过富文本卡片推送精美消息，支持多通道路由。
- **自动维护**：Cookie 自动刷新机制，确保服务长期稳定。

## 🚀 快速开始

### 1. 环境准备
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (推荐的包管理器)

### 2. 安装与配置
```bash
# 克隆项目
git clone <repository_url>
cd AIFeedTracker

# 安装依赖
uv sync

# 配置文件
cp env.example .env
cp data/feishu_channels.json.example data/feishu_channels.json
cp data/bilibili_creators.json.example data/bilibili_creators.json
```

### 3. 运行
```bash
# 启动监控服务
uv run python main.py --mode service
```

## 📖 详细文档

请参考 [docs/README.md](docs/README.md) 获取完整配置指南：

- [飞书卡片配置](docs/FEISHU_CARD_SETUP.md)
- [AI 总结服务配置](docs/AI_SUMMARY_SETUP.md)
- [B 站 Cookie 配置](docs/BILIBILI_SETUP.md)
- [自动化部署指南](docs/DEPLOY_AUTOMATION.md)

## 🛠️ 部署

- **Windows**: 支持作为系统服务运行，使用 `install_service.bat` 进行安装。
- **Linux/Docker**: 推荐使用 Docker 部署，支持一键脚本自动化更新，详见 [部署文档](docs/DEPLOY_AUTOMATION.md)。

## 📄 许可证

本项目采用 [MIT License](LICENSE) 开源协议。
