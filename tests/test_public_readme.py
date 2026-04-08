from pathlib import Path
import unittest


class TestPublicReadme(unittest.TestCase):
    def test_readme_mentions_example_based_setup(self):
        content = Path("README.md").read_text(encoding="utf-8")
        self.assertIn("env.example", content)
        self.assertIn("data/feishu_channels.json.example", content)
        self.assertIn("data/bilibili_creators.json.example", content)

    def test_readme_does_not_mention_private_repo_or_scp(self):
        content = Path("README.md").read_text(encoding="utf-8")
        self.assertNotIn("AIFeedTracker-private", content)
        self.assertNotRegex(content.lower(), r"\bscp\b")
        self.assertNotIn("deploy/.env.example", content)
        self.assertNotIn("docs/DEPLOY_AUTOMATION.md", content)
        self.assertNotIn("私有部署", content)
        self.assertNotIn("私有工作流", content)

    def test_readme_contains_upgrade_notice(self):
        content = Path("README.md").read_text(encoding="utf-8")
        self.assertIn("升级", content)
        self.assertIn("配置文件", content)

    def test_readme_mentions_local_asr_fallback_wording(self):
        content = Path("README.md").read_text(encoding="utf-8")
        self.assertIn("本地 ASR", content)
        self.assertIn("回退", content)

    def test_readme_mentions_local_asr_disable_flag(self):
        content = Path("README.md").read_text(encoding="utf-8")
        self.assertIn("LOCAL_ASR_ENABLED=false", content)

    def test_readme_mentions_local_asr_cpu_mode(self):
        content = Path("README.md").read_text(encoding="utf-8")
        self.assertIn("LOCAL_ASR_DEVICE=cpu", content)

    def test_readme_mentions_faster_whisper_boundary(self):
        content = Path("README.md").read_text(encoding="utf-8")
        self.assertIn("faster_whisper", content)


if __name__ == "__main__":
    unittest.main()
