import unittest
import runpy
from unittest.mock import patch

import main


class TestMainCreatorAdminMode(unittest.IsolatedAsyncioTestCase):
    async def test_creator_admin_mode_starts_admin_without_bot_initialization(self):
        with patch("sys.argv", ["main.py", "--mode", "creator-admin"]), patch(
            "main.AIVideoBot", side_effect=AssertionError("AIVideoBot should not start")
        ), patch("creator_admin.__main__.main") as admin_main:
            await main.main()

        admin_main.assert_called_once_with()

    async def test_creator_admin_script_entrypoint_bypasses_asyncio_run(self):
        with patch("sys.argv", ["main.py", "--mode", "creator-admin"]), patch(
            "asyncio.run", side_effect=AssertionError("asyncio.run should not start")
        ), patch("creator_admin.__main__.main") as admin_main:
            runpy.run_path("main.py", run_name="__main__")

        admin_main.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
