from __future__ import annotations

import logging
from typing import Optional

import redis

from settings import config

logger = logging.getLogger(__name__)


class RedisClient:
    """Lazy Redis client used by cache and security rate limits."""

    def __init__(self) -> None:
        self._client: Optional[redis.Redis] = None

    def connect(self) -> redis.Redis:
        client = redis.from_url(
            config.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            health_check_interval=30,
        )
        client.ping()
        self._client = client
        return client

    def disconnect(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            finally:
                self._client = None

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            return self.connect()
        return self._client

    def ping(self) -> bool:
        try:
            return bool(self.client.ping())
        except redis.RedisError:
            self.disconnect()
            return False

    def get(self, key: str) -> Optional[str]:
        return self.client.get(key)

    def set(self, key: str, value: str, ex: Optional[int] = None) -> None:
        self.client.set(key, value, ex=ex)

    def set_if_absent(self, key: str, value: str, ttl: int) -> bool:
        return bool(self.client.set(key, value, ex=ttl, nx=True))

    def delete(self, key: str) -> None:
        self.client.delete(key)

    def delete_pattern(self, pattern: str) -> int:
        cursor = 0
        deleted = 0
        while True:
            cursor, keys = self.client.scan(cursor=cursor, match=pattern, count=100)
            if keys:
                deleted += int(self.client.delete(*keys))
            if cursor == 0:
                break
        return deleted

    def increment_with_expiry(self, key: str, ttl: int) -> int:
        pipe = self.client.pipeline(transaction=True)
        pipe.incr(key)
        pipe.expire(key, ttl)
        result = pipe.execute()
        return int(result[0])

    def ttl(self, key: str) -> int:
        return int(self.client.ttl(key))


redis_client = RedisClient()
