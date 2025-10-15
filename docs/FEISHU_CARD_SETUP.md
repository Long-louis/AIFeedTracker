# 飞书卡片模板配置指南

本项目使用飞书卡片消息推送视频总结和动态通知。由于卡片模板是绑定到特定飞书应用的，您需要在自己的飞书应用中创建相同的卡片模板。

## 前提条件

1. 已创建飞书企业自建应用
2. 已获取 `app_id` 和 `app_secret`
3. 应用已开启消息相关权限

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
# 飞书应用配置
app_id=cli_xxxxxxxxxxxxx
app_secret=xxxxxxxxxxxxxxxxxxxxx

# 飞书消息配置
FEISHU_TEMPLATE_ID=您的消息模板ID
FEISHU_TEMPLATE_VERSION=您的消息模板版本
FEISHU_USER_OPEN_ID=您的用户open_id
```

### 获取用户 open_id

请查看[飞书文档](https://open.feishu.cn/document/server-docs/contact-v3/user/batch_get_id?appId=cli_a8675b0dfcc3500d)