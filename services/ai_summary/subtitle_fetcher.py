# -*- coding: utf-8 -*-
"""
字幕获取服务模块

从B站视频获取AI生成的字幕文本
"""

import logging
import re
from typing import Optional

import aiohttp
from bilibili_api import Credential, video

from config import BILIBILI_CONFIG


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

        # 初始化B站凭证（如果配置了的话）
        self.credential = None
        sessdata = BILIBILI_CONFIG.get("SESSDATA")
        if sessdata:
            self.credential = Credential(sessdata=sessdata)
            self.logger.info("已加载B站登录凭证")
        else:
            self.logger.warning("未配置B站SESSDATA，某些字幕可能无法获取")

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
                return f"BV{bv_match.group(1)}"
            return None
        except Exception as e:
            self.logger.error(f"提取BV号失败: {e}")
            return None

    async def fetch_subtitle(self, video_url: str) -> Optional[str]:
        """
        获取视频字幕文本

        Args:
            video_url: B站视频URL

        Returns:
            字幕文本内容（纯文本，包含时间戳行前缀），失败返回None
        """
        try:
            # 1. 解析BV号
            bvid = self.extract_bvid(video_url)
            if not bvid:
                self.logger.error(f"无法从URL中提取BV号: {video_url}")
                return None

            self.logger.info(f"开始获取视频字幕: {bvid}")

            # 2. 创建Video对象并获取视频信息以获得cid
            v = video.Video(bvid=bvid, credential=self.credential)
            video_info = await v.get_info()
            if not video_info or "cid" not in video_info:
                self.logger.error(f"无法获取视频 {bvid} 的cid")
                return None

            cid = video_info["cid"]
            self.logger.info(f"获取到视频cid: {cid}")

            # 3. 传入cid参数获取字幕
            subtitle_info = await v.get_subtitle(cid=cid)

            if not subtitle_info or "subtitles" not in subtitle_info:
                self.logger.warning(f"视频 {bvid} 没有可用的字幕")
                return None

            subtitles = subtitle_info["subtitles"]
            if not subtitles:
                self.logger.warning(f"视频 {bvid} 字幕列表为空")
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
            return subtitle_text

        except Exception as e:
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
                        self.logger.error(f"下载字幕失败，状态码: {resp.status}")
                        return None

                    subtitle_data = await resp.json()

            # 解析字幕内容
            if "body" not in subtitle_data:
                self.logger.error("字幕数据格式错误，缺少body字段")
                return None

            body = subtitle_data["body"]
            if not isinstance(body, list):
                self.logger.error("字幕body不是列表格式")
                return None

            return self.subtitle_body_to_text(body)

        except Exception as e:
            self.logger.error(f"下载字幕失败: {e}")
            return None
