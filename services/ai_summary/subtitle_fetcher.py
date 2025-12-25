# -*- coding: utf-8 -*-
"""
字幕获取服务模块

从B站视频获取AI生成的字幕文本
"""

import logging
import re
from enum import Enum
from typing import Optional

import aiohttp
from bilibili_api import video
from bilibili_api.exceptions import ResponseCodeException

from config import build_bilibili_credential


class SubtitleErrorType(Enum):
    """字幕获取失败类型"""

    NONE = "none"  # 无错误
    INVALID_URL = "invalid_url"  # URL格式错误
    VIDEO_NOT_FOUND = "video_not_found"  # 视频不存在
    NO_SUBTITLE = "no_subtitle"  # 视频没有字幕
    COOKIE_EXPIRED = "cookie_expired"  # Cookie已过期/失效
    CREDENTIAL_ERROR = "credential_error"  # 凭证错误（未登录或权限不足）
    NETWORK_ERROR = "network_error"  # 网络错误
    DOWNLOAD_ERROR = "download_error"  # 字幕下载失败
    PARSE_ERROR = "parse_error"  # 字幕解析失败
    UNKNOWN = "unknown"  # 未知错误


class SubtitleFetcher:
    """B站字幕获取服务"""

    @staticmethod
    def format_timestamp(seconds: float) -> str:
        """将秒数格式化为 mm:ss 或 hh:mm:ss"""
        if seconds < 0:
            raise ValueError("seconds必须>=0")

        total_seconds = int(seconds)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    @classmethod
    def subtitle_body_to_text(cls, body: list) -> str:
        """将字幕 body 列表转换为带时间戳的纯文本（逐行）。

        输出格式：
        [mm:ss] 字幕内容
        """
        if not isinstance(body, list):
            raise ValueError("字幕body不是列表格式")

        lines = []
        for item in body:
            if not isinstance(item, dict):
                continue

            content = item.get("content")
            if not isinstance(content, str):
                continue

            content = content.strip()
            if not content:
                continue

            start = item.get("from")
            if isinstance(start, (int, float)):
                ts = cls.format_timestamp(float(start))
                lines.append(f"[{ts}] {content}")
            else:
                lines.append(content)

        return "\n".join(lines)

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # 记录最近一次失败原因，便于上层展示到推送里
        self.last_error: Optional[str] = None
        # 记录失败类型，便于上层判断是否需要重试或提示用户
        self.last_error_type: SubtitleErrorType = SubtitleErrorType.NONE

        # 初始化B站凭证（使用完整凭证，包含 sessdata, bili_jct, buvid3 等）
        self.credential = build_bilibili_credential()
        if self.credential:
            self.logger.info("已加载B站登录凭证")
        else:
            self.logger.warning("未配置B站凭证，某些字幕可能无法获取")

    def extract_bvid(self, video_url: str) -> Optional[str]:
        """
        从视频URL中提取BV号

        Args:
            video_url: B站视频URL

        Returns:
            BV号，如果解析失败返回None
        """
        try:
            # 匹配BV号
            bv_match = re.search(r"BV([a-zA-Z0-9]+)", video_url)
            if bv_match:
                self.last_error = None
                self.last_error_type = SubtitleErrorType.NONE
                return f"BV{bv_match.group(1)}"
            self.last_error = "无法从URL中提取BV号"
            self.last_error_type = SubtitleErrorType.INVALID_URL
            return None
        except Exception as e:
            self.last_error = str(e)
            self.last_error_type = SubtitleErrorType.INVALID_URL
            self.logger.error(f"提取BV号失败: {e}")
            return None

    def _classify_api_error(self, e: ResponseCodeException) -> SubtitleErrorType:
        """
        根据B站API错误码分类错误类型

        常见错误码:
        - -101: 账号未登录
        - -111: csrf校验失败
        - -400: 请求错误
        - -404: 视频不存在
        - -403: 权限不足
        - -352: 风控校验失败（Cookie可能失效）
        - -799: 请求过于频繁
        """
        code = e.code

        # 登录/凭证相关错误
        if code in (-101, -111, -352):
            return SubtitleErrorType.COOKIE_EXPIRED

        # 权限相关错误
        if code == -403:
            return SubtitleErrorType.CREDENTIAL_ERROR

        # 视频不存在
        if code == -404:
            return SubtitleErrorType.VIDEO_NOT_FOUND

        # 请求错误
        if code == -400:
            return SubtitleErrorType.INVALID_URL

        return SubtitleErrorType.UNKNOWN

    async def _fetch_subtitle_list(
        self, bvid: str, cid: int, aid: Optional[int] = None
    ) -> list:
        """
        获取字幕列表，优先使用 dm/view 接口（更可靠）

        Args:
            bvid: 视频BV号
            cid: 视频cid
            aid: 视频aid（可选）

        Returns:
            字幕列表，失败返回空列表
        """
        subtitles = []

        # 方法1: 使用 dm/view 接口（更可靠，能获取到 AI 字幕）
        if aid:
            try:
                dm_view_url = (
                    f"https://api.bilibili.com/x/v2/dm/view?type=1&oid={cid}&pid={aid}"
                )
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://www.bilibili.com/",
                }

                # 构建 cookies
                cookies = {}
                if self.credential:
                    if self.credential.sessdata:
                        cookies["SESSDATA"] = self.credential.sessdata
                    if self.credential.bili_jct:
                        cookies["bili_jct"] = self.credential.bili_jct
                    if self.credential.buvid3:
                        cookies["buvid3"] = self.credential.buvid3

                async with aiohttp.ClientSession(
                    cookies=cookies, headers=headers
                ) as session:
                    async with session.get(dm_view_url) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get("code") == 0:
                                subtitle_info = data.get("data", {}).get("subtitle", {})
                                subtitles = subtitle_info.get("subtitles", [])
                                if subtitles:
                                    self.logger.info(
                                        f"通过 dm/view 接口获取到 {len(subtitles)} 个字幕"
                                    )
                                    return subtitles
            except Exception as e:
                self.logger.warning(f"dm/view 接口获取字幕失败: {e}")

        # 方法2: 使用 bilibili-api 库的 get_subtitle 方法（备用）
        try:
            v = video.Video(bvid=bvid, credential=self.credential)
            subtitle_info = await v.get_subtitle(cid=cid)
            if subtitle_info and "subtitles" in subtitle_info:
                subtitles = subtitle_info.get("subtitles", [])
                if subtitles:
                    self.logger.info(
                        f"通过 bilibili-api 获取到 {len(subtitles)} 个字幕"
                    )
                    return subtitles
        except ResponseCodeException as e:
            error_type = self._classify_api_error(e)
            self.last_error_type = error_type
            if error_type == SubtitleErrorType.COOKIE_EXPIRED:
                self.last_error = (
                    f"B站Cookie已失效(错误码:{e.code})，请重新获取登录凭证"
                )
            elif error_type == SubtitleErrorType.CREDENTIAL_ERROR:
                self.last_error = (
                    f"权限不足，无法获取视频 {bvid} 的字幕（可能需要登录或大会员）"
                )
            else:
                self.last_error = f"获取字幕信息失败(错误码:{e.code}): {e.msg}"
            self.logger.warning(self.last_error)
        except Exception as e:
            self.logger.warning(f"bilibili-api 获取字幕失败: {e}")

        return subtitles

    async def fetch_subtitle(self, video_url: str) -> Optional[str]:
        """
        获取视频字幕文本

        Args:
            video_url: B站视频URL

        Returns:
            字幕文本内容（纯文本，包含时间戳行前缀），失败返回None
        """
        try:
            self.last_error = None
            self.last_error_type = SubtitleErrorType.NONE

            # 1. 解析BV号
            bvid = self.extract_bvid(video_url)
            if not bvid:
                self.logger.error(f"无法从URL中提取BV号: {video_url}")
                return None

            self.logger.info(f"开始获取视频字幕: {bvid}")

            # 2. 创建Video对象并获取视频信息以获得cid
            v = video.Video(bvid=bvid, credential=self.credential)

            try:
                video_info = await v.get_info()
            except ResponseCodeException as e:
                error_type = self._classify_api_error(e)
                self.last_error_type = error_type

                if error_type == SubtitleErrorType.COOKIE_EXPIRED:
                    self.last_error = (
                        f"B站Cookie已失效(错误码:{e.code})，请重新获取登录凭证"
                    )
                elif error_type == SubtitleErrorType.VIDEO_NOT_FOUND:
                    self.last_error = f"视频 {bvid} 不存在或已被删除"
                elif error_type == SubtitleErrorType.CREDENTIAL_ERROR:
                    self.last_error = f"权限不足，无法访问视频 {bvid}"
                else:
                    self.last_error = f"获取视频信息失败(错误码:{e.code}): {e.msg}"

                self.logger.error(self.last_error)
                return None

            if not video_info or "cid" not in video_info:
                self.last_error = f"无法获取视频 {bvid} 的cid"
                self.last_error_type = SubtitleErrorType.VIDEO_NOT_FOUND
                self.logger.error(self.last_error)
                return None

            cid = video_info["cid"]
            aid = video_info.get("aid")
            self.logger.info(f"获取到视频cid: {cid}, aid: {aid}")

            # 3. 获取字幕列表（优先使用 dm/view 接口，因为 player/v2 接口有时返回空）
            subtitles = await self._fetch_subtitle_list(bvid, cid, aid)

            if not subtitles:
                self.last_error = (
                    f"视频 {bvid} 字幕列表为空（UP主未开启AI字幕或视频无语音内容）"
                )
                self.last_error_type = SubtitleErrorType.NO_SUBTITLE
                self.logger.warning(self.last_error)
                return None

            # 4. 选择字幕（优先AI生成的中文字幕）
            selected_subtitle = None
            for sub in subtitles:
                lan = sub.get("lan", "")
                lan_doc = sub.get("lan_doc", "")

                # 优先选择AI生成的中文字幕
                if "ai" in lan.lower() or "ai" in lan_doc.lower():
                    selected_subtitle = sub
                    self.logger.info(f"选择AI生成字幕: {lan_doc}")
                    break

            # 如果没有AI字幕，选择第一个中文字幕
            if not selected_subtitle:
                for sub in subtitles:
                    lan = sub.get("lan", "")
                    if "zh" in lan.lower() or "中" in sub.get("lan_doc", ""):
                        selected_subtitle = sub
                        self.logger.info(f"选择中文字幕: {sub.get('lan_doc')}")
                        break

            # 如果还是没有，选择第一个
            if not selected_subtitle:
                selected_subtitle = subtitles[0]
                self.logger.info(f"选择第一个字幕: {selected_subtitle.get('lan_doc')}")

            # 5. 获取字幕URL并下载
            subtitle_url = selected_subtitle.get("subtitle_url")
            if not subtitle_url:
                self.last_error = "字幕URL为空"
                self.logger.error("字幕URL为空")
                return None

            # 如果URL是相对路径，补充完整
            if subtitle_url.startswith("//"):
                subtitle_url = "https:" + subtitle_url

            # 6. 下载字幕JSON
            subtitle_text = await self._download_subtitle(subtitle_url)
            if not subtitle_text:
                return None

            self.logger.info(
                f"成功获取视频 {bvid} 的字幕，长度: {len(subtitle_text)} 字符"
            )
            self.last_error = None
            self.last_error_type = SubtitleErrorType.NONE
            return subtitle_text

        except ResponseCodeException as e:
            # 捕获bilibili-api的API错误
            error_type = self._classify_api_error(e)
            self.last_error_type = error_type

            if error_type == SubtitleErrorType.COOKIE_EXPIRED:
                self.last_error = (
                    f"B站Cookie已失效(错误码:{e.code})，请重新获取登录凭证"
                )
            else:
                self.last_error = f"B站API错误(错误码:{e.code}): {e.msg}"

            self.logger.error(self.last_error)
            return None
        except aiohttp.ClientError as e:
            self.last_error = f"网络请求失败: {e}"
            self.last_error_type = SubtitleErrorType.NETWORK_ERROR
            self.logger.error(self.last_error)
            return None
        except Exception as e:
            self.last_error = str(e)
            self.last_error_type = SubtitleErrorType.UNKNOWN
            self.logger.error(f"获取字幕失败: {e}", exc_info=True)
            return None

    async def _download_subtitle(self, subtitle_url: str) -> Optional[str]:
        """
        下载并解析字幕JSON文件

        Args:
            subtitle_url: 字幕文件URL

        Returns:
            合并后的纯文本字幕（包含时间戳行前缀）
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    subtitle_url, timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status != 200:
                        self.last_error = f"下载字幕失败，状态码: {resp.status}"
                        self.last_error_type = SubtitleErrorType.DOWNLOAD_ERROR
                        self.logger.error(self.last_error)
                        return None

                    subtitle_data = await resp.json()

            # 解析字幕内容
            if "body" not in subtitle_data:
                self.last_error = "字幕数据格式错误，缺少body字段"
                self.last_error_type = SubtitleErrorType.PARSE_ERROR
                self.logger.error(self.last_error)
                return None

            body = subtitle_data["body"]
            if not isinstance(body, list):
                self.last_error = "字幕body不是列表格式"
                self.last_error_type = SubtitleErrorType.PARSE_ERROR
                self.logger.error(self.last_error)
                return None

            return self.subtitle_body_to_text(body)

        except aiohttp.ClientError as e:
            self.last_error = f"下载字幕网络错误: {e}"
            self.last_error_type = SubtitleErrorType.NETWORK_ERROR
            self.logger.error(self.last_error)
            return None
        except Exception as e:
            self.last_error = f"下载字幕失败: {e}"
            self.last_error_type = SubtitleErrorType.DOWNLOAD_ERROR
            self.logger.error(self.last_error)
            return None
