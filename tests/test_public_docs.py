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

    def test_dockerfile_sets_public_local_asr_cpu_defaults(self):
        content = Path("Dockerfile").read_text(encoding="utf-8")
        self.assertIn("ENV LOCAL_ASR_DEVICE=cpu", content)
        self.assertIn("ENV LOCAL_ASR_COMPUTE_TYPE=int8", content)

    def test_compose_documents_public_container_asr_runtime_limits(self):
        content = Path("deploy/docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn("当前镜像已包含 `ffmpeg`", content)
        self.assertIn("支持本地 ASR 音频处理与 CPU 执行", content)
        self.assertIn("单独启用 `gpus: all` 也不能", content)
        self.assertIn("CUDA/cuDNN 运行库", content)
        self.assertIn("包含 CUDA/cuDNN 运行时的镜像", content)
        self.assertNotIn("deploy/.env.example", content)
        self.assertNotRegex(content.lower(), r"\bscp\b")


if __name__ == "__main__":
    unittest.main()
