from __future__ import annotations

import logging

import redis

from cache.redis import redis_client
from settings import config


logger = logging.getLogger(__name__)


class DiagnosticRateLimiter:
    """Ограничивает загрузку диагностик по installation и глобально."""

    PREFIX = "jsint:notes:diagnostics"

    @classmethod
    def _key(cls, scope: str, installation_id: str = "") -> str:
        suffix = f":{installation_id}" if installation_id else ""
        return f"{cls.PREFIX}:{scope}{suffix}"

    @staticmethod
    def _read_int(key: str) -> int:
        current = redis_client.get(key)
        try:
            return int(current or "0")
        except ValueError:
            return 0

    @classmethod
    def blocked(cls, installation_id: str) -> bool:
        checks = (
            (
                cls._key("hour", installation_id),
                config.NOTES_DIAGNOSTIC_RATE_LIMIT_ATTEMPTS,
            ),
            (
                cls._key("day", installation_id),
                config.NOTES_DIAGNOSTIC_DAILY_LIMIT_ATTEMPTS,
            ),
            (
                cls._key("global-day"),
                config.NOTES_DIAGNOSTIC_GLOBAL_DAILY_LIMIT_ATTEMPTS,
            ),
        )
        try:
            return any(cls._read_int(key) >= limit for key, limit in checks)
        except redis.RedisError as exc:
            logger.error("Redis недоступен для защиты diagnostic upload: %s", exc)
            if config.REDIS_REQUIRED:
                raise RuntimeError(
                    "Сервис защиты диагностик временно недоступен"
                ) from exc
            return True

    @classmethod
    def record_attempt(cls, installation_id: str) -> None:
        try:
            redis_client.increment_with_expiry(
                cls._key("hour", installation_id),
                config.NOTES_DIAGNOSTIC_RATE_LIMIT_WINDOW_SECONDS,
            )
            redis_client.increment_with_expiry(
                cls._key("day", installation_id),
                config.NOTES_DIAGNOSTIC_DAILY_LIMIT_WINDOW_SECONDS,
            )
            redis_client.increment_with_expiry(
                cls._key("global-day"),
                config.NOTES_DIAGNOSTIC_DAILY_LIMIT_WINDOW_SECONDS,
            )
        except redis.RedisError as exc:
            logger.error("Redis недоступен при фиксации diagnostic upload: %s", exc)
            if config.REDIS_REQUIRED:
                raise RuntimeError(
                    "Сервис защиты диагностик временно недоступен"
                ) from exc
