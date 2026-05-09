import unittest
from unittest.mock import patch

import aiohttp

from creator_admin.bilibili_resolver import ResolverError, resolve_bilibili_creator


class _FakeResponse:
    def __init__(self, url: str, text: str = "", status: int = 200, json_data=None):
        self.url = url
        self._text = text
        self.status = status
        self._json_data = json_data

    async def text(self):
        return self._text

    async def json(self, content_type=None):
        if self._json_data is None:
            raise ValueError("no json")
        return self._json_data


class _FakeRequestContext:
    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc

    async def __aenter__(self):
        if self._exc is not None:
            raise self._exc
        return self._response

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeSession:
    def __init__(self, response=None, exc=None, response_map=None):
        self._response = response
        self._exc = exc
        self._response_map = response_map or {}
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.closed = True
        return False

    def get(self, url, *_args, **_kwargs):
        if self.closed:
            raise RuntimeError("Session is closed")
        if self._exc is not None:
            return _FakeRequestContext(response=None, exc=self._exc)
        mapped = self._response_map.get(url)
        if mapped is not None:
            return _FakeRequestContext(response=mapped, exc=None)
        return _FakeRequestContext(response=self._response, exc=None)


class TestBilibiliResolver(unittest.IsolatedAsyncioTestCase):
    async def test_accepts_space_url_and_extracts_uid_and_nickname(self):
        response = _FakeResponse(
            url="https://space.bilibili.com/1234567?spm_id_from=333.1007.0.0",
            text="<html><head><title>测试UP主的个人空间_哔哩哔哩</title></head></html>",
        )
        with patch("aiohttp.ClientSession", return_value=_FakeSession(response=response)):
            result = await resolve_bilibili_creator("https://space.bilibili.com/1234567")

        self.assertEqual(1234567, result["uid"])
        self.assertEqual("测试UP主", result["nickname"])

    async def test_resolves_b23_short_link_redirect(self):
        response = _FakeResponse(
            url="https://space.bilibili.com/7654321",
            text="<html><head><title>AnotherUP的个人空间-哔哩哔哩视频</title></head></html>",
        )
        with patch("aiohttp.ClientSession", return_value=_FakeSession(response=response)):
            result = await resolve_bilibili_creator("https://b23.tv/abcXYZ")

        self.assertEqual(7654321, result["uid"])
        self.assertEqual("AnotherUP", result["nickname"])

    async def test_extracts_link_from_bilibili_share_text(self):
        response = _FakeResponse(
            url="https://space.bilibili.com/625315686",
            text="<html><head><title>股市-桃哥复盘的个人空间-哔哩哔哩视频</title></head></html>",
        )
        share_text = "【股市-桃哥复盘的个人空间-哔哩哔哩】 https://b23.tv/c9pwlW0"
        with patch("aiohttp.ClientSession", return_value=_FakeSession(response=response)):
            result = await resolve_bilibili_creator(share_text)

        self.assertEqual(625315686, result["uid"])
        self.assertEqual("股市-桃哥复盘", result["nickname"])

    async def test_falls_back_to_uid_from_html_when_url_has_no_uid(self):
        html = """
        <html><head>
        <meta property=\"og:url\" content=\"https://space.bilibili.com/24680\" />
        <title>UPName的个人空间_哔哩哔哩</title>
        </head></html>
        """
        response = _FakeResponse(url="https://space.bilibili.com/", text=html)
        with patch("aiohttp.ClientSession", return_value=_FakeSession(response=response)):
            result = await resolve_bilibili_creator("https://space.bilibili.com/")

        self.assertEqual(24680, result["uid"])
        self.assertEqual("UPName", result["nickname"])

    async def test_rejects_non_space_url(self):
        with self.assertRaisesRegex(ResolverError, "Bilibili space"):
            await resolve_bilibili_creator("https://www.bilibili.com/video/BV1xx411c7mD")

    async def test_reports_network_failure(self):
        network_error = aiohttp.ClientError("boom")
        with patch("aiohttp.ClientSession", return_value=_FakeSession(exc=network_error)):
            result = await resolve_bilibili_creator("https://space.bilibili.com/123")

        self.assertEqual(123, result["uid"])
        self.assertIsNone(result["nickname"])

    async def test_keeps_uid_when_space_url_http_status_non_2xx(self):
        response = _FakeResponse(url="https://space.bilibili.com/31341757", text="<html></html>", status=412)
        with patch("aiohttp.ClientSession", return_value=_FakeSession(response=response)):
            result = await resolve_bilibili_creator("https://space.bilibili.com/31341757")

        self.assertEqual(31341757, result["uid"])
        self.assertIsNone(result["nickname"])

    async def test_rejects_invalid_url_scheme(self):
        with self.assertRaisesRegex(ResolverError, "Invalid URL"):
            await resolve_bilibili_creator("ftp://space.bilibili.com/123")

    async def test_rejects_malformed_url(self):
        with self.assertRaisesRegex(ResolverError, "Invalid URL"):
            await resolve_bilibili_creator("https:///space.bilibili.com/123")

    async def test_rejects_redirect_target_not_space_host(self):
        response = _FakeResponse(url="https://www.bilibili.com/video/BV12345", text="<html></html>")
        with patch("aiohttp.ClientSession", return_value=_FakeSession(response=response)):
            with self.assertRaisesRegex(ResolverError, "Resolved URL is not a Bilibili space page"):
                await resolve_bilibili_creator("https://b23.tv/abcXYZ")

    async def test_raises_when_uid_missing_in_body(self):
        html = "<html><head><title>NoUidUser的个人空间_哔哩哔哩</title></head></html>"
        response = _FakeResponse(url="https://space.bilibili.com/", text=html)
        with patch("aiohttp.ClientSession", return_value=_FakeSession(response=response)):
            with self.assertRaisesRegex(ResolverError, "Could not extract creator UID"):
                await resolve_bilibili_creator("https://space.bilibili.com/")

    async def test_extracts_nickname_from_og_title_when_title_missing(self):
        html = (
            "<html><head>"
            '<meta property="og:title" content="OG昵称的个人空间_哔哩哔哩" />'
            "</head></html>"
        )
        response = _FakeResponse(url="https://space.bilibili.com/30001", text=html)
        with patch("aiohttp.ClientSession", return_value=_FakeSession(response=response)):
            result = await resolve_bilibili_creator("https://space.bilibili.com/30001")

        self.assertEqual("OG昵称", result["nickname"])

    async def test_accepts_space_host_with_default_https_port(self):
        response = _FakeResponse(
            url="https://space.bilibili.com:443/998877",
            text="<html><head><title>PortUP的个人空间_哔哩哔哩</title></head></html>",
        )
        with patch("aiohttp.ClientSession", return_value=_FakeSession(response=response)):
            result = await resolve_bilibili_creator("https://space.bilibili.com:443/998877")

        self.assertEqual(998877, result["uid"])

    async def test_reports_non_2xx_http_status(self):
        response = _FakeResponse(url="https://b23.tv/abcXYZ", text="<html></html>", status=404)
        with patch("aiohttp.ClientSession", return_value=_FakeSession(response=response)):
            with self.assertRaisesRegex(ResolverError, "HTTP 404"):
                await resolve_bilibili_creator("https://b23.tv/abcXYZ")

    async def test_prefers_api_nickname_over_block_page_title(self):
        page = _FakeResponse(
            url="https://space.bilibili.com/31341757",
            text="<html><head><title>验证码</title></head></html>",
        )
        api = _FakeResponse(
            url="https://api.bilibili.com/x/space/acc/info?mid=31341757&jsonp=jsonp",
            json_data={"code": 0, "data": {"name": "真实昵称"}},
        )
        with patch(
            "aiohttp.ClientSession",
            return_value=_FakeSession(
                response=page,
                response_map={
                    "https://api.bilibili.com/x/space/acc/info?mid=31341757&jsonp=jsonp": api
                },
            ),
        ):
            result = await resolve_bilibili_creator("https://space.bilibili.com/31341757")

        self.assertEqual(31341757, result["uid"])
        self.assertEqual("真实昵称", result["nickname"])

    async def test_keeps_uid_when_nickname_lookup_cannot_use_closed_session(self):
        page = _FakeResponse(
            url="https://space.bilibili.com/31341757",
            text="<html><head><title>验证码</title></head></html>",
        )
        with patch("aiohttp.ClientSession", return_value=_FakeSession(response=page)):
            result = await resolve_bilibili_creator("https://space.bilibili.com/31341757")

        self.assertEqual(31341757, result["uid"])
        self.assertIsNone(result["nickname"])


if __name__ == "__main__":
    unittest.main()
