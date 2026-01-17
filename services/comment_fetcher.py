# -*- coding: utf-8 -*-
"""
B站视频评论获取服务

功能：
1. 获取视频评论（按热度排序）
2. 根据关键字筛选评论
3. 根据特定用户筛选评论
4. 根据点赞数阈值筛选评论
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from bilibili_api import Credential, comment, video
    from bilibili_api.comment import CommentResourceType, OrderType
except ImportError:
    raise ImportError(
        "请安装 bilibili-api-python: pip install bilibili-api-python 或 uv add bilibili-api-python"
    )


class CommentFetcher:
    """B站评论获取服务"""

    def __init__(self, credential: Optional[Credential] = None):
        """
        初始化评论获取服务

        Args:
            credential: B站凭证对象（包含SESSDATA等，用于自动处理WBI签名）
        """
        self.credential = credential
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def fetch_hot_comments_with_rules(
        self,
        bvid: str,
        rules: List[Dict[str, Any]],
        max_count: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        使用多个规则获取评论（支持为同一视频应用多个筛选规则）

        Args:
            bvid: 视频的BV号
            rules: 规则列表，每个规则包含：
                - name: 规则名称（用于日志）
                - keywords: 关键字列表
                - target_users: 目标用户列表（支持UID整数或用户名字符串）
                - min_likes: 最低点赞数
                - filter_mode: 筛选模式
            max_count: 最多返回的评论总数

        Returns:
            所有规则筛选结果的并集（去重后）
        """
        try:
            # 首先获取所有评论（只获取一次）
            all_comments = await self._fetch_all_hot_comments(bvid)

            if not all_comments:
                self.logger.info(f"视频 {bvid} 没有评论")
                return []

            # 存储所有规则的结果
            all_results = []
            seen_rpids = set()

            # 应用每个规则
            for idx, rule in enumerate(rules, 1):
                rule_name = rule.get("name", f"规则{idx}")
                self.logger.info(f"应用规则: {rule_name}")

                # 分离UID和用户名
                target_users = rule.get("target_users", [])
                target_uids = [u for u in target_users if isinstance(u, int)]
                target_names = [u for u in target_users if isinstance(u, str)]

                # 应用规则筛选
                filtered = self._filter_comments(
                    all_comments,
                    keywords=rule.get("keywords", []),
                    target_user_ids=target_uids if target_uids else None,
                    target_usernames=target_names if target_names else None,
                    min_likes=rule.get("min_likes"),
                    filter_mode=rule.get("filter_mode", "all"),
                )

                # 去重并添加到结果
                for comm in filtered:
                    rpid = comm.get("rpid")
                    if rpid and rpid not in seen_rpids:
                        seen_rpids.add(rpid)
                        all_results.append(comm)

                self.logger.info(f"规则 '{rule_name}' 匹配 {len(filtered)} 条评论")

            # 按点赞数排序
            all_results.sort(key=lambda x: x.get("like", 0), reverse=True)

            # 限制返回数量
            result = all_results[:max_count]

            self.logger.info(
                f"多规则筛选完成：{len(rules)}个规则，共找到{len(all_results)}条评论（去重后），返回前{len(result)}条"
            )

            return result

        except Exception as e:
            self.logger.error(f"多规则评论获取失败: {e}", exc_info=True)
            return []

    async def _fetch_all_hot_comments(self, bvid: str) -> List[Dict[str, Any]]:
        """
        获取视频的所有热门评论（不进行筛选）

        Args:
            bvid: 视频的BV号

        Returns:
            原始评论列表
        """
        try:
            # 创建视频对象
            v = video.Video(bvid=bvid, credential=self.credential)

            # 获取视频aid（用于评论API）
            video_info = await v.get_info()
            aid = video_info["aid"]

            self.logger.info(f"获取视频 {bvid} (aid={aid}) 的评论")

            # 获取评论（按热度排序）
            comment_data = await comment.get_comments(
                oid=aid,
                type_=CommentResourceType.VIDEO,
                page_index=1,
                order=OrderType.LIKE,  # 按热度排序
            )

            all_comments = []

            # 1. 优先获取热门评论区（hots）
            if "hots" in comment_data and comment_data["hots"]:
                all_comments.extend(comment_data["hots"])

            # 2. 获取UP主置顶评论
            if "upper" in comment_data and comment_data["upper"]:
                if "top" in comment_data["upper"] and comment_data["upper"]["top"]:
                    all_comments.insert(0, comment_data["upper"]["top"])

            # 3. 获取普通评论列表
            if "replies" in comment_data and comment_data["replies"]:
                all_comments.extend(comment_data["replies"])

            # 去重
            seen_rpids = set()
            unique_comments = []
            for comm in all_comments:
                rpid = comm.get("rpid")
                if rpid and rpid not in seen_rpids:
                    seen_rpids.add(rpid)
                    unique_comments.append(comm)

            return unique_comments

        except Exception as e:
            self.logger.error(f"获取评论失败: {e}", exc_info=True)
            return []

    async def fetch_hot_comments(
        self,
        bvid: str,
        max_count: int = 20,
        keywords: Optional[List[str]] = None,
        target_user_ids: Optional[List[int]] = None,
        target_usernames: Optional[List[str]] = None,
        min_likes: Optional[int] = None,
        filter_mode: str = "all",
    ) -> List[Dict[str, Any]]:
        """
        获取视频的热门评论并进行筛选（单规则模式）

        Args:
            bvid: 视频的BV号
            max_count: 最多获取的评论数量
            keywords: 关键字列表（满足任一关键字即可）
            target_user_ids: 目标用户UID列表（筛选特定用户的评论）
            target_usernames: 目标用户名列表（支持用户名筛选）
            min_likes: 最低点赞数阈值
            filter_mode: 筛选模式（见_filter_comments方法的说明）

        Returns:
            筛选后的评论列表
        """
        try:
            # 获取所有评论
            all_comments = await self._fetch_all_hot_comments(bvid)

            if not all_comments:
                return []

            # 应用筛选条件
            filtered_comments = self._filter_comments(
                all_comments,
                keywords=keywords,
                target_user_ids=target_user_ids,
                target_usernames=target_usernames,
                min_likes=min_likes,
                filter_mode=filter_mode,
            )

            # 限制返回数量
            result = filtered_comments[:max_count]

            self.logger.info(
                f"筛选后得到 {len(filtered_comments)} 条评论，返回前 {len(result)} 条"
            )

            return result

        except Exception as e:
            self.logger.error(f"获取评论失败: {e}", exc_info=True)
            return []

    def _filter_comments(
        self,
        comments: List[Dict[str, Any]],
        keywords: Optional[List[str]] = None,
        target_user_ids: Optional[List[int]] = None,
        target_usernames: Optional[List[str]] = None,
        min_likes: Optional[int] = None,
        filter_mode: str = "all",
    ) -> List[Dict[str, Any]]:
        """
        筛选评论（支持多种筛选模式）

        Args:
            comments: 原始评论列表
            keywords: 关键字列表
            target_user_ids: 目标用户UID列表
            target_usernames: 目标用户名列表
            min_likes: 最低点赞数
            filter_mode: 筛选模式
                - "all": 所有条件都满足（AND，默认）
                - "any": 任一条件满足（OR）
                - "keywords_only": 只检查关键字
                - "users_only": 只检查用户
                - "keywords_or_users": 关键字或用户任一满足（推荐）
                - "keywords_and_users": 必须同时满足关键字和用户

        Returns:
            筛选后的评论列表
        """
        filtered = []

        for comm in comments:
            # 提取评论信息
            content_obj = comm.get("content", {})
            message = content_obj.get("message", "")
            member = comm.get("member", {})
            mid = member.get("mid", 0)
            uname = member.get("uname", "")
            like_count = comm.get("like", 0)

            # 检查各个条件
            keyword_match = self._check_keyword_match(message, keywords)
            user_match = self._check_user_match(
                mid, uname, target_user_ids, target_usernames
            )
            likes_match = self._check_likes_match(like_count, min_likes)

            # 根据筛选模式决定是否通过
            should_include = self._evaluate_filter_mode(
                filter_mode,
                keyword_match,
                user_match,
                likes_match,
                has_keywords=bool(keywords and keywords),
                has_users=bool(
                    (target_user_ids and target_user_ids)
                    or (target_usernames and target_usernames)
                ),
                has_min_likes=min_likes is not None,
            )

            if should_include:
                filtered.append(comm)

        return filtered

    @staticmethod
    def _check_keyword_match(message: str, keywords: Optional[List[str]]) -> bool:
        """检查是否匹配关键字"""
        if not keywords or not keywords:
            return True  # 没有设置关键字，视为匹配
        return any(keyword in message for keyword in keywords)

    @staticmethod
    def _check_user_match(
        mid: int,
        uname: str,
        target_user_ids: Optional[List[int]] = None,
        target_usernames: Optional[List[str]] = None,
    ) -> bool:
        """检查是否匹配目标用户（支持UID和用户名）"""
        # 没有设置任何用户筛选条件
        if not (target_user_ids and target_user_ids) and not (
            target_usernames and target_usernames
        ):
            return True

        # 检查UID匹配
        if target_user_ids and target_user_ids:
            if mid in target_user_ids:
                return True

        # 检查用户名匹配
        if target_usernames and target_usernames:
            if uname in target_usernames:
                return True

        return False

    @staticmethod
    def _check_likes_match(like_count: int, min_likes: Optional[int]) -> bool:
        """检查是否满足点赞数要求"""
        if min_likes is None:
            return True  # 没有设置点赞数要求，视为匹配
        return like_count >= min_likes

    def _evaluate_filter_mode(
        self,
        mode: str,
        keyword_match: bool,
        user_match: bool,
        likes_match: bool,
        has_keywords: bool,
        has_users: bool,
        has_min_likes: bool,
    ) -> bool:
        """
        根据筛选模式评估是否应该包含该评论

        Args:
            mode: 筛选模式
            keyword_match: 是否匹配关键字
            user_match: 是否匹配用户
            likes_match: 是否满足点赞数
            has_keywords: 是否设置了关键字条件
            has_users: 是否设置了用户条件
            has_min_likes: 是否设置了点赞数条件

        Returns:
            是否应该包含该评论
        """
        # 点赞数是硬性要求，必须满足
        if has_min_likes and not likes_match:
            return False

        # 根据模式评估
        if mode == "all":
            # 所有已设置的条件都必须满足
            return keyword_match and user_match and likes_match

        elif mode == "any":
            # 任一已设置的条件满足即可
            conditions = []
            if has_keywords:
                conditions.append(keyword_match)
            if has_users:
                conditions.append(user_match)
            if has_min_likes:
                conditions.append(likes_match)
            return any(conditions) if conditions else True

        elif mode == "keywords_only":
            # 只检查关键字（忽略用户条件）
            return keyword_match and likes_match

        elif mode == "users_only":
            # 只检查用户（忽略关键字条件）
            return user_match and likes_match

        elif mode == "keywords_or_users":
            # 关键字或用户任一满足即可（点赞数仍需满足）
            if has_keywords and has_users:
                return (keyword_match or user_match) and likes_match
            elif has_keywords:
                return keyword_match and likes_match
            elif has_users:
                return user_match and likes_match
            else:
                return likes_match

        elif mode == "keywords_and_users":
            # 关键字和用户必须同时满足
            return keyword_match and user_match and likes_match

        else:
            # 默认使用"all"模式
            self.logger.warning(f"未知的筛选模式: {mode}，使用默认的'all'模式")
            return keyword_match and user_match and likes_match

    @staticmethod
    def _flatten_comment_tree(
        comments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """展开评论树（包含子回复），并做去重。"""
        if not comments:
            return []

        flattened: List[Dict[str, Any]] = []
        seen = set()
        stack = list(comments)

        while stack:
            comm = stack.pop()
            if not isinstance(comm, dict):
                continue

            rpid = comm.get("rpid")
            if rpid is None:
                rpid = comm.get("rpid_str")
            rpid_str = str(rpid) if rpid is not None else ""
            if rpid_str:
                if rpid_str in seen:
                    replies = comm.get("replies")
                    if isinstance(replies, list) and replies:
                        stack.extend(replies)
                    continue
                seen.add(rpid_str)

            flattened.append(comm)

            replies = comm.get("replies")
            if isinstance(replies, list) and replies:
                stack.extend(replies)

        return flattened

    def format_comment_for_display(self, comm: Dict[str, Any]) -> str:
        """
        格式化评论为可读文本（含图片）

        Args:
            comm: 评论对象

        Returns:
            格式化后的文本（Markdown格式，包含图片链接）
        """
        try:
            # 提取评论信息
            content_obj = comm.get("content", {})
            message = content_obj.get("message", "")

            member = comm.get("member", {})
            uname = member.get("uname", "未知用户")

            like_count = comm.get("like", 0)
            reply_count = comm.get("rcount", 0)

            # 评论时间
            ctime = comm.get("ctime", 0)
            time_str = datetime.fromtimestamp(ctime).strftime("%Y-%m-%d %H:%M:%S")

            # 楼层
            floor = comm.get("floor", 0)

            # 格式化输出
            result = f"👤 **{uname}**\n"
            result += f"🕐 {time_str}\n"
            result += f"👍 {like_count} 赞 | 💬 {reply_count} 回复"
            if floor:
                result += f" | 🏢 {floor}楼"
            result += f"\n\n{message}\n"

            # 🆕 处理评论中的图片
            pictures = content_obj.get("pictures", [])
            if pictures:
                result += f"\n📷 **图片 ({len(pictures)}张)**\n\n"
                for idx, pic in enumerate(pictures, 1):
                    img_src = pic.get("img_src", "")
                    if img_src:
                        # 使用Markdown图片语法，飞书会在app模式下转换为image_key
                        # webhook模式下暂时显示为链接
                        result += f"![评论图片{idx}]({img_src})\n\n"

            return result

        except Exception as e:
            self.logger.error(f"格式化评论失败: {e}")
            return "评论格式化失败"

    async def fetch_recent_comments_by_oid(
        self,
        oid: int,
        type_: CommentResourceType,
        page_index: int = 1,
    ) -> List[Dict[str, Any]]:
        """按时间排序拉取评论（支持动态/视频等资源）。"""
        comment_data = await comment.get_comments(
            oid=oid,
            type_=type_,
            page_index=page_index,
            order=OrderType.TIME,
            credential=self.credential,
        )

        payload: Any = comment_data
        if isinstance(comment_data, dict) and isinstance(
            comment_data.get("data"), dict
        ):
            payload = comment_data["data"]

        if not isinstance(payload, dict):
            return []

        comments: List[Dict[str, Any]] = []

        top = payload.get("top")
        if isinstance(top, dict):
            upper = top.get("upper")
            if isinstance(upper, dict):
                comments.append(upper)
            admin = top.get("admin")
            if isinstance(admin, dict):
                comments.append(admin)
            top_reply = top.get("top")
            if isinstance(top_reply, dict):
                comments.append(top_reply)

        upper_wrap = payload.get("upper")
        if isinstance(upper_wrap, dict):
            top2 = upper_wrap.get("top")
            if isinstance(top2, dict):
                comments.append(top2)

        replies = payload.get("replies")
        if isinstance(replies, list):
            comments.extend(replies)

        return self._flatten_comment_tree(comments)

    async def fetch_recent_video_comments(
        self, bvid: str, page_index: int = 1
    ) -> List[Dict[str, Any]]:
        """按时间排序拉取视频评论（包含子回复）。"""
        v = video.Video(bvid=bvid, credential=self.credential)
        video_info = await v.get_info()
        aid = video_info.get("aid")
        if not aid:
            return []
        return await self.fetch_recent_comments_by_oid(
            oid=int(aid),
            type_=CommentResourceType.VIDEO,
            page_index=page_index,
        )

    async def fetch_upper_pinned_comment(
        self, oid: int, type_: CommentResourceType
    ) -> Optional[Dict[str, Any]]:
        """获取 UP 主置顶评论（如存在）。

        兼容 bilibili-api-python 评论接口的两种常见返回结构：
        - data.top.upper
        - upper.top
        """

        comment_data = await comment.get_comments(
            oid=oid,
            type_=type_,
            page_index=1,
            order=OrderType.TIME,
            credential=self.credential,
        )

        payload: Any = comment_data
        if isinstance(comment_data, dict) and isinstance(
            comment_data.get("data"), dict
        ):
            payload = comment_data["data"]

        if not isinstance(payload, dict):
            return None

        top = payload.get("top")
        if isinstance(top, dict):
            upper = top.get("upper")
            if isinstance(upper, dict):
                return upper

        upper_wrap = payload.get("upper")
        if isinstance(upper_wrap, dict):
            top2 = upper_wrap.get("top")
            if isinstance(top2, dict):
                return top2

        return None

    def format_comments_for_feishu(
        self, comments: List[Dict[str, Any]], video_title: str, bvid: str
    ) -> str:
        """
        格式化评论为飞书消息格式

        Args:
            comments: 评论列表
            video_title: 视频标题
            bvid: 视频BV号

        Returns:
            Markdown格式的文本（适合飞书卡片）
        """
        if not comments:
            return "未找到符合条件的评论"

        # 构建Markdown内容
        md_content = f"## 📺 视频：{video_title}\n\n"
        md_content += f"🔗 https://www.bilibili.com/video/{bvid}\n\n"
        md_content += "---\n\n"
        md_content += f"### 🔥 精选评论 (共{len(comments)}条)\n\n"

        for idx, comm in enumerate(comments, 1):
            md_content += f"#### {idx}. {self.format_comment_for_display(comm)}\n"
            md_content += "---\n\n"

        return md_content


# 使用示例
async def example_usage():
    """使用示例"""
    from config import BILIBILI_CONFIG

    # 创建凭证（bilibili-api-python会自动处理WBI签名！）
    credential = Credential(
        sessdata=BILIBILI_CONFIG.get("SESSDATA"),
        bili_jct=BILIBILI_CONFIG.get("bili_jct"),
        buvid3=BILIBILI_CONFIG.get("buvid3"),
    )

    # 创建评论获取服务
    fetcher = CommentFetcher(credential=credential)

    # 获取评论（带筛选条件）
    comments = await fetcher.fetch_hot_comments(
        bvid="BV1HnaHzcEag",
        max_count=10,
        keywords=["总结", "梗概", "要点"],  # 关键字筛选
        target_user_ids=[123456, 789012],  # 特定用户筛选（示例）
        min_likes=10,  # 最低10个赞
    )

    # 格式化并打印
    if comments:
        formatted = fetcher.format_comments_for_feishu(
            comments, "测试视频标题", "BV1HnaHzcEag"
        )
        print(formatted)
    else:
        print("没有找到符合条件的评论")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(example_usage())
