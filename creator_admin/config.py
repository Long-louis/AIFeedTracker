import os
import secrets
from dataclasses import dataclass


@dataclass(frozen=True)
class AdminSettings:
    host: str
    port: int
    creators_file: str
    password: str
    secret_key: str
    env: str
    cookie_name: str
    cookie_ttl_seconds: int

    @classmethod
    def from_env(cls) -> "AdminSettings":
        host = os.getenv("CREATOR_ADMIN_HOST", "127.0.0.1")
        port_raw = os.getenv("CREATOR_ADMIN_PORT", "8910")
        creators_file = os.getenv("CREATOR_ADMIN_CREATORS_FILE", "data/bilibili_creators.json")
        password = os.getenv("CREATOR_ADMIN_PASSWORD", "")
        env = os.getenv("CREATOR_ADMIN_ENV", "development").strip().lower()
        secret_key = os.getenv("CREATOR_ADMIN_SECRET_KEY", "")
        cookie_name = os.getenv("CREATOR_ADMIN_COOKIE_NAME", "creator_admin_session")
        ttl_raw = os.getenv("CREATOR_ADMIN_COOKIE_TTL_SECONDS", "86400")

        if not password:
            raise ValueError("CREATOR_ADMIN_PASSWORD is required")

        try:
            port = int(port_raw)
        except ValueError as exc:
            raise ValueError("CREATOR_ADMIN_PORT must be an integer") from exc
        if port < 1 or port > 65535:
            raise ValueError("CREATOR_ADMIN_PORT must be between 1 and 65535")

        try:
            cookie_ttl_seconds = int(ttl_raw)
        except ValueError as exc:
            raise ValueError("CREATOR_ADMIN_COOKIE_TTL_SECONDS must be an integer") from exc
        if cookie_ttl_seconds <= 0:
            raise ValueError("CREATOR_ADMIN_COOKIE_TTL_SECONDS must be greater than 0")

        if env == "production":
            if not secret_key:
                raise ValueError("CREATOR_ADMIN_SECRET_KEY is required in production")
            if len(secret_key) < 32:
                raise ValueError("CREATOR_ADMIN_SECRET_KEY is too weak; minimum length is 32")
        else:
            if not secret_key:
                secret_key = secrets.token_urlsafe(48)

        return cls(
            host=host,
            port=port,
            creators_file=creators_file,
            password=password,
            secret_key=secret_key,
            env=env,
            cookie_name=cookie_name,
            cookie_ttl_seconds=cookie_ttl_seconds,
        )
