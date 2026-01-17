# -*- coding: utf-8 -*-
"""
B站动态监控服务模块

提供B站创作者动态监控和推送功能
"""

import asyncio
import json
import logging
import os
import random
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

from .bilibili_auth import BilibiliAuth
from .comment_fetcher import CommentFetcher


@dataclass
class Creator:
    """创作者信息"""

    uid: int
    name: str
    check_interval: int = 300  # 默认5分钟
    enable_comments: bool = False  # 是否启用评论获取
    comment_rules: List[Dict[str, Any]] = None  # 评论筛选规则列表（支持多规则）

    def __post_init__(self):
        """初始化默认值"""
        if self.comment_rules is None:
            self.comment_rules = []


class JsonState:
    """JSON文件状态管理器"""

    def __init__(self, path: str):
        self.path = path
        self.state: Dict[str, Any] = {}
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self.state = json.load(f)
            except Exception:
                self.state = {}
        else:
            self.state = {}

    def save(self) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def get_last_seen(self, uid: int) -> Optional[str]:
        return self.state.get(str(uid), {}).get("last_seen")

    def set_last_seen(self, uid: int, dynamic_id: str) -> None:
        entry = self.state.setdefault(str(uid), {})
        entry["last_seen"] = dynamic_id
        entry.setdefault("seen", []).append(dynamic_id)


