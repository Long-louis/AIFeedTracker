from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .auth import CookieAuth
from .bilibili_resolver import resolve_bilibili_creator
from .config import AdminSettings
from .creator_store import CreatorStore
from .html import creator_form_page, delete_confirm_page, list_page, login_page


Resolver = Callable[[str], Awaitable[dict]]


def create_app(
    settings: AdminSettings,
    store: CreatorStore | None = None,
    resolver: Resolver | None = None,
) -> FastAPI:
    store = store or CreatorStore(settings.creators_file)
    resolver = resolver or resolve_bilibili_creator
    app = FastAPI()
    auth = CookieAuth(settings.secret_key, settings.cookie_ttl_seconds)

    def _is_authed(request: Request) -> bool:
        token = request.cookies.get(settings.cookie_name, "")
        return auth.verify(token) is not None

    def _require_auth(request: Request):
        if not _is_authed(request):
            return RedirectResponse("/login", status_code=303)
        return None

    def _redirect(path: str) -> RedirectResponse:
        return RedirectResponse(path, status_code=303)

    def _success_message(saved: str = "", deleted: str = "") -> str:
        if saved == "1":
            return "保存成功"
        if deleted == "1":
            return "删除成功"
        return ""

    def _load_creators_safe() -> list[dict]:
        try:
            return store.load_creators()
        except ValueError:
            return []

    def _find_by_uid(creators: list[dict], uid: int) -> dict | None:
        for item in creators:
            try:
                item_uid = int(item.get("uid", 0))
            except (TypeError, ValueError):
                continue
            if item_uid == uid:
                return item
        return None

    def _check_duplicate_uid(creators: list[dict], uid: int, current_uid: int | None = None) -> bool:
        for item in creators:
            try:
                item_uid = int(item.get("uid", 0))
            except (TypeError, ValueError):
                continue
            if item_uid == uid and (current_uid is None or item_uid != current_uid):
                return True
        return False

    @app.get("/login", response_class=HTMLResponse)
    async def get_login():
        return HTMLResponse(login_page())

    @app.post("/login")
    async def post_login(password: str = Form(...)):
        if password != settings.password:
            return HTMLResponse(login_page("密码错误"), status_code=200)
        response = _redirect("/")
        response.set_cookie(
            settings.cookie_name,
            auth.sign("admin"),
            httponly=True,
            samesite="lax",
            secure=settings.env == "production",
            max_age=settings.cookie_ttl_seconds,
        )
        return response

    @app.post("/logout")
    async def post_logout():
        response = _redirect("/login")
        response.delete_cookie(settings.cookie_name)
        return response

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request, saved: str = "", deleted: str = ""):
        denied = _require_auth(request)
        if denied:
            return denied
        creators = _load_creators_safe()
        return HTMLResponse(list_page(creators, _success_message(saved=saved, deleted=deleted)))

    @app.get("/creators/new", response_class=HTMLResponse)
    async def new_creator(request: Request):
        denied = _require_auth(request)
        if denied:
            return denied
        return HTMLResponse(
            creator_form_page(
                "新增创作者",
                "/creators",
                {"platform": "bilibili"},
                mode="create",
            )
        )

    @app.post("/creators/resolve", response_class=HTMLResponse)
    async def resolve_creator(
        request: Request,
        space_url: str = Form(...),
        mode: str = Form("create"),
        current_uid: str = Form(""),
    ):
        denied = _require_auth(request)
        if denied:
            return denied

        creator = {"space_url": space_url, "platform": "bilibili", "current_uid": current_uid}
        action = "/creators"
        title = "新增创作者"
        if mode == "edit" and current_uid.strip().isdigit():
            action = f"/creators/{int(current_uid.strip())}"
            title = "编辑创作者"

        try:
            resolved = await resolver(space_url)
            creator["uid"] = resolved.get("uid", "")
            creator["name"] = resolved.get("nickname") or ""
        except Exception:
            return HTMLResponse(creator_form_page(title, action, creator, "解析失败：请稍后重试", mode=mode))

        creators = _load_creators_safe()
        try:
            resolved_uid = int(creator["uid"])
        except (TypeError, ValueError):
            return HTMLResponse(creator_form_page(title, action, creator, "解析失败：UID 无效", mode=mode))
        current_uid_num = int(current_uid) if current_uid.strip().isdigit() else None
        if _check_duplicate_uid(
            creators,
            resolved_uid,
            current_uid=current_uid_num if mode == "edit" else None,
        ):
            return HTMLResponse(creator_form_page(title, action, creator, "该 UID 已存在", mode=mode))

        return HTMLResponse(creator_form_page(title, action, creator, mode=mode))

    @app.post("/creators")
    async def create_creator(
        request: Request,
        uid: int = Form(...),
        name: str = Form(...),
        platform: str = Form("bilibili"),
    ):
        denied = _require_auth(request)
        if denied:
            return denied
        creators = _load_creators_safe()
        if _check_duplicate_uid(creators, uid):
            return HTMLResponse(
                creator_form_page(
                    "新增创作者",
                    "/creators",
                    {"uid": uid, "name": name, "platform": platform},
                    "该 UID 已存在",
                    mode="create",
                ),
                status_code=200,
            )

        creators.append({"uid": uid, "name": name, "platform": platform})
        store.save_creators(creators)
        return _redirect("/?saved=1")

    @app.get("/creators/{uid}/edit", response_class=HTMLResponse)
    async def edit_creator(request: Request, uid: int):
        denied = _require_auth(request)
        if denied:
            return denied
        creators = _load_creators_safe()
        creator = _find_by_uid(creators, uid)
        if creator is None:
            return _redirect("/")
        creator = dict(creator)
        creator["current_uid"] = uid
        return HTMLResponse(creator_form_page("编辑创作者", f"/creators/{uid}", creator, mode="edit"))

    @app.post("/creators/{uid}")
    async def save_creator(
        request: Request,
        uid: int,
        new_uid: int = Form(..., alias="uid"),
        name: str = Form(...),
        platform: str = Form("bilibili"),
    ):
        denied = _require_auth(request)
        if denied:
            return denied
        creators = _load_creators_safe()
        existing = _find_by_uid(creators, uid)
        if existing is None:
            return _redirect("/")

        if _check_duplicate_uid(creators, new_uid, current_uid=uid):
            return HTMLResponse(
                creator_form_page(
                    "编辑创作者",
                    f"/creators/{uid}",
                    {"uid": new_uid, "name": name, "platform": platform, "current_uid": uid},
                    "该 UID 已存在",
                    mode="edit",
                ),
                status_code=200,
            )

        existing["uid"] = new_uid
        existing["name"] = name
        existing["platform"] = platform
        store.save_creators(creators)
        return _redirect("/?saved=1")

    @app.get("/creators/{uid}/delete", response_class=HTMLResponse)
    async def delete_confirm(request: Request, uid: int):
        denied = _require_auth(request)
        if denied:
            return denied
        creators = _load_creators_safe()
        creator = _find_by_uid(creators, uid)
        if creator is None:
            return _redirect("/")
        return HTMLResponse(delete_confirm_page(creator))

    @app.post("/creators/{uid}/delete")
    async def delete_creator(request: Request, uid: int):
        denied = _require_auth(request)
        if denied:
            return denied
        creators = _load_creators_safe()
        creator = _find_by_uid(creators, uid)
        if creator is None:
            return _redirect("/")
        creators.remove(creator)
        store.save_creators(creators)
        return _redirect("/?deleted=1")

    return app
