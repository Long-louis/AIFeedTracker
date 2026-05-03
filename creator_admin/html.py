from html import escape


def _safe_uid(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def page(title: str, body: str) -> str:
    return (
        "<!doctype html>"
        "<html><head><meta charset='utf-8'>"
        f"<title>{escape(title)}</title>"
        "<style>body{font-family:Arial,sans-serif;max-width:900px;margin:24px auto;padding:0 12px;}"
        "input,button{padding:6px;margin:4px 0;}table{border-collapse:collapse;width:100%;}"
        "th,td{border:1px solid #ddd;padding:8px;text-align:left;}a{margin-right:8px;}</style>"
        "</head><body>"
        f"{body}"
        "</body></html>"
    )


def login_page(error: str = "") -> str:
    error_html = f"<p style='color:#b00020'>{escape(error)}</p>" if error else ""
    return page(
        "管理员登录",
        "<h1>管理员登录</h1>"
        f"{error_html}"
        "<form method='post' action='/login'>"
        "<label>密码</label><br><input type='password' name='password' required>"
        "<br><button type='submit'>登录</button></form>",
    )


def list_page(creators: list[dict], message: str = "") -> str:
    rows = []
    for creator in creators:
        uid = _safe_uid(creator.get("uid", 0))
        name = escape(str(creator.get("name", "")))
        platform = escape(str(creator.get("platform", "")))
        rows.append(
            f"<tr><td>{uid}</td><td>{name}</td><td>{platform}</td>"
            f"<td><a href='/creators/{uid}/edit'>编辑</a>"
            f"<a href='/creators/{uid}/delete'>删除</a></td></tr>"
        )
    message_html = f"<p style='color:#067d17'>{escape(message)}</p>" if message else ""
    return page(
        "创作者管理",
        "<h1>创作者管理</h1>"
        f"{message_html}"
        "<p><a href='/creators/new'>新增创作者</a>"
        "<form method='post' action='/logout' style='display:inline'><button type='submit'>退出</button></form></p>"
        "<table><thead><tr><th>UID</th><th>名称</th><th>平台</th><th>操作</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>",
    )


def creator_form_page(title: str, action: str, creator: dict, error: str = "", mode: str = "create") -> str:
    uid = escape(str(creator.get("uid", "")))
    name = escape(str(creator.get("name", "")))
    platform = escape(str(creator.get("platform", "bilibili")))
    current_uid = escape(str(creator.get("current_uid", creator.get("uid", ""))))
    space_url = escape(str(creator.get("space_url", "")))
    error_html = f"<p style='color:#b00020'>{escape(error)}</p>" if error else ""
    return page(
        title,
        f"<h1>{escape(title)}</h1>"
        "<p><a href='/'>返回列表</a></p>"
        f"{error_html}"
        "<form method='post' action='/creators/resolve'>"
        "<label>B站主页链接</label><br>"
        f"<input type='text' name='space_url' value='{space_url}' style='width:100%' placeholder='https://space.bilibili.com/123 或 B站分享文本'>"
        f"<input type='hidden' name='mode' value='{escape(mode)}'>"
        f"<input type='hidden' name='current_uid' value='{current_uid}'>"
        "<br><button type='submit'>解析链接</button></form><hr>"
        f"<form method='post' action='{escape(action)}'>"
        "<label>UID</label><br>"
        f"<input type='number' name='uid' required value='{uid}'><br>"
        "<label>名称</label><br>"
        f"<input type='text' name='name' required value='{name}'><br>"
        "<label>平台</label><br>"
        f"<input type='text' name='platform' value='{platform}'><br>"
        "<button type='submit'>保存</button></form>",
    )


def delete_confirm_page(creator: dict) -> str:
    uid = _safe_uid(creator.get("uid"))
    name = escape(str(creator.get("name", "")))
    return page(
        "确认删除",
        "<h1>确认删除</h1>"
        f"<p>确认删除创作者：{name}（UID: {uid}）？</p>"
        f"<form method='post' action='/creators/{uid}/delete'><button type='submit'>确认删除</button></form>"
        "<p><a href='/'>取消</a></p>",
    )
