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
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from bilibili_api import user
from bilibili_api.comment import CommentResourceType

from config import build_bilibili_credential

from .comment_fetcher import CommentFetcher


class ConfigFileWatcher:
    """配置文件监控器，用于检测文件变化并触发热重载"""

    def __init__(self, file_path: str, check_interval: int = 600):
        """
        初始化配置文件监控器

        Args:
            file_path: 要监控的文件路径
            check_interval: 检查间隔（秒），默认10秒
        """
        self.file_path = file_path
        self.check_interval = check_interval
        self.logger = logging.getLogger(f"{__name__}.ConfigFileWatcher")
        self._last_mtime: Optional[float] = None
        self._last_content_hash: Optional[str] = None
        self._running = False

    def _get_file_info(self) -> Tuple[Optional[float], Optional[str]]:
        """获取文件的修改时间和内容哈希"""
        try:
            if not os.path.exists(self.file_path):
                return None, None
            mtime = os.path.getmtime(self.file_path)
            with open(self.file_path, "r", encoding="utf-8") as f:
                content = f.read()
            # 使用简单的内容哈希来检测实际变化
            content_hash = str(hash(content))
            return mtime, content_hash
        except Exception as e:
            self.logger.warning(f"读取配置文件信息失败: {e}")
            return None, None

    def initialize(self) -> None:
        """初始化文件状态（记录当前状态作为基准）"""
        self._last_mtime, self._last_content_hash = self._get_file_info()
        self.logger.info(f"配置文件监控已初始化: {self.file_path}")

    def check_for_changes(self) -> bool:
        """
        检查文件是否有变化

        Returns:
            bool: 如果文件内容有变化返回 True
        """
        current_mtime, current_hash = self._get_file_info()

        # 文件不存在或读取失败
        if current_mtime is None:
            return False

        # 首次检查
        if self._last_mtime is None:
            self._last_mtime = current_mtime
            self._last_content_hash = current_hash
            return False

        # 检查修改时间和内容哈希
        if current_mtime != self._last_mtime or current_hash != self._last_content_hash:
            self.logger.info(
                f"检测到配置文件变化: mtime {self._last_mtime} -> {current_mtime}"
            )
            self._last_mtime = current_mtime
            self._last_content_hash = current_hash
            return True

        return False


@dataclass
class Creator:
    """创作者信息"""

    uid: int
    name: str
    check_interval: int = 300  # 默认5分钟
    enable_comments: bool = False  # 是否启用评论获取
    comment_rules: List[Dict[str, Any]] = None  # 评论筛选规则列表（支持多规则）
    feishu_channel: Optional[str] = (
        None  # 可选：指定此创作者消息推送通道（例如 webhook:group1）
    )

    # 可选：使用 cron 表达式（5段）定义运行时间；支持多个表达式
    # 示例：
    # - "*/2 10-11 * * *"  (10-11点每2分钟)
    # - "*/2 15-16 * * *"  (15-16点每2分钟)
    # - "0 11 * * *"       (每天11:00)
    crons: Optional[List[str]] = None

    # 可选：每次触发后增加随机延迟（秒），用于错峰与降低风控
    jitter_seconds: int = 0

    def __post_init__(self):
        """初始化默认值"""
        if self.comment_rules is None:
            self.comment_rules = []
        if self.crons is None:
            self.crons = []


class JsonState:
    """JSON文件状态管理器（运行时状态，不属于用户配置）"""

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
        entry["last_seen"] = str(dynamic_id)

    def get_pinned_comment_fingerprint(
        self, uid: int, dynamic_id: str
    ) -> Optional[str]:
        entry = self.state.get(str(uid), {})
        pinned = entry.get("pinned_comments", {})
        if not isinstance(pinned, dict):
            return None
        return pinned.get(str(dynamic_id))

    def set_pinned_comment_fingerprint(
        self, uid: int, dynamic_id: str, fingerprint: str
    ) -> None:
        entry = self.state.setdefault(str(uid), {})
        pinned = entry.setdefault("pinned_comments", {})
        if not isinstance(pinned, dict):
            entry["pinned_comments"] = {}
            pinned = entry["pinned_comments"]
        pinned[str(dynamic_id)] = str(fingerprint)

        # 控制体积：最多保留 50 条最近记录（按插入顺序淘汰最早的）
        if len(pinned) > 50:
            extra = len(pinned) - 50
            for k in list(pinned.keys())[:extra]:
                pinned.pop(k, None)


