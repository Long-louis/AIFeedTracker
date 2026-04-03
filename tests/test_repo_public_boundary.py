from pathlib import Path
import unittest


class TestRepoPublicBoundary(unittest.TestCase):
    def test_gitignore_ignores_private_runtime_configs(self):
        lines = set(Path(".gitignore").read_text(encoding="utf-8").splitlines())
        self.assertIn("data/bilibili_creators.json", lines)
        self.assertIn("data/feishu_channels.json", lines)

    def test_examples_remain_public(self):
        lines = set(Path(".gitignore").read_text(encoding="utf-8").splitlines())
        self.assertNotIn("data/bilibili_creators.json.example", lines)
        self.assertNotIn("data/feishu_channels.json.example", lines)


if __name__ == "__main__":
    unittest.main()
