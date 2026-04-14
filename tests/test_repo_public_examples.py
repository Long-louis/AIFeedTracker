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
        self.assertIn("apps", data)
        self.assertEqual(set(data), {"defaults", "apps", "webhooks"})
        self.assertEqual(data["defaults"]["content"], "app:default")
        self.assertEqual(data["apps"]["default"]["receive_id_type"], "chat_id")

    def test_env_example_mentions_public_local_asr_boundary(self):
        content = Path("env.example").read_text(encoding="utf-8")
        self.assertIn("data/feishu_channels.json.example", content)
        self.assertIn("data/bilibili_creators.json.example", content)
        self.assertIn("FEISHU_TEMPLATE_ID", content)
        self.assertIn("LOCAL_ASR_PROVIDER=sensevoice_api", content)
        self.assertIn("ASR_API_URL=http://127.0.0.1:8900/v1/transcribe", content)
        self.assertIn("ASR_API_TIMEOUT_SECONDS=300", content)
        self.assertNotIn("deploy/.env.example", content)

    def test_env_example_mentions_optional_gpu_asr_path(self):
        content = Path("env.example").read_text(encoding="utf-8")
        self.assertIn("LOCAL_ASR_ENABLED=false", content)
        self.assertIn("LOCAL_ASR_MAX_AUDIO_MINUTES=90", content)
        self.assertIn("LOCAL_ASR_CLEANUP_TEMP_FILES=true", content)

    def test_env_example_mentions_feishu_docs_kb_settings(self):
        content = Path("env.example").read_text(encoding="utf-8")
        self.assertIn("FEISHU_DOCS_ENABLED", content)
        self.assertIn("FEISHU_DOCS_WIKI_SPACE_ID", content)
        self.assertIn("FEISHU_DOCS_STATE_PATH", content)


if __name__ == "__main__":
    unittest.main()