class MonitorService:
    """B站动态监控服务"""

    # API配置
    BILI_SPACE_API = "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space"
    DYNAMIC_PC_URL = "https://t.bilibili.com/{dynamic_id}"
    VIDEO_PC_URL = "https://www.bilibili.com/video/{bvid}"

    STATE_PATH = os.path.join("data", "bilibili_state.json")
    CREATORS_PATH = os.path.join("data", "bilibili_creators.json")

    def __init__(self, feishu_bot=None, summarizer=None, cookie: Optional[str] = None):
        """
        初始化监控服务

        Args:
            feishu_bot: 飞书机器人实例
            summarizer: AI总结服务实例
            cookie: B站Cookie
        """
        self.feishu_bot = feishu_bot
        self.summarizer = summarizer
        self.cookie = cookie
        self.state = JsonState(self.STATE_PATH)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # 初始化B站认证管理
        self.bili_auth = BilibiliAuth()

        # 初始化评论获取服务
        self.comment_fetcher = None
        self._init_comment_fetcher()

    def _init_comment_fetcher(self) -> None:
        """初始化评论获取服务"""
        try:
            from bilibili_api import Credential

            from config import BILIBILI_CONFIG

            # 创建凭证（bilibili-api-python会自动处理WBI签名！）
            credential = None
            if BILIBILI_CONFIG.get("SESSDATA"):
                credential = Credential(
                    sessdata=BILIBILI_CONFIG.get("SESSDATA"),
                    bili_jct=BILIBILI_CONFIG.get("bili_jct"),
                    buvid3=BILIBILI_CONFIG.get("buvid3"),
                )
                self.logger.info("B站凭证创建成功（WBI签名将自动处理）")
            else:
                self.logger.warning("未配置SESSDATA，评论获取功能可能受限")

            self.comment_fetcher = CommentFetcher(credential=credential)
            self.logger.info("评论获取服务初始化成功")

        except Exception as e:
            self.logger.warning(f"评论获取服务初始化失败: {e}")
            self.comment_fetcher = None

    @staticmethod
    def get_publish_time(item: Dict[str, Any]) -> str:
        """获取动态的发布时间"""
        try:
            modules = item.get("modules", {})
            if not modules:
                return ""

            author = modules.get("module_author", {})
            if author and isinstance(author, dict):
                pub_ts = author.get("pub_ts")
                if isinstance(pub_ts, str):
                    pub_ts = int(pub_ts)
                if pub_ts:
                    dt = datetime.fromtimestamp(pub_ts)
                    return f"发布时间：{dt.strftime('%Y-%m-%d %H:%M:%S')}"

                pub_time = author.get("pub_time")
                if pub_time:
                    return f"发布时间：{pub_time}"

            return ""
        except Exception as e:
            logging.error(f"获取发布时间出错: {e}")
            return ""

    @staticmethod
    def get_publish_timestamp(item: Dict[str, Any]) -> int:
        """获取动态的发布时间戳（用于排序）"""
        try:
            modules = item.get("modules", {})
            if modules:
                author = modules.get("module_author", {})
                if author and isinstance(author, dict):
                    pub_ts = author.get("pub_ts")
                    if pub_ts:
                        return int(pub_ts)

            timestamp = item.get("timestamp")
            if timestamp:
                return int(timestamp)

            return 0
        except Exception:
            return 0

    @staticmethod
    def is_pinned_dynamic(item: Dict[str, Any]) -> bool:
        """检查动态是否为置顶动态"""
        try:
            modules = item.get("modules", {})
            if not modules:
                return False

            module_tag = modules.get("module_tag", {})
            if not module_tag:
                return False

            tag_text = module_tag.get("text", "")
            return tag_text == "置顶"
        except Exception:
            return False

    @staticmethod
    def parse_text_from_item(item: Dict[str, Any]) -> str:
        """从动态项解析文本内容"""
        try:
            modules = item.get("modules", {})
            if not modules:
                return ""

            dynamic = modules.get("module_dynamic")
            if not dynamic or not isinstance(dynamic, dict):
                return ""

            text_parts = []
            image_urls = []

            # 解析主要内容
            major = dynamic.get("major", {})
            if major and isinstance(major, dict):
                major_type = major.get("type", "")

                # 处理OPUS类型动态（图文混排）
                if major_type == "MAJOR_TYPE_OPUS":
                    opus = major.get("opus")
                    if opus and isinstance(opus, dict):
                        title = opus.get("title")
                        if title:
                            text_parts.append(f"**{title}**\n")

                        summary = opus.get("summary")
                        if summary and isinstance(summary, dict):
                            text = summary.get("text", "")
                            if text and isinstance(text, str):
                                text_parts.append(text.strip())

                        # 提取图片URL
                        pics = opus.get("pics", [])
                        for pic in pics:
                            if isinstance(pic, dict):
                                img_url = pic.get("url")
                                if img_url:
                                    image_urls.append(img_url)

                # 处理图片动态（draw类型）
                elif major_type == "MAJOR_TYPE_DRAW":
                    draw = major.get("draw", {})
                    if draw:
                        items = draw.get("items", [])
                        for item_data in items:
                            if isinstance(item_data, dict):
                                src = item_data.get("src")
                                if src:
                                    image_urls.append(src)

            # 如果major中没有文本，尝试从desc中获取
            if not text_parts:
                desc = dynamic.get("desc")
                if desc and isinstance(desc, dict):
                    rich_text_nodes = desc.get("rich_text_nodes", [])
                    if rich_text_nodes:
                        for node in rich_text_nodes:
                            if (
                                isinstance(node, dict)
                                and node.get("type") == "RICH_TEXT_NODE_TYPE_TEXT"
                            ):
                                text_content = node.get("text", "")
                                if text_content:
                                    text_parts.append(text_content)
                    else:
                        text = desc.get("text")
                        if text and isinstance(text, str):
                            text_parts.append(text.strip())

            # 构建最终的Markdown内容
            result_parts = []
            if text_parts:
                result_parts.append("".join(text_parts).strip())

            # 添加图片作为Markdown图片链接
            if image_urls:
                if result_parts:
                    result_parts.append("")
                for i, img_url in enumerate(image_urls, 1):
                    result_parts.append(f"![图片{i}]({img_url})")

            return "\n".join(result_parts) if result_parts else ""
        except Exception as e:
            logging.error(f"解析动态文本时出错: {e}")
            return ""

    @staticmethod
    def extract_video_info(item: Dict[str, Any]) -> Optional[Tuple[str, str]]:
        """从动态项提取视频信息"""
        dynamic = item.get("modules", {}).get("module_dynamic", {})
        major = dynamic.get("major", {})
        if not major:
            return None
        if major.get("type") in ("MAJOR_TYPE_ARCHIVE", "archive"):
            archive = major.get("archive", {})
            bvid = archive.get("bvid")
            title = archive.get("title") or ""
            if bvid:
                return bvid, title
        return None

    async def fetch_user_space_dynamics(
        self, session: aiohttp.ClientSession, uid: int, limit_recent: int = 20
    ) -> Dict[str, Any]:
        """
        获取用户空间动态

        Args:
            session: HTTP会话
            uid: 用户ID
            limit_recent: 限制获取最近的动态数量

        Returns:
            Dict: API响应数据
        """
        params = {
            "offset": "",
            "host_mid": str(uid),
            "timezone_offset": "-480",
            "platform": "web",
            "features": "itemOpusStyle,listOnlyfans,opusBigCover",
            "web_location": "333.1387",
        }

        # 导入统一配置的User-Agent
        from config import USER_AGENT

        headers = {
            "User-Agent": USER_AGENT,  # 使用配置的UA，与浏览器保持一致
            "Referer": f"https://space.bilibili.com/{uid}/dynamic",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Origin": "https://space.bilibili.com",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        }

        if self.cookie:
            headers["Cookie"] = self.cookie
        else:
            # 即使没有完整Cookie，也添加一些基础标识
            headers["Cookie"] = "buvid3=generated; b_nut=1234567890"

        async with session.get(
            self.BILI_SPACE_API, params=params, headers=headers, timeout=20
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()

            # 限制返回的动态数量
            if "data" in data and "items" in data["data"]:
                items = data["data"]["items"]
                if len(items) > limit_recent:
                    data["data"]["items"] = items[:limit_recent]

            return data

    async def process_creator(
        self, session: aiohttp.ClientSession, creator: Creator
    ) -> None:
        """
        处理单个创作者的动态

        Args:
            session: HTTP会话
            creator: 创作者信息
        """
        # 获取最近20个动态
        data = await self.fetch_user_space_dynamics(session, creator.uid, 20)

        # 调试：打印API响应
        self.logger.debug(
            f"API响应状态: code={data.get('code')}, message={data.get('message')}"
        )

        items = data.get("data", {}).get("items", [])
        if not items:
            # 检查是否有错误信息
            if data.get("code") != 0:
                error_msg = f"API返回错误: code={data.get('code')}, message={data.get('message')}"
                self.logger.warning(f"{creator.name} ({creator.uid}) - {error_msg}")
                # 发送API错误通知
                if self.feishu_bot:
                    try:
                        await self.feishu_bot.send_system_notification(
                            self.feishu_bot.LEVEL_WARNING,
                            "B站API请求失败",
                            f"获取创作者动态失败\n\n**创作者:** {creator.name}\n**UID:** {creator.uid}\n**错误代码:** {data.get('code')}\n**错误信息:** {data.get('message')}",
                        )
                    except Exception:
                        pass
            else:
                self.logger.info(
                    f"No items for {creator.name} ({creator.uid}) - 该用户可能没有发布动态"
                )
            return

        self.logger.debug(f"{creator.name}: 获取到 {len(items)} 个最近动态")

        # 按发布时间戳排序
        items.sort(key=self.get_publish_timestamp, reverse=True)

        last_seen = self.state.get_last_seen(creator.uid)
        if last_seen is None:
            # 首次运行，推送最新的3个动态（如果有的话）
            self.logger.info(f"首次监控 {creator.name}，将推送最新的几条动态")

            # 获取最近48小时内的动态，但最多推送3条
            current_time = time.time()
            time_window_hours = 48
            time_window_seconds = time_window_hours * 3600
            earliest_allowed_timestamp = current_time - time_window_seconds

            initial_items = []
            for item in items:
                if self.is_pinned_dynamic(item):
                    continue
                item_timestamp = self.get_publish_timestamp(item)
                if item_timestamp >= earliest_allowed_timestamp:
                    initial_items.append(item)
                    if len(initial_items) >= 3:  # 最多推送3条
                        break

            if initial_items:
                # 按时间顺序处理（从旧到新）
                initial_items.sort(key=self.get_publish_timestamp)

                self.logger.info(
                    f"首次运行：为 {creator.name} 推送 {len(initial_items)} 条最新动态"
                )

                for it in initial_items:
                    await self._process_dynamic_item(it, creator)

                # 设置最新的为已看过
                newest_processed = str(
                    initial_items[-1].get("id_str") or initial_items[-1].get("id")
                )
                self.state.set_last_seen(creator.uid, newest_processed)
                self.state.save()
            else:
                # 如果没有符合条件的动态，设置最新动态为已看过
                newest_id = items[0].get("id_str") or items[0].get("id")
                if newest_id:
                    self.state.set_last_seen(creator.uid, str(newest_id))
                    self.state.save()
                    self.logger.info(
                        f"首次运行：{creator.name} 没有最近48小时内的动态，已初始化状态"
                    )
            return

        # 找到上次看过的动态的时间戳
        last_seen_timestamp = 0
        last_seen_found = False
        for item in items:
            item_id = str(item.get("id_str") or item.get("id"))
            if item_id == last_seen:
                last_seen_timestamp = self.get_publish_timestamp(item)
                last_seen_found = True
                break

        # 如果找不到last_seen，更新为最新动态
        if not last_seen_found:
            newest_id = items[0].get("id_str") or items[0].get("id")
            if newest_id:
                self.state.set_last_seen(creator.uid, str(newest_id))
                self.state.save()
                self.logger.warning(
                    f"Last seen dynamic for {creator.name} not found. Updated to latest."
                )
            return

        # 收集新动态
        current_time = time.time()
        time_window_hours = 48
        time_window_seconds = time_window_hours * 3600
        earliest_allowed_timestamp = current_time - time_window_seconds

        new_items: List[Dict[str, Any]] = []

        for item in items:
            if self.is_pinned_dynamic(item):
                continue

            item_timestamp = self.get_publish_timestamp(item)

            if item_timestamp < earliest_allowed_timestamp:
                continue

            if item_timestamp > last_seen_timestamp:
                new_items.append(item)

        if not new_items:
            self.logger.debug(f"No new dynamics for {creator.name}")
            return

        # 按时间顺序处理
        new_items.sort(key=self.get_publish_timestamp)

        self.logger.info(f"Found {len(new_items)} new dynamics for {creator.name}")

        for it in new_items:
            await self._process_dynamic_item(it, creator)

        # 更新last_seen
        newest_processed = str(new_items[-1].get("id_str") or new_items[-1].get("id"))
        self.state.set_last_seen(creator.uid, newest_processed)
        self.state.save()

    async def _process_dynamic_item(
        self, item: Dict[str, Any], creator: Creator
    ) -> None:
        """处理单个动态项"""
        did = str(item.get("id_str") or item.get("id"))
        url = self.DYNAMIC_PC_URL.format(dynamic_id=did)
        vinfo = self.extract_video_info(item)

        if vinfo:
            # 处理视频动态
            await self._process_video_dynamic(item, vinfo, creator, url)
        else:
            # 处理普通动态
            await self._process_text_dynamic(item, creator, url)

    async def _process_video_dynamic(
        self,
        item: Dict[str, Any],
        vinfo: Tuple[str, str],
        creator: Creator,
        dynamic_url: str,
    ) -> None:
        """处理视频动态"""
        bvid, title = vinfo
        video_url = self.VIDEO_PC_URL.format(bvid=bvid)

        pub_time = self.get_publish_time(item)

        # 构建markdown内容
        markdown_content = (
            f"**{title}**\n\n[原视频链接]({video_url})\n[动态链接]({dynamic_url})"
        )

        # 🆕 评论获取功能
        comment_content = await self._fetch_video_comments(bvid, title, creator)
        if comment_content:
            markdown_content += f"\n\n{comment_content}"

        # AI总结
        summary_text = None
        try:
            if self.summarizer is not None:
                ok, message, links, contents = await self.summarizer.summarize_videos(
                    [video_url]
                )
                if ok and contents and contents[0]:
                    summary_text = f"**AI 总结**\n\n{contents[0]}"
                    if links and links[0]:
                        summary_text += f"\n\n[查看完整总结]({links[0]})"
                elif ok and links:
                    summary_text = f"[AI总结链接]({links[0]})"
                else:
                    summary_text = f"AI总结失败：{message}"
        except Exception as e:
            self.logger.error(f"AI总结异常: {e}")
            summary_text = f"AI总结异常：{str(e)}"

        # 添加总结和时间
        if summary_text:
            markdown_content += f"\n\n{summary_text}"
        if pub_time:
            markdown_content += f"\n\n{pub_time}"

        # 发送到飞书
        if self.feishu_bot:
            await self.feishu_bot.send_card_message(
                creator.name, "哔哩哔哩", markdown_content
            )

    async def _fetch_video_comments(
        self, bvid: str, video_title: str, creator: Creator
    ) -> Optional[str]:
        """
        获取视频评论并格式化

        Args:
            bvid: 视频BV号
            video_title: 视频标题
            creator: 创作者配置（包含评论筛选条件）

        Returns:
            格式化后的评论内容，如果没有符合条件的评论则返回None
        """
        # 检查是否启用评论获取
        if not creator.enable_comments:
            return None

        # 检查评论获取服务是否可用
        if not self.comment_fetcher:
            self.logger.warning("评论获取服务未初始化，跳过评论获取")
            return None

        try:
            self.logger.info(f"开始获取视频 {bvid} 的评论（博主: {creator.name}）")

            # 检查是否有配置规则
            if not creator.comment_rules:
                self.logger.info(f"未配置评论规则，跳过（博主: {creator.name}）")
                return None

            # 使用多规则获取评论
            comments = await self.comment_fetcher.fetch_hot_comments_with_rules(
                bvid=bvid,
                rules=creator.comment_rules,
                max_count=10,  # 最多获取10条评论（多规则可能产生更多结果）
            )

            if not comments:
                self.logger.info(f"未找到符合条件的评论（博主: {creator.name}）")
                return None

            # 构建视频链接
            video_url = f"https://www.bilibili.com/video/{bvid}/"

            # 格式化评论（包含视频链接）
            comment_section = "---\n\n### 🔥 精选评论\n\n"
            comment_section += f"**视频**: {video_title}\n\n"
            comment_section += f"🔗 [点击查看原视频]({video_url})\n\n"
            comment_section += "---\n\n"

            for idx, comm in enumerate(comments, 1):
                comment_text = self.comment_fetcher.format_comment_for_display(comm)
                comment_section += f"**评论 {idx}:**\n\n{comment_text}\n\n"

            self.logger.info(f"成功获取 {len(comments)} 条符合条件的评论")
            return comment_section

        except Exception as e:
            self.logger.error(f"获取视频评论失败: {e}", exc_info=True)
            return None

    async def _process_text_dynamic(
        self, item: Dict[str, Any], creator: Creator, url: str
    ) -> None:
        """处理文字动态"""
        text = self.parse_text_from_item(item)
        if not text:
            text = "(无文本内容)"

        pub_time = self.get_publish_time(item)

        # 构建markdown内容
        markdown_content = text
        if pub_time:
            markdown_content = f"{text}\n\n{pub_time}"

        markdown_content += f"\n\n[查看原动态]({url})"

        # 发送到飞书
        if self.feishu_bot:
            await self.feishu_bot.send_card_message(
                creator.name, "哔哩哔哩", markdown_content
            )

    async def monitor_single_creator(
        self, session: aiohttp.ClientSession, creator: Creator
    ) -> None:
        """监控单个创作者的独立任务"""
        while True:
            try:
                self.logger.info(
                    f"开始检查创作者 {creator.name} (UID: {creator.uid}) 的动态"
                )
                await self.process_creator(session, creator)

                # 添加随机抖动
                jitter = random.uniform(0.8, 1.2)
                sleep_time = creator.check_interval * jitter

                next_check = sleep_time / 60
                self.logger.info(
                    f"创作者 {creator.name} 下次检查时间: {next_check:.1f} 分钟后"
                )

                await asyncio.sleep(sleep_time)

            except Exception as e:
                self.logger.error(f"监控创作者 {creator.name} 时出错: {e}")
                # 发送监控异常通知
                if self.feishu_bot:
                    try:
                        await self.feishu_bot.send_system_notification(
                            self.feishu_bot.LEVEL_ERROR,
                            "创作者监控异常",
                            f"监控创作者时遇到异常\n\n**创作者:** {creator.name}\n**UID:** {creator.uid}\n**错误信息:**\n```\n{str(e)}\n```\n\n将在60秒后重试",
                        )
                    except Exception:
                        pass
                await asyncio.sleep(60)

    async def start_monitoring(
        self, creators: List[Creator], once: bool = False
    ) -> None:
        """
        启动监控

        Args:
            creators: 创作者列表
            once: 是否只运行一次
        """
        # 自动检查并刷新Cookie（如果需要且有refresh_token）
        if self.cookie:
            self.logger.info("检查Cookie是否需要刷新...")
            refreshed_cookie = await self.bili_auth.auto_refresh_if_needed(self.cookie)
            if refreshed_cookie != self.cookie:
                self.logger.info("Cookie已自动刷新")
                self.cookie = refreshed_cookie
                # TODO: 更新到config或.env文件
            else:
                self.logger.info("Cookie无需刷新")

        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            if once:
                # 一次性检查模式
                for c in creators:
                    await self.process_creator(session, c)
            else:
                # 持续监控模式
                self.logger.info(f"启动持续监控模式，共 {len(creators)} 个创作者")

                tasks = []
                for i, creator in enumerate(creators):
                    initial_delay = i * 30  # 每个创作者间隔30秒启动

                    async def delayed_monitor(creator, delay):
                        if delay > 0:
                            self.logger.info(
                                f"创作者 {creator.name}: 将在 {delay} 秒后开始监控"
                            )
                            await asyncio.sleep(delay)
                        await self.monitor_single_creator(session, creator)

                    task = asyncio.create_task(delayed_monitor(creator, initial_delay))
                    tasks.append(task)

                try:
                    await asyncio.gather(*tasks)
                except KeyboardInterrupt:
                    self.logger.info("收到停止信号，正在关闭监控...")
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)

    @staticmethod
    def load_creators_from_file(path: str = CREATORS_PATH) -> List[Creator]:
        """从文件加载创作者列表"""
        os.makedirs(os.path.dirname(path), exist_ok=True)

        default = [
            {"uid": 11473291, "name": "笨笨的芝菜", "check_interval": 300},
            {"uid": 550494308, "name": "卢本圆复盘", "check_interval": 300},
        ]

        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(default, f, ensure_ascii=False, indent=2)

        try:
            with open(path, "r", encoding="utf-8") as f:
                items = json.load(f)
            creators = []
            for i in items:
                creator = Creator(
                    uid=int(i["uid"]),
                    name=str(i["name"]),
                    check_interval=int(i.get("check_interval", 300)),
                    enable_comments=bool(i.get("enable_comments", False)),
                    comment_rules=i.get("comment_rules", []),
                )
                creators.append(creator)
            return creators
        except Exception:
            return [
                Creator(
                    uid=i["uid"],
                    name=i["name"],
                    check_interval=i.get("check_interval", 300),
                    enable_comments=False,
                    comment_rules=[],
                )
                for i in default
            ]
