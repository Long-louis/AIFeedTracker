# 飞书卡片配置

项目通过飞书群机器人 Webhook 推送模板卡片消息。推荐直接使用仓库里的 `docs/博主更新订阅.card` 作为起点。

## 你需要准备的内容

1. 一个飞书卡片模板
2. 一个或多个飞书群机器人 Webhook
3. `.env` 中的模板信息
4. `data/feishu_channels.json` 中的通道配置

## 导入卡片模板

1. 打开飞书开放平台并进入卡片搭建工具。
2. 导入 `docs/博主更新订阅.card`。
3. 发布后记录：
   - `template_id`
   - `template_version_name`

把这两个值写入 `.env`：

```env
FEISHU_TEMPLATE_ID=your-template-id
FEISHU_TEMPLATE_VERSION=your-template-version
```

## 配置 Webhook 通道

先复制示例文件：

```bash
cp data/feishu_channels.json.example data/feishu_channels.json
```

然后填写真实 Webhook：

```json
{
  "defaults": {
    "content": "webhook:default",
    "alert": "webhook:alerts"
  },
  "webhooks": {
    "default": {
      "url": "https://open.feishu.cn/open-apis/bot/v2/hook/REPLACE_ME",
      "secret": ""
    },
    "alerts": {
      "url": "https://open.feishu.cn/open-apis/bot/v2/hook/REPLACE_ME",
      "secret": ""
    }
  }
}
```

## 为订阅单独指定通道

在 `data/bilibili_creators.json` 里可以给某个 UP 主单独指定通道：

```json
{
  "uid": 123456,
  "name": "示例UP主",
  "feishu_channel": "webhook:default"
}
```

## 验证

完成配置后运行：

```bash
uv run python main.py --mode monitor --once
```

如果卡片模板字段不匹配，请检查模板里是否包含 `Influencer`、`addition_title`、`platform`、`addition_subtitle`、`markdown_content` 这些变量。
