import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from creator_admin.creator_store import CreatorStore


class TestCreatorStore(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.data_path = Path(self._tmpdir.name) / "creators.json"
        self.store = CreatorStore(self.data_path)

    def test_load_raises_when_file_missing(self):
        with self.assertRaises(FileNotFoundError):
            self.store.load_creators()

    def test_load_raises_when_json_invalid(self):
        self.data_path.write_text("{invalid json", encoding="utf-8")

        with self.assertRaises(ValueError):
            self.store.load_creators()

    def test_load_raises_when_root_not_list(self):
        self.data_path.write_text(json.dumps({"uid": 1}), encoding="utf-8")

        with self.assertRaises(ValueError):
            self.store.load_creators()

    def test_load_raises_on_duplicate_uid(self):
        creators = [{"uid": 1, "name": "a"}, {"uid": 1, "name": "b"}]
        self.data_path.write_text(json.dumps(creators), encoding="utf-8")

        with self.assertRaises(ValueError):
            self.store.load_creators()

    def test_load_preserves_unknown_fields(self):
        creators = [
            {
                "uid": 1,
                "name": "creator",
                "platform": "bilibili",
                "custom_field": {"x": 1},
            }
        ]
        self.data_path.write_text(json.dumps(creators), encoding="utf-8")

        loaded = self.store.load_creators()

        self.assertEqual(creators, loaded)

    def test_load_normalizes_uid_string_to_int(self):
        creators = [{"uid": "100", "name": "creator", "custom_field": {"x": 1}}]
        self.data_path.write_text(json.dumps(creators), encoding="utf-8")

        loaded = self.store.load_creators()

        self.assertEqual(100, loaded[0]["uid"])
        self.assertEqual("creator", loaded[0]["name"])
        self.assertEqual({"x": 1}, loaded[0]["custom_field"])

    def test_load_raises_when_uid_missing(self):
        creators = [{"name": "creator"}]
        self.data_path.write_text(json.dumps(creators), encoding="utf-8")

        with self.assertRaises(ValueError):
            self.store.load_creators()

    def test_load_raises_when_uid_not_int(self):
        creators = [{"uid": "abc", "name": "creator"}]
        self.data_path.write_text(json.dumps(creators), encoding="utf-8")

        with self.assertRaises(ValueError):
            self.store.load_creators()

    def test_load_raises_when_uid_is_bool(self):
        creators = [{"uid": True, "name": "creator"}]
        self.data_path.write_text(json.dumps(creators), encoding="utf-8")

        with self.assertRaises(ValueError):
            self.store.load_creators()

    def test_load_raises_when_uid_non_positive(self):
        creators = [{"uid": 0, "name": "creator"}]
        self.data_path.write_text(json.dumps(creators), encoding="utf-8")

        with self.assertRaises(ValueError):
            self.store.load_creators()

    def test_save_raises_on_duplicate_uid(self):
        creators = [{"uid": 1, "name": "a"}, {"uid": 1, "name": "b"}]

        with self.assertRaises(ValueError):
            self.store.save_creators(creators)

    def test_save_writes_json_list_with_unknown_fields(self):
        creators = [
            {
                "uid": 100,
                "name": "creator",
                "platform": "bilibili",
                "custom_field": [1, 2, 3],
            }
        ]

        self.store.save_creators(creators)

        saved = json.loads(self.data_path.read_text(encoding="utf-8"))
        self.assertIsInstance(saved, list)
        self.assertEqual(creators, saved)

    def test_save_normalizes_uid_string_to_int(self):
        creators = [{"uid": "100", "name": "creator", "custom_field": [1, 2, 3]}]

        self.store.save_creators(creators)

        saved = json.loads(self.data_path.read_text(encoding="utf-8"))
        self.assertEqual(100, saved[0]["uid"])
        self.assertEqual("creator", saved[0]["name"])
        self.assertEqual([1, 2, 3], saved[0]["custom_field"])

    def test_save_raises_when_uid_missing(self):
        creators = [{"name": "creator"}]

        with self.assertRaises(ValueError):
            self.store.save_creators(creators)

    def test_save_raises_when_uid_not_int(self):
        creators = [{"uid": "abc", "name": "creator"}]

        with self.assertRaises(ValueError):
            self.store.save_creators(creators)

    def test_save_raises_when_uid_is_bool(self):
        creators = [{"uid": False, "name": "creator"}]

        with self.assertRaises(ValueError):
            self.store.save_creators(creators)

    def test_save_raises_when_uid_non_positive(self):
        creators = [{"uid": -1, "name": "creator"}]

        with self.assertRaises(ValueError):
            self.store.save_creators(creators)

    def test_save_uses_atomic_replace(self):
        creators = [{"uid": 100, "name": "creator"}]

        with patch("os.replace", wraps=os.replace) as replace_mock:
            self.store.save_creators(creators)

        self.assertEqual(1, replace_mock.call_count)
        src, dst = replace_mock.call_args.args
        self.assertNotEqual(src, dst)
        self.assertEqual(str(self.data_path), dst)

    def test_save_cleans_temp_file_when_replace_fails(self):
        creators = [{"uid": 100, "name": "creator"}]

        temp_path_holder = {}

        def replace_raises(src, dst):
            temp_path_holder["path"] = Path(src)
            raise OSError("replace failed")

        with patch("os.replace", side_effect=replace_raises):
            with self.assertRaises(OSError):
                self.store.save_creators(creators)

        self.assertIn("path", temp_path_holder)
        self.assertFalse(temp_path_holder["path"].exists())


if __name__ == "__main__":
    unittest.main()
