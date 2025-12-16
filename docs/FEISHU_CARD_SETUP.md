# 飞书卡片模板与 Webhook 配置指南

本项目使用 **飞书群自定义机器人 Webhook（V2）** 推送模板卡片消息。

核心原则：
- **Webhook-only**（不使用飞书应用机器人），避免配置复杂和权限/用户 open_id 依赖
- **通道注册表**（channels registry）集中管理多个 webhook 和默认路由

你只需要：
1) 在飞书卡片搭建工具里创建/导入模板卡片，拿到 `template_id` 和 `template_version_name`
2) 在飞书群里创建自定义机器人，拿到 webhook url（以及可选的 secret）
3) 填写 `data/feishu_channels.json` 并在 `.env` 里配置模板信息

> 可选：如果你想使用飞书应用机器人（例如发送到指定 open_id 的用户），可以在 `data/feishu_channels.json` 中添加 `apps` 节点并在 `defaults` 中使用 `app:<name>` 或在某个 UP 的 `feishu_channel` 中使用 `app:<name>`。应用模式会在需要时懒加载 `lark-oapi`，并仅在配置完整时启用。

## 快速创建卡片模板

### 方式一：使用项目提供的卡片文件（推荐）

项目已提供现成的卡片模板文件：`docs/博主更新订阅.card`

#### 步骤：

1. **访问飞书开放平台**
   
   打开 [飞书开放平台](https://open.feishu.cn/)，进入您的应用管理页面

2. **进入消息卡片功能**
   
   在应用详情页，找到「消息卡片」→「卡片搭建工具」

3. **导入卡片文件**
   
   - 点击「导入」按钮
   - 选择项目中的 `docs/博主更新订阅.card` 文件
   - 卡片模板会自动加载

4. **预览和调整**
   
   - 检查卡片预览效果
   - 如需调整颜色或样式，可在可视化编辑器中修改
   - 卡片包含3个变量：
     - `platform` - 平台名称（如：哔哩哔哩）
     - `Influencer` - 博主名称
     - `markdown_content` - Markdown格式内容

5. **发布卡片**
   
   - 点击「保存并发布」
   - 记录生成的：
     - **模板ID** (`template_id`)
     - **版本名称** (`template_version_name`)

#### 卡片预览效果

```
┌──────────────────────────────────────┐
│ 哔哩哔哩                              │  ← 蓝色标题栏（platform）
│ 某某博主                              │  ← 副标题（Influencer）
├──────────────────────────────────────┤
│                                      │
│ 📌 核心观点                           │  ← Markdown内容
│ - 要点1                               │
│ - 要点2                               │
│                                      │
│ 💡 关键亮点                           │
│ 这是总结内容...                       │
│                                      │
│ [查看原视频](链接)                    │
│                                      │
└──────────────────────────────────────┘
```


## 配置到项目

### 更新 .env 文件

```env
# 飞书消息配置
FEISHU_TEMPLATE_ID=您的消息模板ID
FEISHU_TEMPLATE_VERSION=您的消息模板版本

# （可选）通道注册表文件路径，默认 data/feishu_channels.json
# FEISHU_CHANNELS_CONFIG=data/feishu_channels.json
```

### 配置通道注册表（多 webhook）

1. 复制示例文件：

```bash
cp data/feishu_channels.json.example data/feishu_channels.json
```

2. 编辑 `data/feishu_channels.json`：

- 在 `webhooks` 中添加多个命名 webhook（例如 `default`、`alerts`）
- 在 `defaults` 中设置默认路由：
   - `defaults.content`：内容推送走哪个 webhook
   - `defaults.alert`：告警推送走哪个 webhook

3. （可选）为不同 UP 指定不同 webhook：

在 `data/bilibili_creators.json` 的每个对象里增加：

```json
{
   "uid": 123456,
   "name": "某UP",
   "feishu_channel": "webhook:default"
}
```