class MonitorService:
    """B站动态监控服务"""

    DYNAMIC_PC_URL = "https://t.bilibili.com/{dynamic_id}"
    VIDEO_PC_URL = "https://www.bilibili.com/video/{bvid}"

    # 运行时状态文件：只用于去重/断点续跑，已在 .gitignore 忽略
    STATE_PATH = os.path.join("data", "bilibili_state.json")
    CREATORS_PATH = os.path.join("data", "bilibili_creators.json")

    _SCHEDULER_TIMEZONE = "Asia/Shanghai"

    # 动态基础信息里的 comment_type -> bilibili-api-python CommentResourceType
    _COMMENT_TYPE_TO_RESOURCE: Dict[int, CommentResourceType] = {
        1: CommentResourceType.VIDEO,
        11: CommentResourceType.DYNAMIC_DRAW,
        17: CommentResourceType.DYNAMIC,
    }

    # 凭证刷新间隔（秒）：每6小时检查一次
    _CREDENTIAL_REFRESH_INTERVAL = 6 * 3600

    def __init__(self, feishu_bot=None, summarizer=None, cookie: Optional[str] = None):
        """
        初始化监控服务

        Args:
            feishu_bot: 飞书机器人实例
            summarizer: AI总结服务实例
            cookie: 兼容旧参数（已不再使用，凭证改由 bilibili-api-python 管理）
        """
        self.feishu_bot = feishu_bot
        self.summarizer = summarizer
        self.cookie = cookie
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        self.state = JsonState(self.STATE_PATH)

        # 是否允许在启动/首次缺少 last_seen 时补发（默认关闭：避免重启刷屏）
        self._allow_backfill_on_start = False

        # 创建统一凭证（依赖 config.py 中的环境变量）
        self.credential = build_bilibili_credential()

        # 上次凭证刷新时间
        self._last_credential_refresh: float = 0

        # 初始化评论获取服务
        self.comment_fetcher = None
        self._init_comment_fetcher()

    def _init_comment_fetcher(self) -> None:
        """初始化评论获取服务"""
        try:
            if not self.credential:
                self.logger.warning("未配置SESSDATA，评论获取功能可能受限")
            self.comment_fetcher = CommentFetcher(credential=self.credential)
            self.logger.info("评论获取服务初始化成功")
        except Exception as e:
            self.logger.warning(f"评论获取服务初始化失败: {e}")
            self.comment_fetcher = None

    async def _check_and_refresh_credential(self) -> bool:
        """检查并刷新凭证（如果需要）

        静默刷新，不发送通知。只在日志中记录。

        Returns:
            bool: 凭证是否有效
        """
        if not self.credential:
            return False

        current_time = time.time()

        # 如果距离上次刷新不足间隔时间，跳过检查
        if (
            current_time - self._last_credential_refresh
            < self._CREDENTIAL_REFRESH_INTERVAL
        ):
            return True

        try:
            # 检查是否需要刷新（即将过期）
            need_refresh = await self.credential.check_refresh()

            if need_refresh:
                self.logger.info("凭证即将过期，开始刷新...")
                await self.credential.refresh()
                self.logger.info("凭证刷新成功")

            self._last_credential_refresh = current_time
            return True

        except Exception as e:
            self.logger.warning(f"凭证刷新失败: {e}")
            # 不发送通知，等获取动态失败时自然会知道
            return False

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
                if pub_ts:
                    dt = datetime.fromtimestamp(
                        int(pub_ts), tz=timezone(timedelta(hours=8))
                    )
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

                # 处理直播通知/直播推荐（常见：开播提醒）
                if major_type in (
                    "MAJOR_TYPE_LIVE_RCMD",
                    "MAJOR_TYPE_LIVE",
                    "live_rcmd",
                    "LIVE_RCMD",
                ) or (
                    "live_rcmd" in major and isinstance(major.get("live_rcmd"), dict)
                ):
                    live = major.get("live_rcmd") or major.get("live")
                    if live and isinstance(live, dict):
                        title = live.get("title") or live.get("room_title")
                        if title and isinstance(title, str):
                            text_parts.append(f"**📺 开播通知：{title.strip()}**\n")
                        else:
                            text_parts.append("**📺 开播通知**\n")

                        uname = live.get("uname") or live.get("user_name")
                        if uname and isinstance(uname, str):
                            text_parts.append(f"主播：{uname.strip()}\n")

                        jump_url = live.get("jump_url") or live.get("link")
                        if jump_url and isinstance(jump_url, str):
                            text_parts.append(f"[进入直播间]({jump_url})")

                        cover = live.get("cover") or live.get("cover_url")
                        if cover and isinstance(cover, str):
                            image_urls.append(cover)

                # 处理OPUS类型动态（图文混排）
                elif major_type == "MAJOR_TYPE_OPUS":
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

                # 处理视频/投稿类动态（archive）
                elif major_type in ("MAJOR_TYPE_ARCHIVE", "archive"):
                    archive = major.get("archive", {})
                    if archive and isinstance(archive, dict):
                        title = archive.get("title")
                        if title and isinstance(title, str):
                            text_parts.append(f"**{title.strip()}**\n")
                        jump_url = archive.get("jump_url") or archive.get("url")
                        if jump_url and isinstance(jump_url, str):
                            text_parts.append(f"[查看视频]({jump_url})")
                        cover = archive.get("cover")
                        if cover and isinstance(cover, str):
                            image_urls.append(cover)

                # 处理文章/专栏
                elif major_type in ("MAJOR_TYPE_ARTICLE", "ARTICLE", "article") or (
                    "article" in major and isinstance(major.get("article"), dict)
                ):
                    article = major.get("article")
                    if article and isinstance(article, dict):
                        title = article.get("title")
                        if title and isinstance(title, str):
                            text_parts.append(f"**📰 {title.strip()}**\n")
                        desc = article.get("desc") or article.get("summary")
                        if desc and isinstance(desc, str):
                            text_parts.append(desc.strip())
                        jump_url = article.get("jump_url") or article.get("url")
                        if jump_url and isinstance(jump_url, str):
                            text_parts.append(f"\n[查看文章]({jump_url})")
                        cover = article.get("covers")
                        if (
                            isinstance(cover, list)
                            and cover
                            and isinstance(cover[0], str)
                        ):
                            image_urls.append(cover[0])

                # 处理番剧/PGC
                elif major_type in ("MAJOR_TYPE_PGC", "PGC", "pgc") or (
                    "pgc" in major and isinstance(major.get("pgc"), dict)
                ):
                    pgc = major.get("pgc")
                    if pgc and isinstance(pgc, dict):
                        title = pgc.get("title")
                        if title and isinstance(title, str):
                            text_parts.append(f"**🎬 {title.strip()}**\n")
                        desc = pgc.get("desc")
                        if desc and isinstance(desc, str):
                            text_parts.append(desc.strip())
                        jump_url = pgc.get("jump_url") or pgc.get("url")
                        if jump_url and isinstance(jump_url, str):
                            text_parts.append(f"\n[查看详情]({jump_url})")
                        cover = pgc.get("cover")
                        if cover and isinstance(cover, str):
                            image_urls.append(cover)

                # 其他带卡片的动态类型：尽量从 major 子结构抽取 title/jump_url/cover
                # 用于兜底覆盖：直播预约卡片、合集、音乐、商品等（结构通常包含 title/jump_url/cover）
                if not text_parts:
                    for key in (
                        "live_rcmd",
                        "live",
                        "ugc_season",
                        "common",
                        "music",
                        "goods",
                        "reserve",
                    ):
                        card = major.get(key)
                        if isinstance(card, dict):
                            title = card.get("title")
                            if isinstance(title, str) and title.strip():
                                text_parts.append(f"**{title.strip()}**\n")
                            jump_url = card.get("jump_url") or card.get("url")
                            if isinstance(jump_url, str) and jump_url.strip():
                                text_parts.append(f"[查看详情]({jump_url.strip()})")
                            cover = card.get("cover")
                            if isinstance(cover, str) and cover.strip():
                                image_urls.append(cover.strip())
                            break

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
    def _collect_badge_texts(obj: Any) -> List[str]:
        texts: List[str] = []
        if isinstance(obj, dict):
            badge = obj.get("badge")
            if isinstance(badge, dict):
                t = badge.get("text")
                if isinstance(t, str) and t:
                    texts.append(t)

            for v in obj.values():
                texts.extend(MonitorService._collect_badge_texts(v))

        elif isinstance(obj, list):
            for v in obj:
                texts.extend(MonitorService._collect_badge_texts(v))

        return texts

    @staticmethod
    def is_charge_dynamic(item: Dict[str, Any]) -> bool:
        """判断是否为“充电/充电专属/onlyfans”动态。

        依据 deepwiki 对 bilibili-api-python 的说明：优先检查动态结构中的 badge 文本与 onlyfans 字段。
        """

        # 0) 优先检查 basic 层级的充电/粉丝专属标记（最直接）
        basic = item.get("basic", {})
        if isinstance(basic, dict):
            for key, val in basic.items():
                key_l = str(key).lower()
                if any(
                    x in key_l for x in ("onlyfans", "charge", "upower", "fans_only")
                ):
                    if val is True:
                        return True
                    if isinstance(val, str) and val:
                        return True

        modules = item.get("modules", {})
        if not isinstance(modules, dict):
            return False

        dynamic = modules.get("module_dynamic", {})
        if not isinstance(dynamic, dict):
            return False

        # 1) additional.type 里包含 onlyfans/charge/upower 等
        additional = dynamic.get("additional")
        if isinstance(additional, dict):
            t = additional.get("type")
            if isinstance(t, str):
                tl = t.lower()
                if "onlyfans" in tl or "charge" in tl or "upower" in tl:
                    return True
            # 部分结构可能直接给 onlyfans 字段
            if "onlyfans" in additional:
                return True

        major = dynamic.get("major")
        if isinstance(major, dict):
            mt = major.get("type")
            if isinstance(mt, str):
                mtl = mt.lower()
                if "onlyfans" in mtl or "charge" in mtl or "upower" in mtl:
                    return True

        # 2) 扫描 major/opus/archive 等的 badge.text 是否含“充电”
        badge_texts = MonitorService._collect_badge_texts(dynamic)
        if any(("充电" in t) for t in badge_texts):
            return True

        # 3) 兜底：扫描整个 item 的 badge
        all_badges = MonitorService._collect_badge_texts(item)
        return any(("充电" in t) for t in all_badges)

    def _get_comment_thread_info(
        self, item: Dict[str, Any]
    ) -> Optional[Tuple[int, CommentResourceType]]:
        basic = item.get("basic", {})
        if not isinstance(basic, dict):
            return None

        oid_str = basic.get("comment_id_str") or basic.get("rid_str")
        if not oid_str or not isinstance(oid_str, str) or not oid_str.isdigit():
            return None

        ct = basic.get("comment_type")
        if isinstance(ct, str):
            if not ct.isdigit():
                return None
            ct_int = int(ct)
        elif isinstance(ct, int):
            ct_int = ct
        else:
            return None

        resource = self._COMMENT_TYPE_TO_RESOURCE.get(ct_int)
        if resource is None:
            return None

        return int(oid_str), resource

    def _pinned_comment_fingerprint(self, pinned: Optional[Dict[str, Any]]) -> str:
        if not pinned or not isinstance(pinned, dict):
            return ""
        rpid = pinned.get("rpid")
        if rpid is None:
            rpid = pinned.get("rpid_str")
        if rpid is None:
            return ""
        return str(rpid)

    async def _check_recent_pinned_comments(
        self, creator: Creator, items: List[Dict[str, Any]]
    ) -> None:
        """检查近期动态是否出现新的置顶评论。"""

        if not self.comment_fetcher:
            return

        # 方案 A：enable_comments 同时控制置顶评论监控与视频精选评论
        if not creator.enable_comments:
            return

        current_time = time.time()
        earliest_allowed_timestamp = current_time - 48 * 3600

        candidates: List[Dict[str, Any]] = []
        for it in items:
            ts = self.get_publish_timestamp(it)
            if ts and ts >= earliest_allowed_timestamp:
                candidates.append(it)
                if len(candidates) >= 5:
                    break

        if not candidates:
            return

        changed = False

        for it in candidates:
            dynamic_id = str(it.get("id_str") or it.get("id"))
            if not dynamic_id:
                continue

            thread = self._get_comment_thread_info(it)
            if thread is None:
                continue

            oid, resource = thread
            pinned = await self.comment_fetcher.fetch_upper_pinned_comment(
                oid=oid, type_=resource
            )
            fp = self._pinned_comment_fingerprint(pinned)
            prev = self.state.get_pinned_comment_fingerprint(creator.uid, dynamic_id)

            # 首次见到该动态：只初始化，不推送（避免重启刷屏）
            if prev is None:
                self.state.set_pinned_comment_fingerprint(creator.uid, dynamic_id, fp)
                changed = True
                continue

            # 出现新的置顶评论：prev 为空，fp 非空；或 rpid 发生变化
            if fp and fp != prev:
                await self._push_pinned_comment_update(
                    creator=creator,
                    item=it,
                    pinned_comment=pinned,
                )
                self.state.set_pinned_comment_fingerprint(creator.uid, dynamic_id, fp)
                changed = True
                continue

            # 置顶被取消/清空：只更新状态，不推送
            if (not fp) and fp != prev:
                self.state.set_pinned_comment_fingerprint(creator.uid, dynamic_id, fp)
                changed = True

        if changed:
            self.state.save()

    async def _push_pinned_comment_update(
        self, creator: Creator, item: Dict[str, Any], pinned_comment: Dict[str, Any]
    ) -> None:
        if not self.feishu_bot:
            return

        did = str(item.get("id_str") or item.get("id"))
        url = self.DYNAMIC_PC_URL.format(dynamic_id=did)

        title = "（无文本内容）"
        vinfo = self.extract_video_info(item)
        if vinfo:
            _, video_title = vinfo
            if video_title:
                title = video_title
        else:
            text = self.parse_text_from_item(item)
            if text:
                title = text.split("\n", 1)[0].strip() or title

        pinned_md = self.comment_fetcher.format_comment_for_display(pinned_comment)

        charge_tag = ""
        if self.is_charge_dynamic(item):
            charge_tag = "【充电】"

        markdown_content = (
            f"**{charge_tag}动态：** {title}\n\n"
            f"---\n\n{pinned_md}\n\n---\n\n"
            f"[查看原动态]({url})"
        )

        await self.feishu_bot.send_card_message(
            creator.name,
            "哔哩哔哩",
            markdown_content,
            channel=creator.feishu_channel,
            addition_title="置顶评论更新",
        )

    @staticmethod
    def _parse_orig_dynamic(item: Dict[str, Any]) -> Optional[str]:
        """解析转发动态中的原动态内容

        转发动态的结构：item["orig"] 包含被转发的原动态
        """
        orig = item.get("orig")
        if not orig or not isinstance(orig, dict):
            return None

        result_parts = []

        # 获取原动态作者
        orig_modules = orig.get("modules", {})
        if orig_modules:
            author = orig_modules.get("module_author", {})
            if author and isinstance(author, dict):
                name = author.get("name")
                if name:
                    result_parts.append(f"**@{name}**")

        # 获取原动态的动态ID用于生成链接
        orig_id = orig.get("id_str") or orig.get("id")

        # 解析原动态内容
        orig_dynamic = orig_modules.get("module_dynamic", {})
        if orig_dynamic and isinstance(orig_dynamic, dict):
            # 尝试从 desc 获取文本
            desc = orig_dynamic.get("desc")
            if desc and isinstance(desc, dict):
                text = desc.get("text")
                if text and isinstance(text, str):
                    result_parts.append(text.strip())

            # 尝试从 major 获取内容（视频/文章等）
            major = orig_dynamic.get("major")
            if major and isinstance(major, dict):
                major_type = major.get("type", "")

                # 视频
                if major_type in ("MAJOR_TYPE_ARCHIVE", "archive"):
                    archive = major.get("archive", {})
                    if archive:
                        title = archive.get("title")
                        if title:
                            result_parts.append(f"📺 **{title}**")
                        bvid = archive.get("bvid")
                        if bvid:
                            video_url = f"https://www.bilibili.com/video/{bvid}"
                            result_parts.append(f"[查看视频]({video_url})")

                # 文章
                elif major_type in ("MAJOR_TYPE_ARTICLE", "article"):
                    article = major.get("article", {})
                    if article:
                        title = article.get("title")
                        if title:
                            result_parts.append(f"📰 **{title}**")
                        jump_url = article.get("jump_url")
                        if jump_url:
                            if jump_url.startswith("//"):
                                jump_url = "https:" + jump_url
                            result_parts.append(f"[查看文章]({jump_url})")

                # OPUS 图文
                elif major_type == "MAJOR_TYPE_OPUS":
                    opus = major.get("opus", {})
                    if opus:
                        title = opus.get("title")
                        if title:
                            result_parts.append(f"**{title}**")
                        summary = opus.get("summary", {})
                        if summary:
                            text = summary.get("text")
                            if text:
                                result_parts.append(text.strip())

                # 直播
                elif major_type in ("MAJOR_TYPE_LIVE_RCMD", "MAJOR_TYPE_LIVE"):
                    live = major.get("live_rcmd") or major.get("live", {})
                    if live:
                        title = live.get("title") or live.get("room_title")
                        if title:
                            result_parts.append(f"📺 **直播：{title}**")
                        jump_url = live.get("jump_url") or live.get("link")
                        if jump_url:
                            result_parts.append(f"[进入直播间]({jump_url})")

                # 通用卡片类型兜底
                if not any("查看" in p or "进入" in p for p in result_parts):
                    for key in ("common", "ugc_season", "music", "pgc"):
                        card = major.get(key)
                        if isinstance(card, dict):
                            title = card.get("title")
                            if title:
                                result_parts.append(f"**{title}**")
                            jump_url = card.get("jump_url") or card.get("url")
                            if jump_url:
                                if jump_url.startswith("//"):
                                    jump_url = "https:" + jump_url
                                result_parts.append(f"[查看详情]({jump_url})")
                            break

        # 添加原动态链接
        if orig_id:
            orig_url = f"https://t.bilibili.com/{orig_id}"
            result_parts.append(f"[查看原动态]({orig_url})")

        return "\n".join(result_parts) if result_parts else None

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
        self, uid: int, limit_recent: int = 20
    ) -> Dict[str, Any]:
        """
        使用 bilibili-api-python 获取用户动态（替代手写 HTTP 调用）
        """

        if not self.credential:
            return {"code": -1, "message": "未配置SESSDATA，无法拉取动态"}

        try:
            u = user.User(uid=uid, credential=self.credential)

            # get_dynamics_new 返回 {items: [...], has_more: 1/0, offset: ""}
            page = await u.get_dynamics_new(offset="")

            items = page.get("items", []) or []
            if len(items) > limit_recent:
                items = items[:limit_recent]

            return {
                "code": 0,
                "data": {"items": items},
                "has_more": page.get("has_more"),
                "offset": page.get("offset"),
            }

        except Exception as e:
            self.logger.error(f"获取用户动态失败: {e}")
            return {"code": -1, "message": str(e)}

    async def process_creator(self, creator: Creator) -> None:
        """
        处理单个创作者的动态

        Args:
            creator: 创作者信息
        """
        # 获取最近20个动态
        data = await self.fetch_user_space_dynamics(creator.uid, 20)

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
                # 发送API错误通知：由 FeishuBot 的 alert 通道配置决定是否推送/推送到哪里
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

        # 每轮都检查近期动态的置顶评论变化（与是否有新动态无关）
        await self._check_recent_pinned_comments(creator, items)

        last_seen = self.state.get_last_seen(creator.uid)
        if last_seen is None:
            # 默认策略（A）：不补发历史，只对齐游标到当前最新。
            # 若用户显式开启补发（如 --reset），才会推送近期动态。
            if not self._allow_backfill_on_start:
                newest_id = items[0].get("id_str") or items[0].get("id")
                if newest_id:
                    self.state.set_last_seen(creator.uid, str(newest_id))
                    self.state.save()
                self.logger.info(
                    f"首次/重启对齐：{creator.name} 已设置 last_seen，不补发历史动态"
                )
                return

            # 补发模式：推送最近48小时内最多3条（显式触发，如 --reset）
            self.logger.info(
                f"首次监控 {creator.name}（补发模式），将推送最新的几条动态"
            )

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
                    if len(initial_items) >= 3:
                        break

            if initial_items:
                initial_items.sort(key=self.get_publish_timestamp)
                self.logger.info(
                    f"补发模式：为 {creator.name} 推送 {len(initial_items)} 条最新动态"
                )
                for it in initial_items:
                    await self._process_dynamic_item(it, creator)

                newest_processed = str(
                    initial_items[-1].get("id_str") or initial_items[-1].get("id")
                )
                self.state.set_last_seen(creator.uid, newest_processed)
                self.state.save()
            else:
                newest_id = items[0].get("id_str") or items[0].get("id")
                if newest_id:
                    self.state.set_last_seen(creator.uid, str(newest_id))
                    self.state.save()
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

        charge_prefix = ""
        if self.is_charge_dynamic(item):
            charge_prefix = "**【充电】**\n\n"

        # 构建markdown内容
        markdown_content = f"{charge_prefix}**{title}**\n\n[原视频链接]({video_url})\n[动态链接]({dynamic_url})"

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
                    detail = ""
                    if contents and contents[0]:
                        detail = f"\n\n{contents[0]}"
                    summary_text = f"AI总结失败：{message}{detail}"
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
                creator.name,
                "哔哩哔哩",
                markdown_content,
                channel=creator.feishu_channel,
                addition_title="发布新视频",
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
        is_charge = self.is_charge_dynamic(item)

        # 解析转发的原动态内容
        orig_content = self._parse_orig_dynamic(item)

        # 充电动态且无内容时，简化提示（避免 Cookie 过期导致的"无文本内容"）
        if not text and is_charge:
            text = "🔒 充电专属内容，请前往 B 站查看"
        elif not text:
            text = "(无文本内容)"

        charge_prefix = ""
        if is_charge:
            charge_prefix = "**【充电】**\n\n"

        pub_time = self.get_publish_time(item)

        # 构建markdown内容
        markdown_content = f"{charge_prefix}{text}"

        # 添加转发的原动态内容
        if orig_content:
            markdown_content += f"\n\n---\n\n**转发内容：**\n{orig_content}"

        if pub_time:
            markdown_content += f"\n\n{pub_time}"

        markdown_content += f"\n\n[查看原动态]({url})"

        # 发送到飞书
        if self.feishu_bot:
            await self.feishu_bot.send_card_message(
                creator.name,
                "哔哩哔哩",
                markdown_content,
                channel=creator.feishu_channel,
                addition_title="发布新动态",
            )

    async def monitor_single_creator(self, creator: Creator) -> None:
        """监控单个创作者的独立任务"""
        while True:
            try:
                self.logger.info(
                    f"开始检查创作者 {creator.name} (UID: {creator.uid}) 的动态"
                )
                await self.process_creator(creator)

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
                # 发送监控异常通知：由 FeishuBot 的 alert 通道配置决定是否推送/推送到哪里
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
        self,
        creators: List[Creator],
        once: bool = False,
        backfill_on_start: bool = False,
    ) -> None:
        """
        启动监控

        Args:
            creators: 创作者列表
            once: 是否只运行一次
        """
        # 启动时检查并刷新凭证
        await self._check_and_refresh_credential()

        # A 策略：启动时对齐 last_seen 到当前最新（不补发）。
        # 若显式开启 backfill_on_start（例如 --reset），则跳过对齐，允许补发。
        self._allow_backfill_on_start = bool(backfill_on_start)

        if not self._allow_backfill_on_start:
            await self._prime_last_seen(creators)

        if once:
            # 一次性检查模式
            for c in creators:
                await self.process_creator(c)
        else:
            # 持续监控模式：使用 APScheduler 统一调度（cron / interval）
            self.logger.info(
                f"启动持续监控模式（APScheduler），共 {len(creators)} 个创作者"
            )

            scheduler = AsyncIOScheduler(timezone=self._SCHEDULER_TIMEZONE)

            # 初始化配置文件监控器（热重载）
            config_watcher = ConfigFileWatcher(self.CREATORS_PATH, check_interval=600)
            config_watcher.initialize()

            async def _run_creator_job(c: Creator) -> None:
                await self.process_creator(c)

            def _setup_creator_jobs(
                sched: AsyncIOScheduler, creator_list: List[Creator]
            ) -> None:
                """为创作者列表设置调度任务"""
                for creator in creator_list:
                    if creator.crons:
                        for idx, expr in enumerate(creator.crons):
                            if not isinstance(expr, str) or not expr.strip():
                                continue
                            trigger = CronTrigger.from_crontab(
                                expr.strip(), timezone=self._SCHEDULER_TIMEZONE
                            )
                            sched.add_job(
                                _run_creator_job,
                                trigger=trigger,
                                args=[creator],
                                id=f"monitor:{creator.uid}:{idx}",
                                max_instances=1,
                                coalesce=True,
                                jitter=int(creator.jitter_seconds or 0) or None,
                                replace_existing=True,
                            )
                            self.logger.info(
                                f"已为 {creator.name} 设置 cron: {expr.strip()} (jitter={creator.jitter_seconds}s)"
                            )
                    else:
                        sched.add_job(
                            _run_creator_job,
                            trigger="interval",
                            seconds=max(30, int(creator.check_interval)),
                            args=[creator],
                            id=f"monitor:{creator.uid}:interval",
                            max_instances=1,
                            coalesce=True,
                            jitter=int(creator.jitter_seconds or 0) or None,
                            replace_existing=True,
                        )
                        self.logger.info(
                            f"已为 {creator.name} 设置 interval: {creator.check_interval}s (jitter={creator.jitter_seconds}s)"
                        )

            async def _reload_config(sched: AsyncIOScheduler) -> None:
                """热重载配置文件"""
                self.logger.info("检测到配置文件变化，开始热重载...")

                # 加载新配置
                new_creators = self.load_creators_from_file()
                if not new_creators:
                    self.logger.warning("热重载失败：新配置为空或无效，保持当前配置")
                    return

                # 获取当前所有任务ID
                old_job_ids = {
                    job.id for job in sched.get_jobs() if job.id.startswith("monitor:")
                }

                # 移除所有旧的监控任务
                for job_id in old_job_ids:
                    try:
                        sched.remove_job(job_id)
                    except Exception:
                        pass

                # 对齐新创作者的 last_seen（避免补发）
                if not self._allow_backfill_on_start:
                    await self._prime_last_seen(new_creators)

                # 添加新任务
                _setup_creator_jobs(sched, new_creators)

                self.logger.info(
                    f"热重载完成：已更新 {len(new_creators)} 个创作者的监控任务"
                )

                # 发送热重载通知
                if self.feishu_bot:
                    try:
                        creator_names = ", ".join([c.name for c in new_creators[:5]])
                        if len(new_creators) > 5:
                            creator_names += f" 等{len(new_creators)}个"
                        await self.feishu_bot.send_system_notification(
                            self.feishu_bot.LEVEL_INFO,
                            "配置热重载成功",
                            f"已自动重新加载创作者配置\n\n**当前监控:** {creator_names}",
                        )
                    except Exception:
                        pass

            # 添加配置文件监控任务（每10秒检查一次）
            async def _check_config_changes() -> None:
                if config_watcher.check_for_changes():
                    await _reload_config(scheduler)

            scheduler.add_job(
                _check_config_changes,
                trigger="interval",
                seconds=10,
                id="config_watcher",
                max_instances=1,
                coalesce=True,
            )
            self.logger.info("配置文件热重载监控已启动（每10秒检查一次）")

            # 添加凭证自动刷新任务（每6小时检查一次）
            async def _check_credential() -> None:
                await self._check_and_refresh_credential()

            scheduler.add_job(
                _check_credential,
                trigger="interval",
                seconds=self._CREDENTIAL_REFRESH_INTERVAL,
                id="credential_refresh",
                max_instances=1,
                coalesce=True,
            )
            self.logger.info(
                f"凭证自动刷新已启动（每{self._CREDENTIAL_REFRESH_INTERVAL // 3600}小时检查一次）"
            )

            # 设置初始创作者任务
            _setup_creator_jobs(scheduler, creators)

            scheduler.start()

            try:
                await asyncio.Event().wait()
            except KeyboardInterrupt:
                self.logger.info("收到停止信号，正在关闭调度器...")
                scheduler.shutdown(wait=False)

    async def _prime_last_seen(self, creators: List[Creator]) -> None:
        """启动时对齐每个 UP 的 last_seen 到当前最新，不发送任何通知。

        仅对尚无 last_seen 记录的创作者进行对齐，已有记录的保持不变。
        """
        if not creators:
            return

        for c in creators:
            # 已有 last_seen 记录的跳过，避免覆盖
            if self.state.get_last_seen(c.uid) is not None:
                continue
            try:
                data = await self.fetch_user_space_dynamics(c.uid, 1)
                items = data.get("data", {}).get("items", []) or []
                if not items:
                    continue
                newest_id = items[0].get("id_str") or items[0].get("id")
                if newest_id:
                    self.state.set_last_seen(c.uid, str(newest_id))
                    self.logger.info(f"启动对齐：{c.name} 设置 last_seen={newest_id}")
            except Exception as e:
                self.logger.warning(f"启动对齐 last_seen 失败: {c.name} ({c.uid}): {e}")

        self.state.save()

    @staticmethod
    def load_creators_from_file(path: str = CREATORS_PATH) -> List[Creator]:
        """从文件加载创作者列表"""
        os.makedirs(os.path.dirname(path), exist_ok=True)

        # 安全：不再自动生成默认博主列表，避免把个人订阅信息写入工作区。
        # 请手动从 data/bilibili_creators.json.example 复制并修改为 data/bilibili_creators.json。
        if not os.path.exists(path):
            return []

        try:
            with open(path, "r", encoding="utf-8") as f:
                items = json.load(f)
            creators = []
            for i in items:
                # 如果配置中显式禁用（enabled=false），则跳过该条目以便保留但不生效
                if i.get("enabled", True) is False:
                    continue
                channel = i.get("feishu_channel") or i.get("channel")

                crons_val = i.get("crons")
                if crons_val is None:
                    crons_val = i.get("cron")
                if isinstance(crons_val, str) and crons_val.strip():
                    crons: List[str] = [crons_val.strip()]
                elif isinstance(crons_val, list):
                    crons = [str(x).strip() for x in crons_val if str(x).strip()]
                else:
                    crons = []

                jitter = i.get("jitter_seconds")
                if jitter is None:
                    jitter = i.get("jitter")
                jitter_seconds = int(jitter or 0)

                creator = Creator(
                    uid=int(i["uid"]),
                    name=str(i["name"]),
                    check_interval=int(i.get("check_interval", 300)),
                    enable_comments=bool(i.get("enable_comments", False)),
                    comment_rules=i.get("comment_rules", []),
                    feishu_channel=str(channel).strip() if channel else None,
                    crons=crons,
                    jitter_seconds=jitter_seconds,
                )
                creators.append(creator)
            return creators
        except Exception:
            return []
