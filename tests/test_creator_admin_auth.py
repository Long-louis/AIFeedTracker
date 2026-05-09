import hashlib
import hmac
import json
import os
import time
import unittest
from unittest.mock import patch

from creator_admin.auth import CookieAuth
from creator_admin.config import AdminSettings


class TestAdminSettings(unittest.TestCase):
    def test_from_env_uses_defaults_and_generates_dev_secret(self):
        env = {
            "CREATOR_ADMIN_PASSWORD": "secret-password",
        }

        with patch.dict(os.environ, env, clear=True):
            settings = AdminSettings.from_env()

        self.assertEqual("127.0.0.1", settings.host)
        self.assertEqual(8910, settings.port)
        self.assertEqual("data/bilibili_creators.json", settings.creators_file)
        self.assertEqual("secret-password", settings.password)
        self.assertIsInstance(settings.secret_key, str)
        self.assertTrue(len(settings.secret_key) >= 32)

    def test_from_env_requires_password(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "CREATOR_ADMIN_PASSWORD"):
                AdminSettings.from_env()

    def test_from_env_requires_int_port(self):
        env = {
            "CREATOR_ADMIN_PASSWORD": "secret-password",
            "CREATOR_ADMIN_PORT": "not-an-int",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(ValueError, "CREATOR_ADMIN_PORT"):
                AdminSettings.from_env()

    def test_from_env_requires_port_in_valid_range(self):
        for invalid_port in ("0", "65536"):
            env = {
                "CREATOR_ADMIN_PASSWORD": "secret-password",
                "CREATOR_ADMIN_PORT": invalid_port,
            }
            with patch.dict(os.environ, env, clear=True):
                with self.assertRaisesRegex(ValueError, "between 1 and 65535"):
                    AdminSettings.from_env()

    def test_from_env_requires_positive_cookie_ttl(self):
        env = {
            "CREATOR_ADMIN_PASSWORD": "secret-password",
            "CREATOR_ADMIN_COOKIE_TTL_SECONDS": "0",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(ValueError, "greater than 0"):
                AdminSettings.from_env()

    def test_from_env_requires_secret_in_production(self):
        env = {
            "CREATOR_ADMIN_PASSWORD": "secret-password",
            "CREATOR_ADMIN_ENV": "production",
        }

        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(ValueError, "CREATOR_ADMIN_SECRET_KEY"):
                AdminSettings.from_env()

    def test_from_env_requires_strong_secret_in_production(self):
        env = {
            "CREATOR_ADMIN_PASSWORD": "secret-password",
            "CREATOR_ADMIN_ENV": "production",
            "CREATOR_ADMIN_SECRET_KEY": "too-short",
        }

        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(ValueError, "minimum length is 32"):
                AdminSettings.from_env()

    def test_from_env_allows_disabling_secure_cookie_for_plain_http(self):
        env = {
            "CREATOR_ADMIN_PASSWORD": "secret-password",
            "CREATOR_ADMIN_ENV": "production",
            "CREATOR_ADMIN_SECRET_KEY": "k" * 32,
            "CREATOR_ADMIN_COOKIE_SECURE": "false",
        }

        with patch.dict(os.environ, env, clear=True):
            settings = AdminSettings.from_env()

        self.assertFalse(settings.cookie_secure)


class TestCookieAuth(unittest.TestCase):
    def test_sign_and_verify_success(self):
        auth = CookieAuth(secret_key="k" * 32, ttl_seconds=30)

        token = auth.sign("admin")

        payload = auth.verify(token)
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual("admin", payload["username"])

    def test_verify_rejects_tampered_token(self):
        auth = CookieAuth(secret_key="k" * 32, ttl_seconds=30)
        token = auth.sign("admin")
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")

        self.assertIsNone(auth.verify(tampered))

    def test_verify_rejects_expired_token(self):
        auth = CookieAuth(secret_key="k" * 32, ttl_seconds=1)
        token = auth.sign("admin")

        with patch("time.time", return_value=time.time() + 5):
            self.assertIsNone(auth.verify(token))

    def test_verify_rejects_token_when_exp_equals_now(self):
        auth = CookieAuth(secret_key="k" * 32, ttl_seconds=30)
        token = auth.sign("admin")
        payload = auth.verify(token)
        self.assertIsNotNone(payload)
        assert payload is not None

        with patch("time.time", return_value=payload["exp"]):
            self.assertIsNone(auth.verify(token))

    def test_verify_rejects_missing_empty_or_non_string_username(self):
        auth = CookieAuth(secret_key="k" * 32, ttl_seconds=30)

        invalid_payloads = [
            {"exp": int(time.time()) + 30},
            {"username": "", "exp": int(time.time()) + 30},
            {"username": 123, "exp": int(time.time()) + 30},
        ]

        for payload_dict in invalid_payloads:
            payload_bytes = json.dumps(payload_dict, separators=(",", ":")).encode("utf-8")
            payload_b64 = auth._b64url_encode(payload_bytes)
            signature = hmac.new(
                auth._secret,
                payload_b64.encode("ascii"),
                hashlib.sha256,
            ).digest()
            token = f"{payload_b64}.{auth._b64url_encode(signature)}"

            self.assertIsNone(auth.verify(token))

    def test_requires_positive_ttl(self):
        with self.assertRaisesRegex(ValueError, "greater than 0"):
            CookieAuth(secret_key="k" * 32, ttl_seconds=0)


if __name__ == "__main__":
    unittest.main()
