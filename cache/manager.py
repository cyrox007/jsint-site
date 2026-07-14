import json
from typing import Optional, Type, TypeVar
from pydantic import BaseModel

from cache.redis import redis_client

T = TypeVar("T", bound=BaseModel)


class CacheManager:
    PREFIX = "myapp"

    @classmethod
    def _make_key(cls, entity: str, identifier: str) -> str:
        return f"{cls.PREFIX}:{entity}:{identifier}"

    @classmethod
    def get(cls, entity: str, identifier: str, schema: Type[T]) -> Optional[T]:
        key = cls._make_key(entity, identifier)
        data = redis_client.get(key)
        if data is None:
            return None
        try:
            return schema.model_validate_json(data)
        except Exception as e:
            print(f"Ошибка десериализации кеша [{key}]: {e}")
            redis_client.delete(key)
            return None

    @classmethod
    def set(cls, entity: str, identifier: str, data: BaseModel, ttl: int = 300):
        key = cls._make_key(entity, identifier)
        redis_client.set(key, data.model_dump_json(), ex=ttl)

    @classmethod
    def get_list(cls, entity: str, params_hash: str, schema: Type[T]) -> Optional[list[T]]:
        key = cls._make_key(entity, f"list:{params_hash}")
        data = redis_client.get(key)
        if data is None:
            return None
        try:
            items = json.loads(data)
            return [schema.model_validate(item) for item in items]
        except Exception as e:
            print(f"Ошибка десериализации списка [{key}]: {e}")
            redis_client.delete(key)
            return None

    @classmethod
    def set_list(cls, entity: str, params_hash: str, data: list[BaseModel], ttl: int = 120):
        key = cls._make_key(entity, f"list:{params_hash}")
        payload = json.dumps([item.model_dump(mode="json") for item in data])
        redis_client.set(key, payload, ex=ttl)

    @classmethod
    def invalidate(cls, entity: str, identifier: Optional[str] = None):
        if identifier:
            cls._make_key(entity, identifier)
            redis_client.delete(cls._make_key(entity, identifier))
            redis_client.delete_pattern(f"{cls.PREFIX}:{entity}:list:*")
        else:
            redis_client.delete_pattern(f"{cls.PREFIX}:{entity}:*")


cache = CacheManager()