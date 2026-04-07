from pathlib import Path
import subprocess
import unittest


class TestPublicRepoReady(unittest.TestCase):
    def test_private_runtime_configs_not_tracked(self):
        tracked = subprocess.run(
            [
                "git",
                "ls-files",
                "data/bilibili_creators.json",
                "data/feishu_channels.json",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        self.assertEqual("", tracked)

    def test_public_entry_files_exist(self):
        required = [
            "README.md",
            "env.example",
            "data/bilibili_creators.json.example",
            "data/feishu_channels.json.example",
            "docs/BILIBILI_SETUP.md",
            "docs/FEISHU_CARD_SETUP.md",
            "docs/AI_SUMMARY_SETUP.md",
            "docs/博主更新订阅.card",
        ]
        for path in required:
            self.assertTrue(Path(path).exists(), path)

    def test_private_deploy_helpers_are_not_shipped(self):
        forbidden = [
            ".env.example",
            "deploy/.env.example",
            "scripts/commit-and-deploy.sh",
            "scripts/deploy-native.sh",
            "scripts/deploy.sh",
        ]
        for path in forbidden:
            self.assertFalse(Path(path).exists(), path)


if __name__ == "__main__":
    unittest.main()
