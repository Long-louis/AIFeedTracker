# 🎯 评论筛选模式完全指南

## 问题背景

您需要灵活的筛选逻辑，而不仅仅是简单的 AND 关系。例如：

- ✅ 获取**特定用户**的**任意评论**
- ✅ 获取**任意用户**包含**特定关键词**的评论
- ✅ 获取**特定用户**的**特定关键词**评论
- ✅ 以上任意组合

## 解决方案

我们提供了 **6 种预定义筛选模式**，无需额外依赖，配置即用！

---

## 📋 6 种筛选模式详解

### 1. `keywords_or_users` - 关键字或用户（推荐 ⭐）

**逻辑**：`(关键字匹配 OR 用户匹配) AND 点赞数达标`

**适用场景**：

- 想要获取特定用户的所有评论
- 或者任意用户包含关键词的评论
- 两者满足其一即可

**配置示例**：

```json
{
  "comment_keywords": ["总结", "梗概"],
  "comment_target_users": ["CommentUserA", 123456789],
  "comment_min_likes": 10,
  "comment_filter_mode": "keywords_or_users"
}
```

**效果**：

- ✅ "CommentUserA"发的任何评论（不管是否包含关键词）
- ✅ UID=123456789 的用户发的任何评论
- ✅ 任意用户包含"总结"或"梗概"的评论
- ❌ 点赞数<10 的评论（硬性要求）

---

### 2. `keywords_and_users` - 关键字且用户

**逻辑**：`关键字匹配 AND 用户匹配 AND 点赞数达标`

**适用场景**：

- 只要特定用户发布的特定内容
- 更严格的筛选

**配置示例**：

```json
{
  "comment_keywords": ["总结"],
  "comment_target_users": ["CommentUserA"],
  "comment_min_likes": 5,
  "comment_filter_mode": "keywords_and_users"
}
```

**效果**：

- ✅ "CommentUserA"发的包含"总结"的评论
- ❌ "CommentUserA"发的其他评论
- ❌ 其他用户包含"总结"的评论

---

### 3. `keywords_only` - 只看关键字

**逻辑**：`关键字匹配 AND 点赞数达标`（忽略用户条件）

**适用场景**：

- 只关心内容，不关心是谁发的
- 获取所有 AI 总结类评论

**配置示例**：

```json
{
  "comment_keywords": ["总结", "AI总结", "TL;DR"],
  "comment_target_users": [],
  "comment_min_likes": 20,
  "comment_filter_mode": "keywords_only"
}
```

**效果**：

- ✅ 任意用户包含关键词的评论
- ❌ 即使设置了 target_users 也会被忽略

---

### 4. `users_only` - 只看用户

**逻辑**：`用户匹配 AND 点赞数达标`（忽略关键字条件）

**适用场景**：

- 追踪特定评论大神的所有发言
- 不关心内容，只关心是谁发的

**配置示例**：

```json
{
  "comment_keywords": [],
  "comment_target_users": ["评论大神A", "评论大神B", 123456],
  "comment_min_likes": null,
  "comment_filter_mode": "users_only"
}
```

**效果**：

- ✅ 指定用户的所有评论
- ❌ 即使设置了 keywords 也会被忽略

---

### 5. `all` - 所有条件（严格模式）

**逻辑**：`关键字匹配 AND 用户匹配 AND 点赞数达标`

**适用场景**：

- 最严格的筛选
- 所有设置的条件都必须满足

**配置示例**：

```json
{
  "comment_keywords": ["总结"],
  "comment_target_users": ["CommentUserA"],
  "comment_min_likes": 50,
  "comment_filter_mode": "all"
}
```

**效果**：

- ✅ 必须是"CommentUserA"发的
- ✅ 必须包含"总结"
- ✅ 必须点赞数>=50
- ❌ 缺一不可

---

### 6. `any` - 任一条件（宽松模式）

**逻辑**：`关键字匹配 OR 用户匹配 OR 点赞数超高`

**适用场景**：

- 最宽松的筛选
- 满足任一条件即可

**配置示例**：

```json
{
  "comment_keywords": ["总结"],
  "comment_target_users": ["CommentUserA"],
  "comment_min_likes": 100,
  "comment_filter_mode": "any"
}
```

**效果**：

- ✅ "CommentUserA"的评论（不管内容和点赞）
- ✅ 包含"总结"的评论（不管是谁发的）
- ✅ 点赞数>=100 的评论（不管内容和用户）
- ✅ 以上任一条件满足即可

