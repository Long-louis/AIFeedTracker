# -*- coding: utf-8 -*-

import tempfile
import unittest

from services.ai_summary.service import VideoSummaryResult
from services.feishu_docs import FeishuDocsService


class _FakeFeishuDocsService(FeishuDocsService):
    def __init__(self, state_path: str):
        super().__init__(
            {
                "enabled": True,
                "app_id": "app-id",
                "app_secret": "app-secret",
                "wiki_space_id": "space-token",
                "root_node_token": "",
                "root_title": "AI视频知识库",
                "state_path": state_path,
                "request_timeout_seconds": 5,
            }
        )
        self.created_nodes = []
        self.updated_docs = []

    async def _get_tenant_access_token(self) -> str:
        return "token"

    async def _create_wiki_node(self, token: str, **kwargs):
        self.created_nodes.append(kwargs)
        seq = len(self.created_nodes)
        node_token = f"node-{seq}"
        obj_type = kwargs.get("obj_type")
        if obj_type == "docx":
            return {
                "node_token": node_token,
                "obj_token": f"doc-{seq}",
                "url": f"https://feishu.cn/docx/doc-{seq}",
            }
        return {"node_token": node_token, "obj_token": "", "url": ""}

    async def _replace_doc_content(
        self, token: str, doc_token: str, markdown: str
    ) -> None:
        self.updated_docs.append((doc_token, markdown))


