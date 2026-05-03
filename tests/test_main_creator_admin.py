import unittest
from unittest.mock import patch

import main


class TestMainCreatorAdminMode(unittest.IsolatedAsyncioTestCase):
    async def test_creator_admin_mode_starts_admin_without_bot_initialization(self):
        with patch("sys.argv", ["main.py", "--mode", "creator-admin"]), patch(
            "main.AIVideoBot", side_effect=AssertionError("AIVideoBot should not start")
        ), patch("creator_admin.__main__.main") as admin_main:
            await main.main()

        admin_main.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
