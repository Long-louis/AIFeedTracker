from pathlib import Path
import json
import unittest


class TestRepoPublicExamples(unittest.TestCase):
    def test_creators_example_is_valid_json(self):
        data = json.loads(
            Path("data/bilibili_creators.json.example").read_text(encoding="utf-8")
        )
        self.assertIsInstance(data, list)
        self.assertIn("uid", data[0])
        self.assertIn("crons", data[0])
        self.assertIn("feishu_channel", data[0])

    def test_feishu_channels_example_is_valid_json(self):
        data = json.loads(
            Path("data/feishu_channels.json.example").read_text(encoding="utf-8")
        )
        self.assertIn("defaults", data)
        self.assertIn("webhooks", data)
        self.assertNotIn(
            ',\n  "apps"',
            Path("data/feishu_channels.json.example").read_text(encoding="utf-8"),
        )

    def test_env_example_mentions_current_config_files(self):
        content = Path("env.example").read_text(encoding="utf-8")
        self.assertIn("data/feishu_channels.json.example", content)
        self.assertIn("data/bilibili_creators.json.example", content)
        self.assertIn("FEISHU_TEMPLATE_ID", content)


if __name__ == "__main__":
    unittest.main()
