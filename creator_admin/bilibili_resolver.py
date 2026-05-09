import re
from html import unescape
from urllib.parse import urlparse

import aiohttp


class ResolverError(ValueError):
    pass


_SPACE_HOST = "space.bilibili.com"
_SHORT_HOSTS = {"b23.tv", "www.b23.tv"}
_UID_URL_RE = re.compile(r"/([1-9]\d*)(?:/)?$")
_UID_HTML_RE = re.compile(r"space\.bilibili\.com/([1-9]\d*)")
_UID_JSON_RE = re.compile(r'"(?:mid|uid)"\s*:\s*"?([1-9]\d*)"?')
_URL_IN_TEXT_RE = re.compile(r"https?://[^\s，。！？、；）】)]+")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_OG_TITLE_RE = re.compile(
    r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\'](.*?)["\']',
    re.IGNORECASE | re.DOTALL,
)


async def resolve_bilibili_creator(raw_url: str, timeout_seconds: int = 10) -> dict:
    raw_url = _extract_url_from_text(raw_url)
    parsed = urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ResolverError("Invalid URL: expected an absolute HTTP(S) URL")

    host = parsed.hostname.lower()
    if host not in _SHORT_HOSTS and not _is_space_url(parsed):
        raise ResolverError("URL must be a Bilibili space link or b23 short link")

    direct_uid = _extract_uid_from_url(parsed.path) if _is_space_url(parsed) else None

    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(raw_url) as response:
                if not 200 <= response.status < 300:
                    if direct_uid is not None:
                        return {
                            "uid": direct_uid,
                            "nickname": None,
                            "url": f"https://{_SPACE_HOST}/{direct_uid}",
                        }
                    raise ResolverError(
                        f"Resolver request failed with HTTP {response.status} for URL: {raw_url}"
                    )
                final_url = str(response.url)
                html = await response.text()

            final_parsed = urlparse(final_url)
            if not _is_space_url(final_parsed):
                if direct_uid is not None:
                    return {
                        "uid": direct_uid,
                        "nickname": None,
                        "url": f"https://{_SPACE_HOST}/{direct_uid}",
                    }
                raise ResolverError("Resolved URL is not a Bilibili space page")

            uid = _extract_uid_from_url(final_parsed.path)
            if uid is None:
                uid = _extract_uid_from_html(html)
            if uid is None:
                raise ResolverError("Could not extract creator UID from space page")

            nickname = await _fetch_nickname_by_uid(session, uid)
    except aiohttp.ClientError as exc:
        if direct_uid is not None:
            return {
                "uid": direct_uid,
                "nickname": None,
                "url": f"https://{_SPACE_HOST}/{direct_uid}",
            }
        raise ResolverError(f"Network request failed: {exc}") from exc

    if not nickname:
        nickname = _extract_nickname(html)
    return {"uid": uid, "nickname": nickname, "url": f"https://{_SPACE_HOST}/{uid}"}


def _is_space_url(parsed) -> bool:
    hostname = parsed.hostname
    return bool(hostname) and hostname.lower() == _SPACE_HOST and parsed.path.startswith("/")


def _extract_url_from_text(text: str) -> str:
    candidate = text.strip()
    match = _URL_IN_TEXT_RE.search(candidate)
    if match:
        return match.group(0).rstrip(".,;:!?。！？）】)")
    return candidate


def _extract_uid_from_url(path: str) -> int | None:
    match = _UID_URL_RE.search(path)
    if not match:
        return None
    return int(match.group(1))


def _extract_uid_from_html(html: str) -> int | None:
    for pattern in (_UID_JSON_RE, _UID_HTML_RE):
        match = pattern.search(html)
        if match:
            return int(match.group(1))
    return None


def _extract_nickname(html: str) -> str | None:
    title = None
    title_match = _TITLE_RE.search(html)
    if title_match:
        title = title_match.group(1)
    else:
        og_match = _OG_TITLE_RE.search(html)
        if og_match:
            title = og_match.group(1)

    if not title:
        return None

    text = unescape(re.sub(r"\s+", " ", title)).strip()
    for suffix in (
        "的个人空间_哔哩哔哩",
        "的个人空间-哔哩哔哩视频",
        "的个人空间",
        "_哔哩哔哩",
        "-哔哩哔哩视频",
    ):
        if text.endswith(suffix):
            text = text[: -len(suffix)].strip()
            break

    if not text:
        return None

    blocked_names = {
        "验证码",
        "安全验证",
        "访问受限",
    }
    if text in blocked_names:
        return None

    return text


async def _fetch_nickname_by_uid(session: aiohttp.ClientSession, uid: int) -> str | None:
    api_url = f"https://api.bilibili.com/x/space/acc/info?mid={uid}&jsonp=jsonp"
    try:
        async with session.get(api_url) as response:
            if not 200 <= response.status < 300:
                return None
            payload = await response.json(content_type=None)
    except (aiohttp.ClientError, RuntimeError, ValueError, TypeError):
        return None

    if not isinstance(payload, dict):
        return None
    if payload.get("code") != 0:
        return None

    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    name = data.get("name")
    if not isinstance(name, str):
        return None
    name = name.strip()
    return name or None
