import base64
import hashlib
import hmac
import json
import time


class CookieAuth:
    def __init__(self, secret_key: str, ttl_seconds: int):
        if not secret_key:
            raise ValueError("secret_key is required")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than 0")
        self._secret = secret_key.encode("utf-8")
        self._ttl_seconds = ttl_seconds

    def sign(self, username: str) -> str:
        expires_at = int(time.time()) + self._ttl_seconds
        payload = {
            "username": username,
            "exp": expires_at,
        }
        payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        payload_b64 = self._b64url_encode(payload_bytes)
        signature = hmac.new(self._secret, payload_b64.encode("ascii"), hashlib.sha256).digest()
        signature_b64 = self._b64url_encode(signature)
        return f"{payload_b64}.{signature_b64}"

    def verify(self, token: str) -> dict | None:
        if not token or "." not in token:
            return None

        payload_b64, signature_b64 = token.split(".", 1)
        expected_sig = hmac.new(self._secret, payload_b64.encode("ascii"), hashlib.sha256).digest()
        expected_sig_b64 = self._b64url_encode(expected_sig)

        if not hmac.compare_digest(signature_b64, expected_sig_b64):
            return None

        try:
            payload_bytes = self._b64url_decode(payload_b64)
            payload = json.loads(payload_bytes.decode("utf-8"))
        except Exception:
            return None

        exp = payload.get("exp")
        if not isinstance(exp, int):
            return None
        if exp <= int(time.time()):
            return None

        username = payload.get("username")
        if not isinstance(username, str) or not username:
            return None

        return payload

    @staticmethod
    def _b64url_encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

    @staticmethod
    def _b64url_decode(value: str) -> bytes:
        padding = "=" * ((4 - len(value) % 4) % 4)
        return base64.urlsafe_b64decode(value + padding)
