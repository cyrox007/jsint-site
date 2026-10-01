from __future__ import annotations

import os
import re
from datetime import timedelta
from urllib.parse import quote, urlparse

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
    MEDIA_STORAGE_PATH = os.getenv(
        "MEDIA_STORAGE_PATH",
        "/var/lib/jsint-site/media" if IS_PRODUCTION else os.path.join(BASE_DIR, "storage", "media"),
    ).strip()
    MEDIA_UPLOAD_MAX_BYTES = min(
        MAX_CONTENT_LENGTH,
        max(
            64 * 1024,
            int(os.getenv("MEDIA_UPLOAD_MAX_BYTES", str(2 * 1024 * 1024))),
        ),
    )
    PREFERRED_URL_SCHEME = "https" if IS_PRODUCTION else "http"

    AUTH_RATE_LIMIT_ATTEMPTS = max(1, int(os.getenv("AUTH_RATE_LIMIT_ATTEMPTS", "5")))
    AUTH_RATE_LIMIT_WINDOW_SECONDS = max(30, int(os.getenv("AUTH_RATE_LIMIT_WINDOW_SECONDS", "300")))
    CONTACT_RATE_LIMIT_ATTEMPTS = max(1, int(os.getenv("CONTACT_RATE_LIMIT_ATTEMPTS", "3")))
    CONTACT_RATE_LIMIT_WINDOW_SECONDS = max(
        60,
        int(os.getenv("CONTACT_RATE_LIMIT_WINDOW_SECONDS", "900")),
    )
    CONTACT_DAILY_LIMIT_ATTEMPTS = max(
        CONTACT_RATE_LIMIT_ATTEMPTS,
        int(os.getenv("CONTACT_DAILY_LIMIT_ATTEMPTS", "10")),
    )
    CONTACT_DAILY_LIMIT_WINDOW_SECONDS = max(
        CONTACT_RATE_LIMIT_WINDOW_SECONDS,
        int(os.getenv("CONTACT_DAILY_LIMIT_WINDOW_SECONDS", "86400")),
    )
    CONTACT_GLOBAL_LIMIT_ATTEMPTS = max(
        CONTACT_DAILY_LIMIT_ATTEMPTS,
        int(os.getenv("CONTACT_GLOBAL_LIMIT_ATTEMPTS", "120")),
    )
    CONTACT_GLOBAL_LIMIT_WINDOW_SECONDS = max(
        60,
        int(os.getenv("CONTACT_GLOBAL_LIMIT_WINDOW_SECONDS", "600")),
    )
    CONTACT_REPLY_LIMIT_ATTEMPTS = max(
        1,
        int(os.getenv("CONTACT_REPLY_LIMIT_ATTEMPTS", "3")),
    )
    CONTACT_DUPLICATE_WINDOW_SECONDS = max(
        3600,
        int(os.getenv("CONTACT_DUPLICATE_WINDOW_SECONDS", "604800")),
    )
    CONTACT_FORM_MIN_SECONDS = max(
        1,
        int(os.getenv("CONTACT_FORM_MIN_SECONDS", "3")),
    )
    CONTACT_FORM_TTL_SECONDS = max(
        300,
        int(os.getenv("CONTACT_FORM_TTL_SECONDS", "1800")),
    )
    CONTACT_MAX_URLS = max(0, int(os.getenv("CONTACT_MAX_URLS", "3")))
    CONTACT_MAX_REQUEST_BYTES = max(
        4096,
        min(64 * 1024, int(os.getenv("CONTACT_MAX_REQUEST_BYTES", "16384"))),
    )
    CONTACT_TURNSTILE_SITE_KEY = os.getenv("CONTACT_TURNSTILE_SITE_KEY", "").strip()
    CONTACT_TURNSTILE_SECRET_KEY = os.getenv("CONTACT_TURNSTILE_SECRET_KEY", "").strip()
    CONTACT_TURNSTILE_REQUIRED = _env_bool("CONTACT_TURNSTILE_REQUIRED", False)

    YANDEX_METRIKA_ID = os.getenv("YANDEX_METRIKA_ID", "").strip()
    YANDEX_WEBMASTER_VERIFICATION = os.getenv(
        "YANDEX_WEBMASTER_VERIFICATION",
        "725d05a47d08b13d",
    ).strip()
    YANDEX_INDEXNOW_ENABLED = _env_bool("YANDEX_INDEXNOW_ENABLED", IS_PRODUCTION)
    YANDEX_INDEXNOW_KEY = os.getenv(
        "YANDEX_INDEXNOW_KEY",
        "jsinteractive-indexnow-725d05a47d08b13d",
    ).strip()
    SITE_BASE_URL = os.getenv(
        "SITE_BASE_URL",
        "https://jsinteractive.ru" if IS_PRODUCTION else "http://localhost:5000",
    ).strip().rstrip("/")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

    # Внутренние уведомления администратора и опциональный push на телефон.
    # ADMIN_PUSH_URL совместим с ntfy topic URL или собственным HTTP endpoint.
    ADMIN_PUSH_URL = os.getenv("ADMIN_PUSH_URL", "").strip()
    ADMIN_PUSH_TOKEN = os.getenv("ADMIN_PUSH_TOKEN", "").strip()
    ADMIN_PUSH_TIMEOUT_SECONDS = max(
        2,
        min(30, int(os.getenv("ADMIN_PUSH_TIMEOUT_SECONDS", "8"))),
    )

    NOTES_DIAGNOSTIC_STORAGE_PATH = os.getenv(
        "NOTES_DIAGNOSTIC_STORAGE_PATH",
        "/var/lib/jsint-site/diagnostics" if IS_PRODUCTION else os.path.join(BASE_DIR, "storage", "diagnostics"),
    ).strip()
    NOTES_DIAGNOSTIC_UPLOAD_MAX_BYTES = max(
        1024 * 1024,
        min(
            64 * 1024 * 1024,
            int(os.getenv("NOTES_DIAGNOSTIC_UPLOAD_MAX_BYTES", str(10 * 1024 * 1024))),
        ),
    )

    VANGA_DEMO_URL = os.getenv("VANGA_DEMO_URL", "http://127.0.0.1:9100").strip().rstrip("/")
    VANGA_DEMO_TIMEOUT_SECONDS = max(1, min(30, int(os.getenv("VANGA_DEMO_TIMEOUT_SECONDS", "10"))))

    NOTES_CONTROL_PLANE_ENABLED = _env_bool("NOTES_CONTROL_PLANE_ENABLED", False)
    NOTES_UPDATE_API_PREFIX = os.getenv("NOTES_UPDATE_API_PREFIX", "/api/notes/v1").strip().rstrip("/")
    NOTES_UPDATE_BASE_URL = os.getenv("NOTES_UPDATE_BASE_URL", "").strip()
    NOTES_RELEASE_STORAGE_PATH = os.getenv(
        "NOTES_RELEASE_STORAGE_PATH", "/var/lib/jsint-site/notes-releases"
    ).strip()
    NOTES_RELEASE_UPLOAD_MAX_BYTES = max(
        1024 * 1024,
        int(os.getenv("NOTES_RELEASE_UPLOAD_MAX_BYTES", str(512 * 1024 * 1024))),
    )
    NOTES_OPERATOR_SIGNER_URL = os.getenv(
        "NOTES_OPERATOR_SIGNER_URL", "http://127.0.0.1:17843/v1"
    ).strip().rstrip("/")
    NOTES_RELEASE_GITHUB_REPOSITORY = os.getenv(
        "NOTES_RELEASE_GITHUB_REPOSITORY", "cyrox007/Notes"
    ).strip()
    NOTES_RELEASE_GITHUB_TOKEN = os.getenv("NOTES_RELEASE_GITHUB_TOKEN", "").strip()
    NOTES_RELEASE_DEFAULT_REQUIRES_PHP = os.getenv(
        "NOTES_RELEASE_DEFAULT_REQUIRES_PHP", "8.1.0"
    ).strip()
    OPERATOR_AUDIT_RETENTION_DAYS = max(
        30,
        int(os.getenv("OPERATOR_AUDIT_RETENTION_DAYS", "730")),
    )
    LICENSE_REVOKED_RETENTION_DAYS = max(
        30,
        int(os.getenv("LICENSE_REVOKED_RETENTION_DAYS", "30")),
    )

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

        parsed_site_url = urlparse(cls.SITE_BASE_URL)
        if (
            parsed_site_url.scheme not in {"http", "https"}
            or not parsed_site_url.hostname
            or parsed_site_url.username is not None
            or parsed_site_url.password is not None
            or parsed_site_url.query
            or parsed_site_url.fragment
            or parsed_site_url.path not in {"", "/"}
        ):
            raise RuntimeError("SITE_BASE_URL must be an absolute origin URL without path/query/fragment")

        if not os.path.isabs(cls.MEDIA_STORAGE_PATH):
            raise RuntimeError("MEDIA_STORAGE_PATH must be an absolute external path")

        if cls.CONTACT_TURNSTILE_REQUIRED and (
            not cls.CONTACT_TURNSTILE_SITE_KEY or not cls.CONTACT_TURNSTILE_SECRET_KEY
        ):
            raise RuntimeError(
                "CONTACT_TURNSTILE_REQUIRED требует CONTACT_TURNSTILE_SITE_KEY и "
                "CONTACT_TURNSTILE_SECRET_KEY"
            )

        if bool(cls.CONTACT_TURNSTILE_SITE_KEY) != bool(cls.CONTACT_TURNSTILE_SECRET_KEY):
            raise RuntimeError(
                "CONTACT_TURNSTILE_SITE_KEY и CONTACT_TURNSTILE_SECRET_KEY должны "
                "задаваться одновременно"
            )

        if cls.YANDEX_WEBMASTER_VERIFICATION and re.fullmatch(
            r"[A-Za-z0-9_-]{8,128}",
            cls.YANDEX_WEBMASTER_VERIFICATION,
        ) is None:
            raise RuntimeError("Некорректный YANDEX_WEBMASTER_VERIFICATION")

        if cls.YANDEX_INDEXNOW_ENABLED and re.fullmatch(
            r"[A-Za-z0-9-]{8,128}",
            cls.YANDEX_INDEXNOW_KEY,
        ) is None:
            raise RuntimeError("Некорректный YANDEX_INDEXNOW_KEY")

        if cls.ADMIN_PUSH_URL:
            push = urlparse(cls.ADMIN_PUSH_URL)
            push_host = (push.hostname or "").lower()
            loopback_push = push_host in {"127.0.0.1", "localhost", "::1"}
            if (
                push.scheme not in ({"http", "https"} if loopback_push else {"https"})
                or not push.hostname
                or push.username is not None
                or push.password is not None
                or push.fragment
            ):
                raise RuntimeError("Некорректный ADMIN_PUSH_URL")

        if not os.path.isabs(cls.NOTES_DIAGNOSTIC_STORAGE_PATH):
            raise RuntimeError("NOTES_DIAGNOSTIC_STORAGE_PATH должен быть абсолютным путём")

        if cls.IS_PRODUCTION:
            if parsed_site_url.scheme != "https":
                raise RuntimeError("SITE_BASE_URL must use HTTPS in production")
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

        if cls.NOTES_CONTROL_PLANE_ENABLED:
            if not cls.NOTES_UPDATE_API_PREFIX.startswith("/") or cls.NOTES_UPDATE_API_PREFIX == "/":
                raise RuntimeError("NOTES_UPDATE_API_PREFIX must be a non-root absolute URL path")
            parsed = urlparse(cls.NOTES_UPDATE_BASE_URL)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or "." not in parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.query
                or parsed.fragment
                or not parsed.path.endswith("/")
                or re.fullmatch(r"/(?:[A-Za-z0-9_-]+/)*", parsed.path) is None
            ):
                raise RuntimeError("NOTES_UPDATE_BASE_URL must be a canonical HTTPS directory URL")
            if not os.path.isabs(cls.NOTES_RELEASE_STORAGE_PATH):
                raise RuntimeError("NOTES_RELEASE_STORAGE_PATH must be an absolute external path")
            if re.fullmatch(
                r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",
                cls.NOTES_RELEASE_GITHUB_REPOSITORY,
            ) is None:
                raise RuntimeError("Некорректный NOTES_RELEASE_GITHUB_REPOSITORY")
            if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", cls.NOTES_RELEASE_DEFAULT_REQUIRES_PHP) is None:
                raise RuntimeError("Некорректный NOTES_RELEASE_DEFAULT_REQUIRES_PHP")
            signer = urlparse(cls.NOTES_OPERATOR_SIGNER_URL)
            signer_host = (signer.hostname or "").lower()
            if (
                signer.scheme != "http"
                or signer_host not in {"127.0.0.1", "localhost", "::1"}
                or signer.username is not None
                or signer.password is not None
                or signer.query
                or signer.fragment
            ):
                raise RuntimeError(
                    "NOTES_OPERATOR_SIGNER_URL must point to a loopback HTTP origin"
                )


config = Config()