---

## 🎨 实际使用示例

### 示例 1: 获取 AI 总结评论（推荐）

**需求**：获取评论区的 AI 总结，无论是谁发的

```json
{
  "uid": 123456789,
  "name": "UP主示例",
  "enable_comments": true,
  "comment_rules": [
    {
      "name": "AI总结评论",
      "keywords": ["总结", "梗概", "AI总结", "TL;DR", "要点"],
      "target_users": [],
      "min_likes": 10,
      "filter_mode": "keywords_only"
    }
  ]
}
```

---

### 示例 2: 追踪评论大神

**需求**：关注几个经常发高质量评论的用户，获取他们的所有评论

```json
{
  "uid": 987654321,
  "name": "UP主示例",
  "enable_comments": true,
  "comment_rules": [
    {
      "name": "评论大神追踪",
      "keywords": [],
      "target_users": ["CommentExpertA", "CommentExpertB", 111222333],
      "min_likes": 5,
      "filter_mode": "users_only"
    }
  ]
}
```

---

### 示例 3: 灵活组合（最常用）

**需求**：

- 想要特定用户的评论
- 或者任意用户的 AI 总结评论

```json
{
  "uid": 555555555,
  "name": "UP主示例",
  "enable_comments": true,
  "comment_rules": [
    {
      "name": "AI总结或专家评论",
      "keywords": ["总结", "梗概"],
      "target_users": ["CommentExpertA"],
      "min_likes": 10,
      "filter_mode": "keywords_or_users"
    }
  ]
}
```

**实际效果**：

- ✅ "CommentExpertA"的所有评论（即使不包含关键词）
- ✅ 任意用户包含"总结"或"梗概"的评论
- ❌ 其他用户的其他评论

---

### 示例 4: 特定用户的特定内容

**需求**：只要某个大神的 AI 总结评论

```json
{
  "enable_comments": true,
  "comment_rules": [
    {
      "name": "专家AI总结",
      "keywords": ["总结"],
      "target_users": ["CommentExpertA"],
      "min_likes": null,
      "filter_mode": "keywords_and_users"
    }
  ]
}
```

**实际效果**：

- ✅ "CommentExpertA"发的包含"总结"的评论
- ❌ "CommentExpertA"的其他评论
- ❌ 其他用户的总结评论

---

## 🔧 支持 UID 和用户名

`comment_target_users` 字段支持**混合使用**：

```json
{
  "comment_target_users": [
    123456789, // UID (整数)
    "CommentUserA", // 用户名 (字符串)
    987654321, // 另一个UID
    "CommentUserB" // 另一个用户名
  ]
}
```

**建议**：

- 使用 UID 更准确（用户可能改名）
- 使用用户名更直观（方便配置）
- 可以混用！

---

## 📊 筛选模式对比表

| 模式                 | 关键字 | 用户 | 点赞数 | 适用场景                              |
| -------------------- | ------ | ---- | ------ | ------------------------------------- |
| `keywords_or_users`  | OR     | OR   | AND    | 🌟 最常用：获取 AI 总结或特定用户评论 |
| `keywords_and_users` | AND    | AND  | AND    | 特定用户的特定内容                    |
| `keywords_only`      | ✓      | ✗    | AND    | 只关心内容，不关心用户                |
| `users_only`         | ✗      | ✓    | AND    | 只关心用户，不关心内容                |
| `all`                | AND    | AND  | AND    | 最严格：所有条件都满足                |
| `any`                | OR     | OR   | OR     | 最宽松：任一条件满足                  |

**说明**：

- ✓ = 检查该条件
- ✗ = 忽略该条件
- AND = 必须满足
- OR = 满足其一即可

---

## 💡 配置技巧

### 技巧 1: 获取所有高赞评论

```json
{
  "enable_comments": true,
  "comment_keywords": [],
  "comment_target_users": [],
  "comment_min_likes": 100,
  "comment_filter_mode": "any"
}
```

### 技巧 2: 只要有"总结"就行

```json
{
  "enable_comments": true,
  "comment_keywords": ["总结"],
  "comment_target_users": [],
  "comment_min_likes": null,
  "comment_filter_mode": "keywords_only"
}
```

### 技巧 3: 特定用户的高质量评论

```json
{
  "enable_comments": true,
  "comment_rules": [
    {
      "name": "特定用户高质量评论",
      "keywords": [],
      "target_users": ["CommentExpertA"],
      "min_likes": 20,
      "filter_mode": "users_only"
    }
  ]
}
```

