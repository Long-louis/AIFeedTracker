# AI 视频总结配置

项目支持通过 OpenAI 兼容接口对 B 站视频字幕生成结构化总结。

## 支持的服务

- `deepseek`
- `zhipu`
- `qwen`

默认推荐 `deepseek`。

## 最小配置

在 `.env` 中填写：

```env
AI_SERVICE=deepseek
AI_API_KEY=your-api-key
```

可选配置：

```env
# AI_BASE_URL=https://api.deepseek.com
# AI_MODEL=deepseek-chat
```

## 工作方式

1. 服务检测到视频动态
2. 尝试获取视频字幕
3. 调用 AI 服务生成 Markdown 总结
4. 将总结附加到飞书卡片中

如果没有配置 `AI_API_KEY`，服务仍可运行，只是不会生成 AI 总结。

## 验证

配置完成后运行：

```bash
uv run python main.py --mode monitor --once
```

如果视频存在可获取字幕且 AI 调用成功，推送内容中会包含总结结果。
