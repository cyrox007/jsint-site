from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from cache.manager import cache
from models.categories import Category
from schemas.category import CategoryOut


class CatalogService:
    TTL_DETAIL = 300
    TTL_LIST = 120

    @classmethod
    def get_category(cls, session: Session, cat_id: UUID) -> Optional[CategoryOut]:
        # Кеш по id
        cached = cache.get("category", str(cat_id), CategoryOut)
        if cached:
            return cached
        
        cat = Category.get_category_by_id(session, cat_id)
        if not cat:
            return None
        
        schema = CategoryOut.model_validate(cat)
        cache.set("publications", str(cat_id), schema, ttl=cls.TTL_DETAIL)
        return schema
    