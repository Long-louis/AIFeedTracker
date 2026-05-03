import unittest
from pathlib import Path


class TestProjectStructure(unittest.TestCase):
    def test_main_imports_logging_config_from_root(self):
        project_root = Path(__file__).resolve().parent.parent
        main_source = (project_root / "main.py").read_text(encoding="utf-8")
        self.assertIn("from logging_config import configure_logging", main_source)


if __name__ == "__main__":
    unittest.main()