class TestFeishuDocsService(unittest.IsolatedAsyncioTestCase):
    async def test_upsert_uses_state_idempotency(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = f"{tmpdir}/feishu_doc_state.json"
            service = _FakeFeishuDocsService(state_path)

            summary = VideoSummaryResult(
                video_url="https://www.bilibili.com/video/BV1xx411c7mD",
                summary_source="subtitle",
                summary_markdown="## 关键信息和观点\n- 要点1\n\n## 时间线总结\n- 00:00 开场",
            )

            doc_url = await service.upsert_video_summary(
                creator_uid=1001,
                creator_name="测试UP",
                bvid="BV1xx411c7mD",
                video_title="测试视频",
                video_url=summary.video_url,
                publish_time="发布时间：2026-04-09 11:30:00",
                summary=summary,
            )
            self.assertEqual(doc_url, "https://feishu.cn/docx/doc-4")
            self.assertEqual(len(service.created_nodes), 4)
            self.assertEqual(len(service.updated_docs), 1)

            # 相同内容再次写入，不重复创建/更新
            doc_url_2 = await service.upsert_video_summary(
                creator_uid=1001,
                creator_name="测试UP",
                bvid="BV1xx411c7mD",
                video_title="测试视频",
                video_url=summary.video_url,
                publish_time="发布时间：2026-04-09 11:30:00",
                summary=summary,
            )
            self.assertEqual(doc_url_2, "https://feishu.cn/docx/doc-4")
            self.assertEqual(len(service.created_nodes), 4)
            self.assertEqual(len(service.updated_docs), 1)

            # 内容变化后，仅更新文档
            summary2 = VideoSummaryResult(
                video_url=summary.video_url,
                summary_source="subtitle",
                summary_markdown="## 关键信息和观点\n- 要点2\n\n## 时间线总结\n- 01:00 核心",
            )
            await service.upsert_video_summary(
                creator_uid=1001,
                creator_name="测试UP",
                bvid="BV1xx411c7mD",
                video_title="测试视频",
                video_url=summary.video_url,
                publish_time="发布时间：2026-04-09 11:30:00",
                summary=summary2,
            )
            self.assertEqual(len(service.created_nodes), 4)
            self.assertEqual(len(service.updated_docs), 2)


class TestFeishuDocsAuthPayload(unittest.TestCase):
    def test_extract_tenant_token_from_top_level_payload(self):
        token, expire = FeishuDocsService._extract_tenant_token_and_expire(
            {
                "code": 0,
                "msg": "success",
                "tenant_access_token": "tok-top-level",
                "expire": 7200,
            }
        )
        self.assertEqual(token, "tok-top-level")
        self.assertEqual(expire, 7200)

    def test_extract_tenant_token_from_nested_data_payload(self):
        token, expire = FeishuDocsService._extract_tenant_token_and_expire(
            {
                "code": 0,
                "msg": "success",
                "data": {"tenant_access_token": "tok-nested", "expire": 3600},
            }
        )
        self.assertEqual(token, "tok-nested")
        self.assertEqual(expire, 3600)


class TestFeishuDocsBlockConversion(unittest.TestCase):
    def test_extract_converted_blocks_from_children(self):
        blocks = FeishuDocsService._extract_converted_blocks(
            {
                "children": [
                    {"block_type": 3, "heading1": {"elements": []}},
                    "invalid",
                ]
            }
        )
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["block_type"], 3)

    def test_extract_converted_blocks_rebuilds_first_level_from_convert_payload(self):
        blocks = FeishuDocsService._extract_converted_blocks(
            {
                "first_level_block_ids": ["h1", "p1"],
                "blocks": [
                    {
                        "block_id": "h1",
                        "revision_id": 0,
                        "parent_id": "",
                        "children": ["child1"],
                        "block_type": 3,
                        "heading1": {"elements": [{"text_run": {"content": "标题"}}]},
                    },
                    {
                        "block_id": "child1",
                        "revision_id": 0,
                        "parent_id": "h1",
                        "children": [],
                        "block_type": 2,
                        "text": {"elements": [{"text_run": {"content": "嵌套内容"}}]},
                    },
                    {
                        "block_id": "p1",
                        "revision_id": 0,
                        "parent_id": "",
                        "children": [],
                        "block_type": 2,
                        "text": {"elements": [{"text_run": {"content": "段落"}}]},
                    },
                ],
            }
        )

        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0]["block_type"], 3)
        self.assertEqual(blocks[1]["block_type"], 2)
        self.assertNotIn("block_id", blocks[0])
        self.assertNotIn("revision_id", blocks[0])
        self.assertNotIn("parent_id", blocks[0])
        self.assertNotIn("children", blocks[0])

    def test_extract_descendant_payload_orders_blocks_by_document_tree(self):
        payload = FeishuDocsService._extract_convert_descendant_payload(
            {
                "first_level_block_ids": ["h1", "list1"],
                "blocks": [
                    {
                        "block_id": "li2",
                        "parent_id": "list1",
                        "children": [],
                        "block_type": 12,
                        "bullet": {"elements": [{"text_run": {"content": "第二项"}}]},
                    },
                    {
                        "block_id": "h1",
                        "parent_id": "",
                        "children": [],
                        "block_type": 3,
                        "heading1": {"elements": [{"text_run": {"content": "标题"}}]},
                    },
                    {
                        "block_id": "li1",
                        "parent_id": "list1",
                        "children": [],
                        "block_type": 12,
                        "bullet": {"elements": [{"text_run": {"content": "第一项"}}]},
                    },
                    {
                        "block_id": "list1",
                        "parent_id": "",
                        "children": ["li1", "li2"],
                        "block_type": 12,
                        "bullet": {"elements": [{"text_run": {"content": "列表"}}]},
                    },
                ],
            }
        )

        self.assertIsNotNone(payload)
        self.assertEqual(payload["children_id"], ["h1", "list1"])
        self.assertEqual(
            [block["block_id"] for block in payload["descendants"]],
            ["h1", "list1", "li1", "li2"],
        )

    def test_extract_descendant_payload_preserves_string_child_relationship(self):
        payload = FeishuDocsService._extract_convert_descendant_payload(
            {
                "first_level_block_ids": ["parent"],
                "blocks": [
                    {
                        "block_id": "parent",
                        "children": "child",
                        "block_type": 12,
                        "bullet": {"elements": [{"text_run": {"content": "父级"}}]},
                    },
                    {
                        "block_id": "child",
                        "children": [],
                        "block_type": 12,
                        "bullet": {"elements": [{"text_run": {"content": "子级"}}]},
                    },
                ],
            }
        )

        self.assertIsNotNone(payload)
        self.assertEqual(payload["descendants"][0]["children"], ["child"])
        self.assertEqual(
            [block["block_id"] for block in payload["descendants"]],
            ["parent", "child"],
        )

    def test_markdown_to_text_blocks_converts_basic_markdown_formatting(self):
        blocks = FeishuDocsService._markdown_to_text_blocks(
            "## 关键信息和观点\n- **要点A**：内容"
        )
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0]["block_type"], 4)
        self.assertEqual(
            blocks[0]["heading2"]["elements"][0]["text_run"]["content"],
            "关键信息和观点",
        )
        elements = blocks[1]["text"]["elements"]
        self.assertEqual(elements[0]["text_run"]["content"], "• ")
        self.assertEqual(elements[1]["text_run"]["content"], "要点A")
        self.assertTrue(
            elements[1]["text_run"]["text_element_style"]["bold"]
        )
        self.assertNotIn("**", "".join(e["text_run"]["content"] for e in elements))

    def test_markdown_to_text_blocks_handles_empty_text(self):
        blocks = FeishuDocsService._markdown_to_text_blocks("   \n\n")
        self.assertEqual(len(blocks), 1)
        self.assertEqual(
            blocks[0]["text"]["elements"][0]["text_run"]["content"],
            "（暂无总结内容）",
        )


