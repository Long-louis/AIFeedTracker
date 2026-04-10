from pathlib import Path
import json
import unittest


class TestRepoPublicExamples(unittest.TestCase):
    def test_hidden_env_example_is_not_shipped(self):
        self.assertFalse(Path(".env.example").exists())

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
        self.assertNotIn("apps", data)
        self.assertEqual(set(data), {"defaults", "webhooks"})

    def test_env_example_mentions_public_local_asr_boundary(self):
        content = Path("env.example").read_text(encoding="utf-8")
        self.assertIn("data/feishu_channels.json.example", content)
        self.assertIn("data/bilibili_creators.json.example", content)
        self.assertIn("FEISHU_TEMPLATE_ID", content)
        self.assertIn("LOCAL_ASR_ENABLED=false", content)
        self.assertIn("LOCAL_ASR_DEVICE=cpu", content)
        self.assertIn("LOCAL_ASR_COMPUTE_TYPE=int8", content)
        self.assertIn("faster_whisper", content)
        self.assertNotIn("deploy/.env.example", content)

    def test_env_example_mentions_optional_gpu_asr_path(self):
        content = Path("env.example").read_text(encoding="utf-8")
        self.assertIn("LOCAL_ASR_DEVICE=cuda", content)
        self.assertIn("LOCAL_ASR_COMPUTE_TYPE=float16", content)
        self.assertIn("deploy/docker-compose.gpu.yml", content)

    def test_env_example_mentions_feishu_docs_kb_settings(self):
        content = Path("env.example").read_text(encoding="utf-8")
        self.assertIn("FEISHU_DOCS_ENABLED", content)
        self.assertIn("FEISHU_DOCS_WIKI_SPACE_ID", content)
        self.assertIn("FEISHU_DOCS_STATE_PATH", content)


if __name__ == "__main__":
    unittest.main()
