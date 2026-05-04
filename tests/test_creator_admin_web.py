import tempfile
import unittest
import importlib
import sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from starlette.testclient import TestClient

from creator_admin.auth import CookieAuth
from creator_admin.config import AdminSettings
from creator_admin.creator_store import CreatorStore


class TestCreatorAdminWeb(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _ensure_real_fastapi_module() -> None:
        fastapi_mod = sys.modules.get("fastapi")
        if fastapi_mod is not None and not hasattr(fastapi_mod, "Form"):
            sys.modules.pop("fastapi", None)
            sys.modules.pop("fastapi.concurrency", None)
            sys.modules.pop("creator_admin.app", None)
        importlib.import_module("fastapi")

    async def asyncSetUp(self):
        self._ensure_real_fastapi_module()
        from creator_admin.app import create_app

        self._tmpdir = tempfile.TemporaryDirectory()
        self.addAsyncCleanup(self._cleanup_tmpdir)
        self.data_path = Path(self._tmpdir.name) / "creators.json"
        self.data_path.write_text(
            """[
  {
    "uid": 100,
    "name": "已存在UP",
    "platform": "bilibili"
  }
]
""",
            encoding="utf-8",
        )
        self.settings = AdminSettings(
            host="127.0.0.1",
            port=8910,
            creators_file=str(self.data_path),
            password="pw",
            secret_key="k" * 32,
            env="test",
            cookie_name="creator_admin_session",
            cookie_ttl_seconds=3600,
            cookie_secure=False,
        )
        self.store = CreatorStore(self.data_path)

        async def fake_resolver(_url: str):
            return {"uid": 200, "nickname": "新UP", "url": "https://space.bilibili.com/200"}

        self.app = create_app(self.settings, self.store, fake_resolver)
        self.client = TestClient(self.app)

    async def _cleanup_tmpdir(self):
        self._tmpdir.cleanup()

    def _auth_cookie(self):
        token = CookieAuth(self.settings.secret_key, self.settings.cookie_ttl_seconds).sign("admin")
        return {self.settings.cookie_name: token}

    def _assert_redirect_to_login(self, response):
        self.assertEqual(303, response.status_code)
        self.assertEqual("/login", response.headers["location"])

    async def test_login_logout_and_auth_guard(self):
        response = self.client.get("/", follow_redirects=False)
        self.assertEqual(303, response.status_code)
        self.assertIn("/login", response.headers["location"])

        page = self.client.get("/login")
        self.assertEqual(200, page.status_code)
        self.assertIn("管理员登录", page.text)

        bad = self.client.post("/login", data={"password": "bad"})
        self.assertEqual(200, bad.status_code)
        self.assertIn("密码错误", bad.text)

        good = self.client.post("/login", data={"password": "pw"}, follow_redirects=False)
        self.assertEqual(303, good.status_code)
        self.assertEqual("/", good.headers["location"])
        self.assertIn(self.settings.cookie_name, good.cookies)

        protected = self.client.get("/", cookies=self._auth_cookie())
        self.assertEqual(200, protected.status_code)
        self.assertIn("创作者管理", protected.text)

        logout = self.client.post("/logout", cookies=self._auth_cookie(), follow_redirects=False)
        self.assertEqual(303, logout.status_code)
        self.assertEqual("/login", logout.headers["location"])

    async def test_unauthenticated_access_redirects_to_login(self):
        for route in ["/", "/creators/new", "/creators/100/edit", "/creators/100/delete"]:
            response = self.client.get(route, follow_redirects=False)
            self._assert_redirect_to_login(response)

        for path, data in [
            ("/logout", {}),
            ("/creators/resolve", {"space_url": "https://space.bilibili.com/200", "mode": "create"}),
            ("/creators", {"uid": "200", "name": "新UP", "platform": "bilibili"}),
            ("/creators/100", {"uid": "200", "name": "新UP", "platform": "bilibili"}),
            ("/creators/100/delete", {}),
        ]:
            response = self.client.post(path, data=data, follow_redirects=False)
            self._assert_redirect_to_login(response)

    async def test_list_new_resolve_create_edit_delete_flow(self):
        cookies = self._auth_cookie()

        listing = self.client.get("/", cookies=cookies)
        self.assertIn("已存在UP", listing.text)

        new_page = self.client.get("/creators/new", cookies=cookies)
        self.assertEqual(200, new_page.status_code)
        self.assertIn("新增创作者", new_page.text)
        self.assertIn("type='text' name='space_url'", new_page.text)

        resolved = self.client.post(
            "/creators/resolve",
            data={"space_url": "https://space.bilibili.com/200", "mode": "create"},
            cookies=cookies,
        )
        self.assertEqual(200, resolved.status_code)
        self.assertIn("value='200'", resolved.text)
        self.assertIn("新UP", resolved.text)

        created = self.client.post(
            "/creators",
            data={"uid": "200", "name": "新UP", "platform": "bilibili"},
            cookies=cookies,
            follow_redirects=False,
        )
        self.assertEqual(303, created.status_code)
        self.assertIn("saved=1", created.headers["location"])
        created_location = urlparse(created.headers["location"])
        self.assertEqual("/", created_location.path)
        self.assertEqual(["1"], parse_qs(created_location.query).get("saved"))

        dup_create = self.client.post(
            "/creators/resolve",
            data={"space_url": "https://space.bilibili.com/200", "mode": "create"},
            cookies=cookies,
        )
        self.assertIn("已存在", dup_create.text)

        edit_page = self.client.get("/creators/200/edit", cookies=cookies)
        self.assertEqual(200, edit_page.status_code)
        self.assertIn("编辑创作者", edit_page.text)

        edit_resolved = self.client.post(
            "/creators/resolve",
            data={"space_url": "https://space.bilibili.com/200", "mode": "edit", "current_uid": "200"},
            cookies=cookies,
        )
        self.assertNotIn("已存在", edit_resolved.text)

        saved = self.client.post(
            "/creators/200",
            data={"uid": "201", "name": "改名UP", "platform": "bilibili"},
            cookies=cookies,
            follow_redirects=False,
        )
        self.assertEqual(303, saved.status_code)
        saved_location = urlparse(saved.headers["location"])
        self.assertEqual("/", saved_location.path)
        self.assertEqual(["1"], parse_qs(saved_location.query).get("saved"))

        confirm = self.client.get("/creators/201/delete", cookies=cookies)
        self.assertEqual(200, confirm.status_code)
        self.assertIn("确认删除", confirm.text)

        deleted = self.client.post("/creators/201/delete", cookies=cookies, follow_redirects=False)
        self.assertEqual(303, deleted.status_code)
        self.assertIn("deleted=1", deleted.headers["location"])
        deleted_location = urlparse(deleted.headers["location"])
        self.assertEqual("/", deleted_location.path)
        self.assertEqual(["1"], parse_qs(deleted_location.query).get("deleted"))

    async def test_success_messages_render_from_querystring(self):
        cookies = self._auth_cookie()
        saved_page = self.client.get("/?saved=1", cookies=cookies)
        self.assertEqual(200, saved_page.status_code)
        self.assertIn("保存成功", saved_page.text)

        deleted_page = self.client.get("/?deleted=1", cookies=cookies)
        self.assertEqual(200, deleted_page.status_code)
        self.assertIn("删除成功", deleted_page.text)

    async def test_edit_uid_conflict_keeps_file_unchanged(self):
        cookies = self._auth_cookie()
        self.data_path.write_text(
            """[
  {
    "uid": 100,
    "name": "A",
    "platform": "bilibili"
  },
  {
    "uid": 200,
    "name": "B",
    "platform": "bilibili"
  }
]
""",
            encoding="utf-8",
        )
        before = self.data_path.read_text(encoding="utf-8")

        response = self.client.post(
            "/creators/200",
            data={"uid": "100", "name": "B2", "platform": "bilibili"},
            cookies=cookies,
        )
        self.assertEqual(200, response.status_code)
        self.assertIn("该 UID 已存在", response.text)
        self.assertEqual(before, self.data_path.read_text(encoding="utf-8"))

    async def test_malformed_uid_records_do_not_crash_list_or_delete_confirm(self):
        cookies = self._auth_cookie()
        self.data_path.write_text(
            """[
  {
    "uid": "bad",
    "name": "坏数据",
    "platform": "bilibili"
  },
  {
    "name": "缺失UID",
    "platform": "bilibili"
  }
]
""",
            encoding="utf-8",
        )

        listing = self.client.get("/", cookies=cookies)
        self.assertEqual(200, listing.status_code)
        self.assertIn("创作者管理", listing.text)

        confirm = self.client.get("/creators/0/delete", cookies=cookies, follow_redirects=False)
        self.assertEqual(303, confirm.status_code)
        self.assertEqual("/", confirm.headers["location"])

    async def test_resolve_handles_bad_uid_payload_and_safe_error_message(self):
        self._ensure_real_fastapi_module()
        from creator_admin.app import create_app

        async def bad_uid_resolver(_url: str):
            return {"uid": "abc", "nickname": "新UP"}

        async def boom_resolver(_url: str):
            raise RuntimeError("token=very-secret")

        app_bad_uid = create_app(self.settings, self.store, bad_uid_resolver)
        app_boom = create_app(self.settings, self.store, boom_resolver)
        client_bad_uid = TestClient(app_bad_uid)
        client_boom = TestClient(app_boom)
        cookies = self._auth_cookie()

        bad_uid = client_bad_uid.post(
            "/creators/resolve",
            data={"space_url": "https://space.bilibili.com/abc", "mode": "create"},
            cookies=cookies,
        )
        self.assertEqual(200, bad_uid.status_code)
        self.assertIn("解析失败", bad_uid.text)

        resolver_fail = client_boom.post(
            "/creators/resolve",
            data={"space_url": "https://space.bilibili.com/abc", "mode": "create"},
            cookies=cookies,
        )
        self.assertEqual(200, resolver_fail.status_code)
        self.assertIn("解析失败", resolver_fail.text)
        self.assertNotIn("very-secret", resolver_fail.text)


if __name__ == "__main__":
    unittest.main()