class TestFeishuDocsMarkdownConvert(unittest.IsolatedAsyncioTestCase):
    async def test_convert_markdown_to_blocks_prefers_descendant_payload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = f"{tmpdir}/feishu_doc_state.json"
            service = _FakeFeishuDocsService(state_path)

            async def _fake_request_json(method, path, **kwargs):
                if path == "/docx/v1/documents/blocks/convert":
                    return {
                        "first_level_block_ids": ["h1"],
                        "blocks": [
                            {
                                "block_id": "h1",
                                "block_type": 3,
                                "children": [],
                                "heading1": {
                                    "elements": [{"text_run": {"content": "标题"}}]
                                },
                            }
                        ],
                    }
                raise AssertionError(f"unexpected path: {path}")

            service._request_json = _fake_request_json  # type: ignore[method-assign]

            write_payload = await service._convert_markdown_to_blocks("token", "# 标题")
            self.assertEqual(write_payload["mode"], "descendant")
            self.assertEqual(write_payload["children_id"], ["h1"])
            self.assertEqual(len(write_payload["descendants"]), 1)
            self.assertEqual(write_payload["descendants"][0]["block_type"], 3)

    async def test_convert_markdown_to_blocks_falls_back_when_scope_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = f"{tmpdir}/feishu_doc_state.json"
            service = _FakeFeishuDocsService(state_path)

            async def _fake_request_json(method, path, **kwargs):
                raise RuntimeError(
                    "Access denied: requires docx:document.block:convert"
                )

            service._request_json = _fake_request_json  # type: ignore[method-assign]

            write_payload = await service._convert_markdown_to_blocks(
                "token", "## 关键信息和观点\n- 要点A"
            )
            self.assertEqual(write_payload["mode"], "children")
            blocks = write_payload["children"]
            self.assertEqual(len(blocks), 2)
            self.assertEqual(blocks[0]["block_type"], 4)
            self.assertEqual(
                blocks[0]["heading2"]["elements"][0]["text_run"]["content"],
                "关键信息和观点",
            )


