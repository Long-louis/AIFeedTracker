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
        self.assertNotIn("scp", content.lower())
        self.assertNotIn("deploy/.env.example", content)
        self.assertNotIn("docs/DEPLOY_AUTOMATION.md", content)

    def test_readme_contains_upgrade_notice(self):
        content = Path("README.md").read_text(encoding="utf-8")
        self.assertIn("升级", content)
        self.assertIn("配置文件", content)

    def test_readme_mentions_optional_local_asr_cpu_fallback(self):
        content = Path("README.md").read_text(encoding="utf-8")
        self.assertIn("本地 ASR", content)
        self.assertIn("可选", content)
        self.assertIn("CPU", content)


if __name__ == "__main__":
    unittest.main()