---

## 🚀 测试您的配置

创建测试脚本 `test_my_filter.py`：

```python
import asyncio
import logging
from services.comment_fetcher import CommentFetcher
from bilibili_api import Credential
from config import BILIBILI_CONFIG

async def test():
    credential = Credential(
        sessdata=BILIBILI_CONFIG.get("SESSDATA"),
        bili_jct=BILIBILI_CONFIG.get("bili_jct"),
        buvid3=BILIBILI_CONFIG.get("buvid3"),
    )

    fetcher = CommentFetcher(credential)

    # 测试您的筛选条件
    comments = await fetcher.fetch_hot_comments(
        bvid="BV1HnaHzcEag",
        keywords=["总结", "梗概"],
        target_usernames=["CommentUserA"],
        min_likes=20,
        filter_mode="keywords_or_users"  # 修改这里测试不同模式
    )

    print(f"找到 {len(comments)} 条评论")
    for comm in comments:
        print(fetcher.format_comment_for_display(comm))

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test())
```

---

## ❓ 常见问题

### Q: 如何选择合适的模式？

**推荐流程**：

1. 先用 `keywords_or_users` （最灵活）
2. 如果评论太多，用 `keywords_and_users` （更严格）
3. 如果只关心内容，用 `keywords_only`
4. 如果只关心用户，用 `users_only`

### Q: 点赞数在各个模式中的作用？

**重要**：在大多数模式中，`comment_min_likes` 是**硬性要求**：

- 除了 `any` 模式外，点赞数不达标的评论都会被过滤
- 设为 `null` 表示不限制点赞数

### Q: 如果只设置了关键字，没设置用户？

各模式表现：

- `keywords_or_users`: ✅ 正常工作，只检查关键字
- `keywords_and_users`: ✅ 正常工作，只检查关键字
- `keywords_only`: ✅ 正常工作
- `users_only`: ❌ 不会返回任何结果
- `all`: ✅ 正常工作，只检查关键字
- `any`: ✅ 正常工作

### Q: 用户名和 UID 可以混用吗？

**可以！** 完全支持混用：

```json
{
  "comment_target_users": [
    "甜糖糖0507", // 用户名
    123456789, // UID
    "另一个用户" // 用户名
  ]
}
```

---

## 🎓 高级示例

### 场景 A: 专业评论员追踪

您发现几个用户经常发布高质量评论，想追踪他们：

```json
{
  "enable_comments": true,
  "comment_rules": [
    {
      "name": "专业评论员追踪",
      "keywords": [],
      "target_users": ["CommentExpertA", "CommentExpertB", "CommentExpertC"],
      "min_likes": null,
      "filter_mode": "users_only"
    }
  ]
}
```

### 场景 B: AI 总结 + 人工总结

想要所有的总结类评论，无论是 AI 还是人工：

```json
{
  "enable_comments": true,
  "comment_keywords": [
    "总结",
    "梗概",
    "要点",
    "TL;DR",
    "AI总结",
    "概括",
    "提炼"
  ],
  "comment_target_users": [],
  "comment_min_likes": 10,
  "comment_filter_mode": "keywords_only"
}
```

### 场景 C: 精准狙击

只要某个特定用户发的包含"复盘"关键词且高赞的评论：

```json
{
  "enable_comments": true,
  "comment_rules": [
    {
      "name": "专家复盘评论",
      "keywords": ["复盘"],
      "target_users": ["TradingExpert"],
      "min_likes": 50,
      "filter_mode": "keywords_and_users"
    }
  ]
}
```

---

## 🔄 实时生效

配置修改后**无需重启**服务：

1. 编辑 `data/bilibili_creators.json`
2. 保存文件
3. 下次检查动态时自动加载新配置

---

## 📝 总结

| 您的需求                    | 推荐模式               |
| --------------------------- | ---------------------- |
| 任意用户的 AI 总结评论      | `keywords_only`        |
| 特定用户的所有评论          | `users_only`           |
| 特定用户的 AI 总结评论      | `keywords_and_users`   |
| AI 总结评论 或 特定用户评论 | `keywords_or_users` ⭐ |
| 最宽松，能抓到就行          | `any`                  |
| 最严格，全部满足            | `all`                  |

**默认推荐**：`keywords_or_users` - 兼顾灵活性和实用性