class TestFeishuDocsReplaceContent(unittest.IsolatedAsyncioTestCase):
    async def test_replace_doc_content_uses_descendant_for_convert_payload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = f"{tmpdir}/feishu_doc_state.json"
            service = FeishuDocsService(
                {
                    "enabled": True,
                    "app_id": "app-id",
                    "app_secret": "app-secret",
                    "wiki_space_id": "space-token",
                    "root_node_token": "",
                    "root_title": "AI视频知识库",
                    "state_path": state_path,
                    "request_timeout_seconds": 5,
                }
            )
            descendant_payloads = []
            children_calls = []

            async def _fake_request_json(method, path, **kwargs):
                if method == "GET" and path.endswith("children?page_size=500"):
                    return {"items": []}
                if method == "POST" and path == "/docx/v1/documents/blocks/convert":
                    return {
                        "first_level_block_ids": ["h1", "p1"],
                        "blocks": [
                            {
                                "block_id": "h1",
                                "revision_id": 1,
                                "parent_id": "",
                                "children": [],
                                "block_type": 3,
                                "heading1": {
                                    "elements": [{"text_run": {"content": "标题"}}]
                                },
                            },
                            {
                                "block_id": "p1",
                                "revision_id": 1,
                                "parent_id": "",
                                "children": [],
                                "block_type": 2,
                                "text": {
                                    "elements": [{"text_run": {"content": "段落"}}]
                                },
                            },
                        ],
                    }
                if (
                    method == "POST"
                    and path
                    == "/docx/v1/documents/doc-token/blocks/doc-token/descendant?document_revision_id=-1"
                ):
                    descendant_payloads.append(kwargs.get("payload", {}))
                    return {}
                if (
                    method == "POST"
                    and path == "/docx/v1/documents/doc-token/blocks/doc-token/children"
                ):
                    children_calls.append(kwargs.get("payload", {}))
                    return {}
                raise AssertionError(f"unexpected request: {method} {path}")

            service._request_json = _fake_request_json  # type: ignore[method-assign]

            await service._replace_doc_content(
                token="token",
                doc_token="doc-token",
                markdown="## 关键信息和观点\n- A\n\n## 时间线总结\n- 00:00 B",
            )

            self.assertEqual(len(descendant_payloads), 1)
            self.assertEqual(children_calls, [])
            self.assertEqual(descendant_payloads[0]["children_id"], ["h1", "p1"])
            self.assertEqual(len(descendant_payloads[0]["descendants"]), 2)

    async def test_replace_doc_content_fallbacks_to_children_on_descendant_schema_mismatch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = f"{tmpdir}/feishu_doc_state.json"
            service = FeishuDocsService(
                {
                    "enabled": True,
                    "app_id": "app-id",
                    "app_secret": "app-secret",
                    "wiki_space_id": "space-token",
                    "root_node_token": "",
                    "root_title": "AI视频知识库",
                    "state_path": state_path,
                    "request_timeout_seconds": 5,
                }
            )
            descendant_calls = 0
            children_calls = []

            async def _fake_request_json(method, path, **kwargs):
                nonlocal descendant_calls
                if method == "GET" and path.endswith("children?page_size=500"):
                    return {"items": []}
                if method == "POST" and path == "/docx/v1/documents/blocks/convert":
                    return {
                        "first_level_block_ids": ["h1", "p1"],
                        "blocks": [
                            {
                                "block_id": "h1",
                                "block_type": 3,
                                "children": [],
                                "heading1": {
                                    "elements": [{"text_run": {"content": "标题"}}]
                                },
                            },
                            {
                                "block_id": "p1",
                                "block_type": 2,
                                "children": [],
                                "text": {
                                    "elements": [{"text_run": {"content": "段落"}}]
                                },
                            },
                        ],
                    }
                if (
                    method == "POST"
                    and path
                    == "/docx/v1/documents/doc-token/blocks/doc-token/descendant?document_revision_id=-1"
                ):
                    descendant_calls += 1
                    raise RuntimeError(
                        "HTTP 400: {'code': 1770006, 'msg': 'schema mismatch'}"
                    )
                if (
                    method == "POST"
                    and path == "/docx/v1/documents/doc-token/blocks/doc-token/children"
                ):
                    children_calls.append(kwargs.get("payload", {}))
                    return {}
                raise AssertionError(f"unexpected request: {method} {path}")

            service._request_json = _fake_request_json  # type: ignore[method-assign]

            await service._replace_doc_content(
                token="token",
                doc_token="doc-token",
                markdown="## 关键信息和观点\n- A\n\n## 时间线总结\n- 00:00 B",
            )

            self.assertEqual(descendant_calls, 1)
            self.assertEqual(len(children_calls), 1)
            self.assertEqual(len(children_calls[0]["children"]), 4)
            self.assertEqual(children_calls[0]["children"][0]["block_type"], 4)

    async def test_replace_doc_content_sends_children_in_batches_of_50(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = f"{tmpdir}/feishu_doc_state.json"
            service = FeishuDocsService(
                {
                    "enabled": True,
                    "app_id": "app-id",
                    "app_secret": "app-secret",
                    "wiki_space_id": "space-token",
                    "root_node_token": "",
                    "root_title": "AI视频知识库",
                    "state_path": state_path,
                    "request_timeout_seconds": 5,
                }
            )
            batch_sizes = []

            async def _fake_request_json(method, path, **kwargs):
                if method == "GET" and path.endswith("children?page_size=500"):
                    return {"items": []}
                if method == "POST" and path == "/docx/v1/documents/blocks/convert":
                    return {
                        "children": [
                            {
                                "block_type": 2,
                                "text": {
                                    "elements": [
                                        {
                                            "text_run": {
                                                "content": f"line-{i}",
                                            }
                                        }
                                    ]
                                },
                            }
                            for i in range(120)
                        ]
                    }
                if (
                    method == "POST"
                    and path == "/docx/v1/documents/doc-token/blocks/doc-token/children"
                ):
                    children = kwargs.get("payload", {}).get("children", [])
                    batch_sizes.append(len(children))
                    return {}
                raise AssertionError(f"unexpected request: {method} {path}")

            service._request_json = _fake_request_json  # type: ignore[method-assign]

            await service._replace_doc_content(
                token="token",
                doc_token="doc-token",
                markdown="## 关键信息和观点\n- A\n\n## 时间线总结\n- 00:00 B",
            )

            self.assertEqual(batch_sizes, [50, 50, 20])


class TestFeishuDocsShareableUrl(unittest.IsolatedAsyncioTestCase):
    async def test_to_shareable_url_converts_docx_to_tenant_wiki_link(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = f"{tmpdir}/feishu_doc_state.json"
            service = FeishuDocsService(
                {
                    "enabled": True,
                    "app_id": "app-id",
                    "app_secret": "app-secret",
                    "wiki_space_id": "space-token",
                    "root_node_token": "",
                    "root_title": "AI视频知识库",
                    "state_path": state_path,
                    "request_timeout_seconds": 5,
                    "tenant_host": "tenant.feishu.cn",
                }
            )

            async def _fake_get_token():
                return "token"

            async def _fake_request_json(method, path, **kwargs):
                self.assertEqual(method, "GET")
                self.assertIn(
                    "/wiki/v2/spaces/get_node?token=doc-token-1&obj_type=docx", path
                )
                return {
                    "node": {
                        "node_token": "wiki-node-1",
                        "obj_token": "doc-token-1",
                    }
                }

            service._get_tenant_access_token = _fake_get_token  # type: ignore[method-assign]
            service._request_json = _fake_request_json  # type: ignore[method-assign]

            shareable = await service.to_shareable_url(
                "https://feishu.cn/docx/doc-token-1"
            )
            self.assertEqual(shareable, "https://tenant.feishu.cn/wiki/wiki-node-1")


if __name__ == "__main__":
    unittest.main()
