from pathlib import Path
import unittest


class TestPublicDocs(unittest.TestCase):
    def test_private_repo_reference_removed_from_docs(self):
        bilibili = Path("docs/BILIBILI_SETUP.md").read_text(encoding="utf-8")
        feishu = Path("docs/FEISHU_CARD_SETUP.md").read_text(encoding="utf-8")
        ai = Path("docs/AI_SUMMARY_SETUP.md").read_text(encoding="utf-8")
        joined = "\n".join([bilibili, feishu, ai])
        self.assertNotIn("AIFeedTracker-private", joined)
        self.assertNotRegex(joined.lower(), r"\bscp\b")
        self.assertNotIn("私有部署", joined)
        self.assertNotIn("私有工作流", joined)

    def test_card_asset_still_exists(self):
        self.assertTrue(Path("docs/博主更新订阅.card").exists())

    def test_deploy_automation_doc_removed(self):
        self.assertFalse(Path("docs/DEPLOY_AUTOMATION.md").exists())

    def test_ai_summary_setup_mentions_public_local_asr_cpu_boundary(self):
        content = Path("docs/AI_SUMMARY_SETUP.md").read_text(encoding="utf-8")
        self.assertIn("LOCAL_ASR_ENABLED=false", content)
        self.assertIn("LOCAL_ASR_DEVICE=cpu", content)
        self.assertIn("faster_whisper", content)
        self.assertNotIn("deploy/.env.example", content)
        self.assertNotIn("docs/DEPLOY_AUTOMATION.md", content)
        self.assertNotRegex(content.lower(), r"\bscp\b")
        self.assertNotIn("私有部署", content)

    def test_dockerfile_does_not_duplicate_app_local_asr_defaults(self):
        content = Path("Dockerfile").read_text(encoding="utf-8")
        self.assertNotIn("ENV LOCAL_ASR_DEVICE=cpu", content)
        self.assertNotIn("ENV LOCAL_ASR_COMPUTE_TYPE=int8", content)

    def test_compose_documents_public_container_asr_runtime_limits(self):
        content = Path("deploy/docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn("当前镜像已包含 `ffmpeg`", content)
        self.assertIn("支持本地 ASR 音频处理与 CPU 执行", content)
        self.assertIn("单独启用 `gpus: all` 也不能", content)
        self.assertIn("CUDA/cuDNN 运行库", content)
        self.assertIn("包含 CUDA/cuDNN 运行时的镜像", content)
        self.assertNotIn("deploy/.env.example", content)
        self.assertNotRegex(content.lower(), r"\bscp\b")

    def test_gpu_deploy_files_exist(self):
        self.assertTrue(Path("Dockerfile.gpu").exists())
        self.assertTrue(Path("deploy/docker-compose.gpu.yml").exists())

    def test_gpu_compose_declares_gpu_runtime_path(self):
        content = Path("deploy/docker-compose.gpu.yml").read_text(encoding="utf-8")
        self.assertIn("dockerfile: Dockerfile.gpu", content)
        self.assertIn("runtime: nvidia", content)
        self.assertIn("NVIDIA_VISIBLE_DEVICES=all", content)
        self.assertIn("NVIDIA_DRIVER_CAPABILITIES=compute,utility", content)
        self.assertIn("NVIDIA Container Toolkit", content)
        self.assertNotIn("deploy/.env.example", content)
        self.assertNotRegex(content.lower(), r"\bscp\b")

    def test_ai_summary_setup_mentions_gpu_container_path(self):
        content = Path("docs/AI_SUMMARY_SETUP.md").read_text(encoding="utf-8")
        self.assertIn("deploy/docker-compose.gpu.yml", content)
        self.assertIn("NVIDIA Container Toolkit", content)
        self.assertNotRegex(content.lower(), r"\bscp\b")

    def test_ai_summary_setup_mentions_feishu_docs_kb_and_trimmed_sections(self):
        content = Path("docs/AI_SUMMARY_SETUP.md").read_text(encoding="utf-8")
        self.assertIn("## 视频总结输出结构", content)
        self.assertIn("## 关键信息和观点", content)
        self.assertIn("## 时间线总结", content)
        self.assertIn("FEISHU_DOCS_ENABLED=true", content)
        self.assertIn("根 -> 博主 -> YYYY-MM -> 视频文档", content)


if __name__ == "__main__":
    unittest.main()
