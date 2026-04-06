# -*- coding: utf-8 -*-

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bilibili_api import login_v2

from services.bilibili_auth import BilibiliAuth


class _FakePicture:
    def to_file(self, path):
        Path(path).write_text("fake-qr", encoding="utf-8")


class _FakeQrCodeLogin:
    generated_temp_path = None

    async def generate_qrcode(self):
        self.__class__.generated_temp_path = (
            Path(login_v2.tempfile.gettempdir()) / "qrcode.png"
        )
        self._picture = _FakePicture()

    def get_qrcode_picture(self):
        return self._picture


class TestBilibiliAuthQrLogin(unittest.IsolatedAsyncioTestCase):
    async def test_start_qr_login_uses_project_temp_dir_for_library_qr_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            auth_path = Path(tmpdir) / "data" / "bilibili_auth.json"
            qr_path = Path(tmpdir) / "temp" / "bilibili_qrcode.png"

            with (
                patch.object(BilibiliAuth, "AUTH_DATA_PATH", auth_path),
                patch.object(BilibiliAuth, "QR_CODE_PATH", qr_path),
                patch.object(login_v2, "QrCodeLogin", _FakeQrCodeLogin),
                patch.object(login_v2.tempfile, "tempdir", "/tmp"),
            ):
                auth = BilibiliAuth()

                returned_path = await auth.start_qr_login()

                self.assertEqual(returned_path, str(qr_path))
                self.assertTrue(qr_path.exists())
                self.assertIsNotNone(_FakeQrCodeLogin.generated_temp_path)
                self.assertTrue(
                    _FakeQrCodeLogin.generated_temp_path.is_relative_to(qr_path.parent)
                )
                self.assertEqual(login_v2.tempfile.tempdir, "/tmp")


if __name__ == "__main__":
    unittest.main()
