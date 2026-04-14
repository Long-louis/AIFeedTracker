# -*- coding: utf-8 -*-

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from json import JSONDecodeError
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp

from config import FEISHU_DOCS_CONFIG
from services.ai_summary import VideoSummaryResult


class FeishuDocsService:
    """把视频总结写入飞书知识库文档（根 -> 博主 -> YYYY-MM -> 视频文档）。"""

    _API_BASE = "https://open.feishu.cn/open-apis"
    _MARKDOWN_CONVERT_SCOPE = "docx:document.block:convert"
    _DOC_CHILDREN_BATCH_SIZE = 50

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.config = dict(config or FEISHU_DOCS_CONFIG)

        self.enabled = bool(self.config.get("enabled"))
        self.app_id = str(self.config.get("app_id") or "")
        self.app_secret = str(self.config.get("app_secret") or "")
        self.wiki_space_id = str(self.config.get("wiki_space_id") or "")
        self.root_node_token = str(self.config.get("root_node_token") or "")
        self.root_title = str(self.config.get("root_title") or "AI视频知识库")
        self.state_path = str(
            self.config.get("state_path") or "data/feishu_doc_state.json"
        )
        self.request_timeout_seconds = int(
            self.config.get("request_timeout_seconds") or 30
        )

        self._tenant_access_token: Optional[str] = None
        self._tenant_access_token_expire_ts = 0.0

        self._state = self._load_state()
        self._normalize_state()

        if not self.enabled:
            return

        required_missing = []
        if not self.app_id:
            required_missing.append("FEISHU_DOCS_APP_ID")
        if not self.app_secret:
            required_missing.append("FEISHU_DOCS_APP_SECRET")
        if not self.wiki_space_id:
            required_missing.append("FEISHU_DOCS_WIKI_SPACE_ID")

        if required_missing:
            self.logger.warning(
                "飞书文档知识库已禁用：缺少必要配置 %s", ", ".join(required_missing)
            )
            self.enabled = False

    def _normalize_state(self) -> None:
        self._state.setdefault("creator_nodes", {})
        self._state.setdefault("month_nodes", {})
        self._state.setdefault("video_docs", {})

    def _load_state(self) -> Dict[str, Any]:
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        if not os.path.exists(self.state_path):
            return {}
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception as exc:
            self.logger.warning("读取飞书文档状态失败，将重建状态: %s", exc)
        return {}

    def _save_state(self) -> None:
        tmp = f"{self.state_path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._state, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.state_path)

    @staticmethod
    def _month_key_from_publish_time(publish_time: str) -> str:
        if publish_time:
            matched = re.search(r"(\d{4}-\d{2})", publish_time)
            if matched:
                return matched.group(1)
        return datetime.now().strftime("%Y-%m")

    @staticmethod
    def _clean_title(title: str) -> str:
        normalized = " ".join((title or "未命名视频").strip().split())
        return normalized[:150] if len(normalized) > 150 else normalized

    @staticmethod
    def _hash_summary(summary_markdown: str) -> str:
        return hashlib.sha256(summary_markdown.encode("utf-8")).hexdigest()

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        token: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        unwrap_data: bool = True,
    ) -> Dict[str, Any]:
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        timeout = aiohttp.ClientTimeout(total=self.request_timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(
                method,
                f"{self._API_BASE}{path}",
                headers=headers,
                json=payload,
            ) as resp:
                body = await resp.text()

        try:
            data = json.loads(body or "{}")
        except JSONDecodeError as exc:
            stripped = (body or "").lstrip()
            if stripped.startswith(")]}'"):
                parts = stripped.split("\n", 1)
                payload_text = parts[1] if len(parts) > 1 else stripped[4:]
                data = json.loads(payload_text or "{}")
            else:
                preview = stripped[:200]
                raise RuntimeError(
                    f"飞书接口返回非JSON响应: path={path} body={preview}"
                ) from exc

        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status}: {data}")
        if data.get("code", 0) != 0:
            raise RuntimeError(data.get("msg") or str(data))
        if unwrap_data:
            return data.get("data") or {}
        return data

    @staticmethod
    def _extract_tenant_token_and_expire(
        auth_payload: Dict[str, Any],
    ) -> tuple[str, int]:
        token = auth_payload.get("tenant_access_token")
        expire = auth_payload.get("expire")

        nested = auth_payload.get("data")
        if (not token or expire is None) and isinstance(nested, dict):
            token = token or nested.get("tenant_access_token")
            if expire is None:
                expire = nested.get("expire")

        if not token:
            raise RuntimeError("飞书 tenant_access_token 为空")

        try:
            expire_int = int(expire or 0)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                f"飞书 tenant_access_token 过期时间无效: {expire}"
            ) from exc

        return str(token), expire_int

    async def _get_tenant_access_token(self) -> str:
        now_ts = time.time()
        if self._tenant_access_token and now_ts < self._tenant_access_token_expire_ts:
            return self._tenant_access_token

        data = await self._request_json(
            "POST",
            "/auth/v3/tenant_access_token/internal",
            payload={"app_id": self.app_id, "app_secret": self.app_secret},
            unwrap_data=False,
        )
        token, expire = self._extract_tenant_token_and_expire(data)
        self._tenant_access_token = token
        self._tenant_access_token_expire_ts = now_ts + max(60, expire - 60)
        return self._tenant_access_token

    async def _create_wiki_node(
        self,
        token: str,
        *,
        parent_node_token: str,
        title: str,
        obj_type: str,
    ) -> Dict[str, str]:
        payload = {
            "parent_node_token": parent_node_token,
            "node_type": "origin",
            "obj_type": obj_type,
            "title": title,
        }
        data = await self._request_json(
            "POST",
            f"/wiki/v2/spaces/{self.wiki_space_id}/nodes",
            token=token,
            payload=payload,
        )
        node = data.get("node") if isinstance(data.get("node"), dict) else data
        return {
            "node_token": str(node.get("node_token") or data.get("node_token") or ""),
            "obj_token": str(node.get("obj_token") or data.get("obj_token") or ""),
            "url": str(data.get("url") or node.get("url") or ""),
        }

    async def _replace_doc_content(
        self, token: str, doc_token: str, markdown: str
    ) -> None:
        await self._clear_doc_children(token, doc_token)
        blocks = await self._convert_markdown_to_blocks(token, markdown)
        if not blocks:
            return

        for index in range(0, len(blocks), self._DOC_CHILDREN_BATCH_SIZE):
            await self._request_json(
                "POST",
                f"/docx/v1/documents/{doc_token}/blocks/{doc_token}/children",
                token=token,
                payload={
                    "children": blocks[index : index + self._DOC_CHILDREN_BATCH_SIZE]
                },
            )

    async def _convert_markdown_to_blocks(
        self, token: str, markdown: str
    ) -> List[Dict[str, Any]]:
        normalized_markdown = (markdown or "").strip()
        if not normalized_markdown:
            normalized_markdown = "（暂无总结内容）"

        try:
            data = await self._request_json(
                "POST",
                "/docx/v1/documents/blocks/convert",
                token=token,
                payload={
                    "content_type": "markdown",
                    "content": normalized_markdown,
                },
            )
            blocks = self._extract_converted_blocks(data)
            if blocks:
                return blocks
            self.logger.warning("Markdown 转文档块接口返回空结果，回退为纯文本块")
        except Exception as exc:
            message = str(exc)
            if self._MARKDOWN_CONVERT_SCOPE in message:
                self.logger.warning(
                    "缺少飞书权限 %s，文档将以纯文本块写入。请在应用权限中开通后重试。",
                    self._MARKDOWN_CONVERT_SCOPE,
                )
            else:
                self.logger.warning("Markdown 转文档块失败，回退为纯文本块: %s", exc)

        return self._markdown_to_text_blocks(normalized_markdown)

    @staticmethod
    def _extract_converted_blocks(data: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not isinstance(data, dict):
            return []

        for key in ("children", "blocks", "items"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return []

    async def _clear_doc_children(self, token: str, doc_token: str) -> None:
        data = await self._request_json(
            "GET",
            f"/docx/v1/documents/{doc_token}/blocks/{doc_token}/children?page_size=500",
            token=token,
        )
        items = data.get("items") or []
        if not isinstance(items, list) or not items:
            return

        await self._request_json(
            "DELETE",
            f"/docx/v1/documents/{doc_token}/blocks/{doc_token}/children/batch_delete?document_revision_id=-1",
            token=token,
            payload={"start_index": 0, "end_index": len(items)},
        )

    @staticmethod
    def _markdown_to_text_blocks(markdown: str) -> List[Dict[str, Any]]:
        lines = [line.strip() for line in (markdown or "").splitlines() if line.strip()]
        if not lines:
            lines = ["（暂无总结内容）"]

        blocks: List[Dict[str, Any]] = []
        for line in lines:
            blocks.append(
                {
                    "block_type": 2,
                    "text": {
                        "elements": [
                            {
                                "text_run": {
                                    "content": line,
                                }
                            }
                        ]
                    },
                }
            )
        return blocks

    async def _ensure_root_node(self, token: str) -> str:
        if self.root_node_token:
            return self.root_node_token

        state_root = self._state.get("root_node_token")
        if state_root:
            self.root_node_token = str(state_root)
            return self.root_node_token

        created = await self._create_wiki_node(
            token,
            parent_node_token="",
            title=self.root_title,
            obj_type="docx",
        )
        node_token = created.get("node_token")
        if not node_token:
            raise RuntimeError("创建知识库根目录失败：未返回 node_token")
        self.root_node_token = node_token
        self._state["root_node_token"] = node_token
        self._save_state()
        return node_token

    async def _ensure_creator_node(
        self, token: str, *, root_node_token: str, creator_uid: int, creator_name: str
    ) -> str:
        key = str(creator_uid)
        creator_nodes = self._state["creator_nodes"]
        exists = creator_nodes.get(key)
        if isinstance(exists, dict) and exists.get("node_token"):
            return str(exists["node_token"])

        created = await self._create_wiki_node(
            token,
            parent_node_token=root_node_token,
            title=f"{creator_name}({creator_uid})",
            obj_type="docx",
        )
        node_token = created.get("node_token")
        if not node_token:
            raise RuntimeError("创建博主目录失败：未返回 node_token")
        creator_nodes[key] = {
            "node_token": node_token,
            "creator_name": creator_name,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._save_state()
        return node_token

    async def _ensure_month_node(
        self,
        token: str,
        *,
        creator_uid: int,
        creator_node_token: str,
        month_key: str,
    ) -> str:
        map_key = f"{creator_uid}:{month_key}"
        month_nodes = self._state["month_nodes"]
        exists = month_nodes.get(map_key)
        if isinstance(exists, dict) and exists.get("node_token"):
            return str(exists["node_token"])

        created = await self._create_wiki_node(
            token,
            parent_node_token=creator_node_token,
            title=month_key,
            obj_type="docx",
        )
        node_token = created.get("node_token")
        if not node_token:
            raise RuntimeError("创建月份目录失败：未返回 node_token")
        month_nodes[map_key] = {
            "node_token": node_token,
            "month": month_key,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._save_state()
        return node_token

    def _build_doc_content(
        self,
        *,
        creator_name: str,
        title: str,
        video_url: str,
        publish_time: str,
        summary_source: str,
        summary_markdown: str,
    ) -> str:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            f"# {title}",
            "",
            f"- 博主: {creator_name}",
            f"- 视频链接: {video_url}",
            f"- 发布时间: {publish_time or '未知'}",
            f"- 总结来源: {summary_source}",
            f"- 更新于: {now_str}",
            "",
            summary_markdown.strip(),
            "",
        ]
        return "\n".join(lines)

    async def upsert_video_summary(
        self,
        *,
        creator_uid: int,
        creator_name: str,
        bvid: str,
        video_title: str,
        video_url: str,
        publish_time: str,
        summary: VideoSummaryResult,
    ) -> Optional[str]:
        if not self.enabled:
            return None

        try:
            token = await self._get_tenant_access_token()
            root_node_token = await self._ensure_root_node(token)
            creator_node_token = await self._ensure_creator_node(
                token,
                root_node_token=root_node_token,
                creator_uid=creator_uid,
                creator_name=creator_name,
            )
            month_key = self._month_key_from_publish_time(publish_time)
            month_node_token = await self._ensure_month_node(
                token,
                creator_uid=creator_uid,
                creator_node_token=creator_node_token,
                month_key=month_key,
            )

            content_hash = self._hash_summary(summary.summary_markdown)
            doc_state = self._state["video_docs"].get(bvid)

            doc_content = self._build_doc_content(
                creator_name=creator_name,
                title=self._clean_title(video_title),
                video_url=video_url,
                publish_time=publish_time,
                summary_source=summary.summary_source,
                summary_markdown=summary.summary_markdown,
            )

            doc_url = None
            if doc_state and doc_state.get("doc_token"):
                doc_token = str(doc_state["doc_token"])
                doc_url = str(
                    doc_state.get("doc_url") or f"https://feishu.cn/docx/{doc_token}"
                )
                if doc_state.get("content_hash") != content_hash:
                    await self._replace_doc_content(token, doc_token, doc_content)
            else:
                safe_title = self._clean_title(video_title)
                doc_title = f"[{datetime.now().strftime('%Y-%m-%d')}] {safe_title}"
                created_doc = await self._create_wiki_node(
                    token,
                    parent_node_token=month_node_token,
                    title=doc_title,
                    obj_type="docx",
                )
                doc_token = created_doc.get("obj_token") or created_doc.get(
                    "node_token"
                )
                if not doc_token:
                    raise RuntimeError("创建视频文档失败：未返回 doc token")
                await self._replace_doc_content(token, doc_token, doc_content)
                doc_url = (
                    created_doc.get("url") or f"https://feishu.cn/docx/{doc_token}"
                )

            self._state["video_docs"][bvid] = {
                "doc_token": doc_token,
                "doc_url": doc_url,
                "creator_uid": int(creator_uid),
                "month": month_key,
                "content_hash": content_hash,
                "summary_source": summary.summary_source,
                "last_updated_at": datetime.now().isoformat(timespec="seconds"),
            }
            self._save_state()
            return doc_url
        except Exception as exc:
            self.logger.error("写入飞书知识库失败: bvid=%s error=%s", bvid, exc)
            return None
