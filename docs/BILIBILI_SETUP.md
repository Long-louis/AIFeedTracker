# B 站凭证配置

本项目使用 `bilibili-api-python` 访问 B 站动态接口。你需要先准备一组可用的登录凭证，并写入项目根目录 `.env`。

## 需要的字段

- `SESSDATA`
- `bili_jct`
- `buvid3`
- `DedeUserID`
- `ac_time_value`

可选字段：

- `buvid4`
- `refresh_token`
- `USER_AGENT`

## 获取方式

### Cookie 字段

1. 登录 B 站网页。
2. 打开浏览器开发者工具。
3. 在 Cookie 存储中找到并复制 `SESSDATA`、`bili_jct`、`buvid3`、`DedeUserID`。
4. 如果存在 `buvid4`，也建议一起填写。

### `ac_time_value`

在已登录的 B 站页面打开浏览器控制台，执行：

```javascript
window.localStorage.ac_time_value
```

复制返回值写入 `.env`。

## `.env` 示例

```env
SESSDATA=your-sessdata
bili_jct=your-bili-jct
buvid3=your-buvid3
DedeUserID=your-dede-user-id
ac_time_value=your-ac-time-value

# Optional
# buvid4=your-buvid4
# refresh_token=your-refresh-token
# USER_AGENT=Mozilla/5.0 ...
```

## 验证

填写完成后可运行：

```bash
uv run python main.py --mode monitor --once
```

如果凭证失效，服务会尝试刷新，必要时会触发二维码登录流程。

## 参考资料

- `bilibili-api-python`: https://nemo2011.github.io/bilibili-api/#/
- B 站接口资料汇总: https://socialsisteryi.github.io/bilibili-API-collect/docs/index.html
