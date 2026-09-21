from __future__ import annotations

import hashlib
import logging

import redis
from flask import request

from cache.redis import redis_client
from settings import config

logger = logging.getLogger(__name__)


class LoginRateLimiter:
    PREFIX = "jsint:auth:login"

    @classmethod
    def _key(cls, email: str) -> str:
        remote = request.remote_addr or "unknown"
        normalized = email.strip().lower()
        digest = hashlib.sha256(f"{remote}|{normalized}".encode("utf-8")).hexdigest()
        return f"{cls.PREFIX}:{digest}"

    @classmethod
    def blocked(cls, email: str) -> bool:
        key = cls._key(email)
        try:
            current = redis_client.get(key)
        except redis.RedisError as exc:
            logger.error("Redis unavailable for login rate limit: %s", exc)
            if config.REDIS_REQUIRED:
                raise RuntimeError("Сервис защиты входа временно недоступен") from exc
            return False

        try:
            return int(current or "0") >= config.AUTH_RATE_LIMIT_ATTEMPTS
        except ValueError:
            return False

    @classmethod
    def record_failure(cls, email: str) -> int:
        key = cls._key(email)
        try:
            return redis_client.increment_with_expiry(
                key,
                config.AUTH_RATE_LIMIT_WINDOW_SECONDS,
            )
        except redis.RedisError as exc:
            logger.error("Redis unavailable for login rate limit: %s", exc)
            if config.REDIS_REQUIRED:
                raise RuntimeError("Сервис защиты входа временно недоступен") from exc
            return 0

    @classmethod
    def clear(cls, email: str) -> None:
        try:
            redis_client.delete(cls._key(email))
        except redis.RedisError:
            pass
