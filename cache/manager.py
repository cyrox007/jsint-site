from __future__ import annotations

import json
import logging
from typing import Any, Optional, Type, TypeVar

import redis
from pydantic import BaseModel

from cache.redis import redis_client

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class CacheManager:
    PREFIX = "jsint"

    @classmethod
    def _make_key(cls, entity: str, identifier: str) -> str:
        return f"{cls.PREFIX}:{entity}:{identifier}"

    @staticmethod
    def _warn(operation: str, exc: Exception) -> None:
        logger.warning("Redis cache %s failed: %s", operation, exc)

    @classmethod
    def get(cls, entity: str, identifier: str, schema: Type[T]) -> Optional[T]:
        key = cls._make_key(entity, identifier)
        try:
            data = redis_client.get(key)
        except redis.RedisError as exc:
            cls._warn("get", exc)
            return None

        if data is None:
            return None
        try:
            return schema.model_validate_json(data)
        except Exception as exc:
            cls._warn("deserialize", exc)
            try:
                redis_client.delete(key)
            except redis.RedisError:
                pass
            return None

    @classmethod
    def set(cls, entity: str, identifier: str, data: BaseModel, ttl: int = 300) -> None:
        key = cls._make_key(entity, identifier)
        try:
            redis_client.set(key, data.model_dump_json(), ex=ttl)
        except redis.RedisError as exc:
            cls._warn("set", exc)

    @classmethod
    def get_list(cls, entity: str, params_hash: str, schema: Type[T] | type[dict]) -> Optional[list[Any]]:
        key = cls._make_key(entity, f"list:{params_hash}")
        try:
            data = redis_client.get(key)
        except redis.RedisError as exc:
            cls._warn("get_list", exc)
            return None

        if data is None:
            return None

        try:
            items = json.loads(data)
            if not isinstance(items, list):
                raise ValueError("cached list payload is not a list")
            if schema is dict:
                return [item for item in items if isinstance(item, dict)]
            return [schema.model_validate(item) for item in items]
        except Exception as exc:
            cls._warn("deserialize_list", exc)
            try:
                redis_client.delete(key)
            except redis.RedisError:
                pass
            return None

    @classmethod
    def set_list(cls, entity: str, params_hash: str, data: list[Any], ttl: int = 120) -> None:
        key = cls._make_key(entity, f"list:{params_hash}")
        payload_items = [
            item.model_dump(mode="json") if isinstance(item, BaseModel) else item
            for item in data
        ]
        try:
            redis_client.set(
                key,
                json.dumps(payload_items, ensure_ascii=False, default=str),
                ex=ttl,
            )
        except redis.RedisError as exc:
            cls._warn("set_list", exc)

    @classmethod
    def invalidate(cls, entity: str, identifier: Optional[str] = None) -> None:
        try:
            if identifier:
                redis_client.delete(cls._make_key(entity, identifier))
                redis_client.delete_pattern(f"{cls.PREFIX}:{entity}:list:*")
            else:
                redis_client.delete_pattern(f"{cls.PREFIX}:{entity}:*")
        except redis.RedisError as exc:
            cls._warn("invalidate", exc)

    @classmethod
    def delete_pattern(cls, pattern: str) -> None:
        try:
            redis_client.delete_pattern(pattern)
        except redis.RedisError as exc:
            cls._warn("delete_pattern", exc)


cache = CacheManager()
