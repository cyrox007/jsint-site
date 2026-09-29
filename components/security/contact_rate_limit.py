from __future__ import annotations

import hashlib
import logging

import redis
from flask import request

from cache.redis import redis_client
from settings import config

logger = logging.getLogger(__name__)


class ContactRateLimiter:
    PREFIX = "jsint:public:contact"

    @classmethod
    def _key(cls) -> str:
        remote = request.remote_addr or "unknown"
        digest = hashlib.sha256(remote.encode("utf-8")).hexdigest()
        return f"{cls.PREFIX}:{digest}"

    @classmethod
    def blocked(cls) -> bool:
        try:
            current = redis_client.get(cls._key())
        except redis.RedisError as exc:
            logger.error("Redis недоступен для защиты формы обратной связи: %s", exc)
            if config.REDIS_REQUIRED:
                raise RuntimeError("Сервис защиты формы временно недоступен") from exc
            return False

        try:
            return int(current or "0") >= config.CONTACT_RATE_LIMIT_ATTEMPTS
        except ValueError:
            return False

    @classmethod
    def record_submission(cls) -> int:
        try:
            return redis_client.increment_with_expiry(
                cls._key(),
                config.CONTACT_RATE_LIMIT_WINDOW_SECONDS,
            )
        except redis.RedisError as exc:
            logger.error("Redis недоступен для защиты формы обратной связи: %s", exc)
            if config.REDIS_REQUIRED:
                raise RuntimeError("Сервис защиты формы временно недоступен") from exc
            return 0
