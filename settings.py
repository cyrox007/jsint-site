from __future__ import annotations

import os
from datetime import timedelta
from urllib.parse import quote

from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str) -> list[str]:
    raw = os.getenv(name, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


class Config:
    APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
    IS_PRODUCTION = APP_ENV == "production"

    SECRET_KEY = os.getenv("SECRET_KEY", "")
    ADMIN_ROUTE_PREFIX = os.getenv("ADMIN_ROUTE_PREFIX", "/x321/dashboard").rstrip("/") or "/x321/dashboard"
    ADMIN_EMAILS = {item.lower() for item in _env_list("ADMIN_EMAILS")}

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "js")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_SSLMODE = os.getenv("DB_SSLMODE", "prefer")

    REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    REDIS_REQUIRED = _env_bool("REDIS_REQUIRED", IS_PRODUCTION)
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/1")
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/2")

    ALLOWED_HOSTS = _env_list("ALLOWED_HOSTS")
    BEHIND_PROXY = _env_bool("BEHIND_PROXY", IS_PRODUCTION)

    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", IS_PRODUCTION)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "jsint_session")
    PERMANENT_SESSION_LIFETIME = timedelta(
        hours=max(1, int(os.getenv("SESSION_LIFETIME_HOURS", "12")))
    )

    MAX_CONTENT_LENGTH = max(64 * 1024, int(os.getenv("MAX_CONTENT_LENGTH", str(2 * 1024 * 1024))))
    PREFERRED_URL_SCHEME = "https" if IS_PRODUCTION else "http"

    AUTH_RATE_LIMIT_ATTEMPTS = max(1, int(os.getenv("AUTH_RATE_LIMIT_ATTEMPTS", "5")))
    AUTH_RATE_LIMIT_WINDOW_SECONDS = max(30, int(os.getenv("AUTH_RATE_LIMIT_WINDOW_SECONDS", "300")))

    YANDEX_METRIKA_ID = os.getenv("YANDEX_METRIKA_ID", "").strip()
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

    @classmethod
    def database_url(cls, async_mode: bool = False) -> str:
        driver = "postgresql+asyncpg" if async_mode else "postgresql"
        user = quote(cls.DB_USER, safe="")
        password = quote(cls.DB_PASSWORD, safe="")
        host = cls.DB_HOST.strip()
        port = cls.DB_PORT.strip()
        name = quote(cls.DB_NAME, safe="")
        ssl = f"?sslmode={quote(cls.DB_SSLMODE, safe='')}" if cls.DB_SSLMODE else ""
        return f"{driver}://{user}:{password}@{host}:{port}/{name}{ssl}"

    @classmethod
    def is_admin_email(cls, email: str) -> bool:
        if not cls.ADMIN_EMAILS:
            return not cls.IS_PRODUCTION
        return email.strip().lower() in cls.ADMIN_EMAILS

    @classmethod
    def validate(cls) -> None:
        unsafe_secret_keys = {
            "",
            "replace-with-at-least-32-random-characters",
            "fallback-secret-key-for-development",
            "development-only-secret-key-change-me",
        }
        if (
            not cls.SECRET_KEY
            or cls.SECRET_KEY in unsafe_secret_keys
            or len(cls.SECRET_KEY) < 32
        ):
            raise RuntimeError("SECRET_KEY must be a non-placeholder value of at least 32 characters")

        if not cls.ADMIN_ROUTE_PREFIX.startswith("/") or cls.ADMIN_ROUTE_PREFIX == "/":
            raise RuntimeError("ADMIN_ROUTE_PREFIX must be a non-root absolute URL path")

        if cls.IS_PRODUCTION:
            if not cls.ALLOWED_HOSTS:
                raise RuntimeError("ALLOWED_HOSTS is required in production")
            if not cls.ADMIN_EMAILS:
                raise RuntimeError("ADMIN_EMAILS is required in production")
            if not cls.SESSION_COOKIE_SECURE:
                raise RuntimeError("SESSION_COOKIE_SECURE must be enabled in production")
            if not cls.DB_PASSWORD:
                raise RuntimeError("DB_PASSWORD is required in production")
            if not cls.CELERY_BROKER_URL:
                raise RuntimeError("CELERY_BROKER_URL is required in production")
            if not cls.CELERY_RESULT_BACKEND:
                raise RuntimeError("CELERY_RESULT_BACKEND is required in production")


config = Config()
