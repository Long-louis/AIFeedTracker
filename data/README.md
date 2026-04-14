# Data 目录说明

此目录用于存储项目的配置和运行时数据。

## 文件说明

### bilibili_creators.json（必需）

存储您想要监控的 B 站博主列表。

**首次使用**：复制示例文件并修改

```bash
cp bilibili_creators.json.example bilibili_creators.json
```

**文件结构**：

```json
[
  {
    "uid": 123456, // B站用户ID（必需，示例值请替换）
    "name": "博主名称", // 显示名称（必需）
    "check_interval": 300, // 检查间隔（秒），默认300秒
    "enable_comments": false, // 是否启用评论监控（可选）
    "comment_rules": [], // 评论筛选规则列表（可选，支持多规则）
    "feishu_channel": "webhook:default" // 可选：为该博主指定推送通道（例如 webhook:alerts）
  }
]
```

**如何获取博主 UID**：

1. 访问博主的 B 站主页
2. URL 中的数字即为 UID：`https://space.bilibili.com/123456`

### bilibili_state.json（自动生成，无需手动创建）

存储动态监控的运行时状态（最小化仅包含 `last_seen`），用于避免重复推送。

**重要**：此文件由程序自动创建和管理，属于运行时中间数据，你**不需要**手动创建或修改。

**格式（当前实现最小字段仅使用 last_seen）**：

```json
{
  "123456": {
    "last_seen": "最近一次推送的动态ID"
  }
}
```

**重置方法**（重新推送历史动态）：

- 使用重置命令：`uv run python main.py --reset`（会清空状态，并在下一次启动时补发近期动态）

### bilibili_auth.json（可选）

存储 B 站认证令牌（refresh_token）用于自动刷新 Cookie。

**注意**：此文件包含敏感信息，已在.gitignore 中忽略，不会被推送到 GitHub。

详细配置请参考：[../docs/Configuration.md](../docs/Configuration.md)

## 安全提示

- ⚠️ **不要**将包含真实数据的 `.json` 文件推送到 GitHub
- ✅ **使用** `.example` 示例文件作为参考
- ✅ 实际配置文件已在 `.gitignore` 中被忽略
- ✅ 只有示例文件（`.example`）会被 Git 追踪

## 快速开始

### 必需配置（用户需要操作）

```bash
# 1. 复制示例文件
cp data/bilibili_creators.json.example data/bilibili_creators.json

# 2. 编辑配置文件，添加您要监控的博主UID
# 使用文本编辑器修改 bilibili_creators.json
```

### Feishu 通道配置（可选但推荐）

本项目通过 `data/feishu_channels.json` 集中管理飞书推送通道（多个命名 webhook 与可选 app）。

复制示例并填写 webhook 信息：

```bash
cp data/feishu_channels.json.example data/feishu_channels.json
```

在 `webhooks` 中添加多个命名 webhook 并在 `defaults` 中设置 `content` / `alert` 的默认通道。可选地，在 `apps` 节点中添加应用机器人配置，并使用 `app:<name>` 作为通道来启用应用机器人（app 模式会在需要时懒加载 `lark-oapi`）。

### 自动生成文件（程序自动创建）

以下文件会在程序首次运行时自动创建，**无需手动操作**：

- ✅ `bilibili_auth.json` - B 站认证令牌（如果配置了 refresh_token）

### 测试运行

```bash
# 运行一次检查（测试配置是否正确）
uv run python main.py --mode monitor --once
```
