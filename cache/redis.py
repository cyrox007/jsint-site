import json
from typing import Optional
import redis

from settings import config


class RedisClient:
    """Синхронный клиент Redis для Flask."""

    def __init__(self):
        self._client: Optional[redis.Redis] = None

    def connect(self):
        self._client = redis.from_url(
            config.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
        self._client.ping()
        print("✅ Redis подключен")

    def disconnect(self):
        if self._client:
            self._client.close()

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            self.connect()
        return self._client

    def get(self, key: str) -> Optional[str]:
        return self.client.get(key)

    def set(self, key: str, value: str, ex: Optional[int] = None):
        self.client.set(key, value, ex=ex)

    def delete(self, key: str):
        self.client.delete(key)

    def delete_pattern(self, pattern: str) -> int:
        """Удаляет все ключи по паттерну."""
        cursor = 0
        deleted = 0
        while True:
            cursor, keys = self.client.scan(cursor=cursor, match=pattern, count=100)
            if keys:
                deleted += self.client.delete(*keys)
            if cursor == 0:
                break
        return deleted


redis_client = RedisClient()