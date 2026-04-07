from pathlib import Path
import unittest


class TestPublicDocs(unittest.TestCase):
    def test_private_repo_reference_removed_from_docs(self):
        bilibili = Path("docs/BILIBILI_SETUP.md").read_text(encoding="utf-8")
        feishu = Path("docs/FEISHU_CARD_SETUP.md").read_text(encoding="utf-8")
        ai = Path("docs/AI_SUMMARY_SETUP.md").read_text(encoding="utf-8")
        joined = "\n".join([bilibili, feishu, ai])
        self.assertNotIn("AIFeedTracker-private", joined)
        self.assertNotIn("scp", joined.lower())

    def test_card_asset_still_exists(self):
        self.assertTrue(Path("docs/博主更新订阅.card").exists())

    def test_deploy_automation_doc_removed(self):
        self.assertFalse(Path("docs/DEPLOY_AUTOMATION.md").exists())


if __name__ == "__main__":
    unittest.main()
