# AI 视频机器人

![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

一个智能飞书机器人，支持视频总结、B 站动态监控和消息推送功能。

## 🌟 功能特性

### 1. 视频 AI 总结

- 自动获取 B 站视频字幕
- 调用国内 AI 服务（DeepSeek、智谱 AI、通义千问等）生成总结
- 支持 OpenAI 兼容接口，配置灵活
- 生成结构化 Markdown 格式总结

### 2. B 站动态监控

- 监控指定 B 站博主的最新动态
- 自动推送到飞书群聊
- Cookie 自动刷新机制

### 3. 飞书消息推送

- 发送富文本卡片消息
- 支持 Markdown 格式
- 图片自动上传和转换

## 🚀 快速开始

### 环境要求

- Python 3.10+
- uv (Python 包管理器)

### 安装

```bash
# 克隆项目
git clone <repository_url>
cd ai_video_robot

# 使用 uv 安装依赖
uv sync
```

### 配置

1. 复制 `env.example` 为 `.env`
2. 配置飞书应用信息：

   ```env
   app_id=你的飞书应用ID
   app_secret=你的飞书应用密钥
   ```

3. **配置飞书卡片模板（必需）**：

   项目提供了现成的卡片模板文件 `docs/博主更新订阅.card`，只需导入即可：

   - 在飞书开放平台的「消息卡片」→「卡片搭建工具」中导入 `docs/博主更新订阅.card`
   - 发布后获取 `template_id` 和 `template_version_name`
   - 更新 `config.py` 中的配置

   详细步骤请查看 [飞书卡片配置指南](./docs/FEISHU_CARD_SETUP.md)

4. **配置 AI 服务（必需）**：

   ```env
   AI_SERVICE=deepseek  # 可选: deepseek, zhipu, qwen
   AI_API_KEY=你的API密钥
   ```

   详细配置请参考 [AI 总结服务配置指南](./docs/AI_SUMMARY_SETUP.md)

5. **配置监控博主列表（必需）**：

   ```bash
   # 复制示例文件
   cp data/bilibili_creators.json.example data/bilibili_creators.json

   # 编辑文件，添加您要监控的博主UID
   # 详见: data/README.md
   ```

   **注意**：`bilibili_state.json` 文件会在首次运行时自动创建，无需手动配置

6. 配置 B 站 Cookie（可选，用于动态监控）：

   ```bash
   # 配置 refresh_token 和 User-Agent
   uv run python tools/manual_set_refresh_token.py
   uv run python tools/check_browser_info.py
   ```

   详细步骤请参考 [B 站配置指南](./docs/BILIBILI_SETUP.md)

### 运行

#### 方式一：直接运行（开发/测试）

```bash
# 启动监控服务（持续运行）
uv run python main.py --mode service

# 启动监控服务（普通模式）
uv run python main.py --mode monitor

# 单次监控（测试用）
uv run python main.py --mode monitor --once

# 手动总结视频
uv run python main.py --mode test --video <视频链接>
```

#### 方式二：Windows 服务（生产环境，推荐）

**优点：** 开机自启、后台运行、自动重启、系统级管理

**1. 安装服务**

以**管理员身份**运行：

```bash
install_service.bat
```

**2. 管理服务**

命令行方式（管理员权限）：

```bash
# 启动服务
net start AIVideoRobot

# 停止服务
net stop AIVideoRobot

# 重启服务（代码更新后需要重启）
net stop AIVideoRobot && net start AIVideoRobot
```

图形界面方式：

1. 按 `Win + R`，输入 `services.msc`
2. 找到 "AI Video Robot Monitor Service"
3. 右键 → 启动/停止/重启

**3. 查看日志**

服务运行日志：

- `log/service_stdout.log` - 标准输出
- `log/service_stderr.log` - 错误输出
- `log/app.log` - 应用日志（详细）

**4. 卸载服务**

以管理员身份运行：

```bash
uninstall_service.bat
```

#### 方式三：后台运行（临时测试）

```bash
# 使用 BAT 脚本快速启动（最小化窗口）
run_background.bat
```

#### 方式四：Docker

```bash
# 生成你的配置文件
cp env.example myenv.txt

# 编辑 myenv.txt

# 生成你的监控博主信息文件
cp data/bilibili_creators.json.example bilibili_creators.json

# 编辑 bilibili_creators.json

# 复制配置文件到任意位置 (替换{my-config-path}为实际路径)
cp myenv.txt {my-config-path}/myenv.txt
cp bilibili_creators.json {my-config-path}/bilibili_creators.json

# 使用 Docker 运行
## 自行构建 Docker 镜像运行 (替换{my-config-path}为实际路径)
docker build -t ai-feed-tracker .
docker run -d \
  --name ai-feed-tracker \
  --restart=unless-stopped \
  --env-file {my-config-path}/myenv.txt \
  -v {my-config-path}/bilibili_creators.json:/app/data/bilibili_creators.json \
  ai-feed-tracker:latest
  
## 使用我提供的 Docker 镜像运行 (替换{my-config-path}为实际路径)
docker run -d \
  --name ai-feed-tracker \
  --restart=unless-stopped \
  --env-file {my-config-path}/myenv.txt \
  -v {my-config-path}/bilibili_creators.json:/app/data/bilibili_creators.json \
  -e TZ=Asia/Shanghai \
  hup2c/ai-feed-tracker:latest

## 查看日志
docker logs -f ai-feed-tracker
```

## 📚 文档

完整文档请查看 [docs/](./docs/) 目录：

- [飞书卡片配置指南](./docs/FEISHU_CARD_SETUP.md) - 创建飞书消息卡片模板
- [AI 总结服务配置指南](./docs/AI_SUMMARY_SETUP.md) - AI 服务配置和使用说明
- [快速开始指南](./docs/QUICK_START.md) - 5 分钟快速上手
- [B 站配置指南](./docs/BILIBILI_SETUP.md) - Cookie 配置和自动刷新

## 🧪 测试

```bash
# 测试 AI 总结服务
uv run python tests/test_ai_summary.py

# 测试 B 站 API 连接
uv run python tests/test_api.py

# 测试 refresh_token 功能
uv run python tests/test_refresh_token_auto.py
```

## 📁 项目结构

```
ai_video_robot/
├── main.py                 # 主入口
├── config.py               # 配置管理
├── core/                   # 核心模块
│   └── logging_config.py   # 日志配置
├── services/               # 业务服务
│   ├── ai_summary/        # AI总结服务
│   │   ├── subtitle_fetcher.py    # 字幕获取
│   │   ├── ai_client.py           # AI客户端
│   │   ├── summary_generator.py   # 总结生成
│   │   └── service.py             # 服务主接口
│   ├── bilibili_auth.py   # B站认证
│   ├── feishu.py          # 飞书服务
│   └── monitor.py         # 监控服务
├── tools/                  # 工具脚本
│   ├── manual_set_refresh_token.py  # 手动设置token
│   └── check_browser_info.py        # 浏览器信息检测
├── tests/                  # 测试文件
│   └── test_ai_summary.py           # AI总结测试
├── docs/                   # 文档目录
│   └── AI_SUMMARY_SETUP.md          # AI配置指南
└── data/                   # 数据存储
```

## ⚙️ 核心功能说明

### AI 视频总结

- 从 B 站自动获取 AI 生成的中文字幕
- 支持多个国内 AI 服务（DeepSeek、智谱 AI、通义千问）
- 使用精心设计的提示词生成结构化总结
- 总结包含核心观点、关键亮点和详细内容
- 费用极低（DeepSeek 单视频< ¥0.01）

### Cookie 自动刷新

- 使用 `refresh_token` 机制自动刷新 B 站 Cookie
- 每小时检查一次 Cookie 状态
- Cookie 即将过期时自动刷新
- 无需人工干预

### 动态监控

- 定时检查指定博主的最新动态
- 支持视频、文字、转发等多种类型
- 自动去重，避免重复推送
- 视频动态自动生成 AI 总结

## 常见问题

### Q: B 站 API 返回 -352 错误？

**A**: Cookie 无效或过期，参考 [B 站配置指南](./docs/BILIBILI_SETUP.md) 重新配置。

### Q: 如何获取 refresh_token？

**A**: 从浏览器 Console 执行 `localStorage.getItem('ac_time_value')`，详见配置指南。

### Q: 如何验证配置？

**A**: 运行测试：`uv run python tests/test_api.py`

### Q: Windows 服务安装后无法启动？

**A**: 检查以下几点：

1. 确认以管理员身份运行 `install_service.bat`
2. 检查虚拟环境是否正确：`E:\ai_video_robot\.venv\Scripts\python.exe`
3. 查看错误日志：`log/service_stderr.log`
4. 手动测试运行：`uv run python main.py --mode service`

### Q: 服务显示乱码？

**A**: 已使用英文描述避免编码问题。重新运行 `uninstall_service.bat` 后再运行 `install_service.bat` 即可。

### Q: 如何更新代码后重启服务？

**A**: Windows 服务不会自动重新加载代码，需要手动重启：

```bash
# 方法1: 命令行重启（管理员权限）
net stop AIVideoRobot && net start AIVideoRobot

# 方法2: 使用重启脚本
restart_service.bat

# 方法3: 图形界面
# 按 Win+R → services.msc → 找到服务 → 右键重启
```

**重要**: 每次修改 Python 代码后都必须重启服务才能生效！

### Q: 开发时是否应该使用服务模式？

**A**:

- **开发调试**：建议用 `uv run python main.py --mode test`（看到实时输出）
- **测试运行**：可用 `run_background.bat`（最小化窗口）
- **生产环境**：使用 Windows 服务（稳定可靠，自动重启）

## 📝 技术栈

- **异步编程**: asyncio + aiohttp
- **AI 服务**: OpenAI SDK（兼容国内服务）
- **B 站 API**: bilibili-api-python
- **数据存储**: JSON 文件
- **消息推送**: 飞书开放平台 SDK
- **日志**: Python logging

## 🤝 贡献

我们欢迎各种形式的贡献！

- 🐛 报告 Bug
- 💡 提出新功能建议
- 📝 改进文档
- 🔧 提交代码修复

请查看 [CONTRIBUTING.md](./CONTRIBUTING.md) 了解详细的贡献指南。

## ⚠️ 免责声明

本项目仅供学习和个人使用。请遵守相关平台的服务条款和使用政策。

## 📄 许可证

本项目采用 [MIT License](./LICENSE) 开源协议。

## 🙏 致谢

感谢以下开源项目：

- [bilibili-api-python](https://github.com/Nemo2011/bilibili-api) - B 站 API 封装
- [OpenAI Python SDK](https://github.com/openai/openai-python) - AI 服务调用
