from typing import List, Optional
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
        
        cat = Category.get_by_id(session, cat_id)
        if not cat:
            return None
        
        schema = CategoryOut.model_validate(cat)
        cache.set("publications", str(cat_id), schema, ttl=cls.TTL_DETAIL)
        return schema
    
    @classmethod
    def get_category_tree(cls, session: Session, parent_id: Optional[UUID] = None) -> List[dict]:
        """
        Получить дерево категорий (с кешем).
        Кешируем по parent_id, чтобы можно было получать поддеревья.
        """
        cache_key = f"tree:{parent_id or 'root'}"
        cached = cache.get_list("category", cache_key, dict)  # dict для дерева
        if cached is not None:
            return cached

        tree = Category.get_tree(session, parent_id)
        if tree:
            cache.set_list("category", cache_key, tree, ttl=cls.TTL_LIST)
        return tree
    
    @classmethod
    def get_category_breadcrumbs(cls, session: Session, category_id: UUID) -> List[CategoryOut]:
        """Получить цепочку предков (хлебные крошки) с кешем."""
        cache_key = f"breadcrumbs:{category_id}"
        cached = cache.get_list("category", cache_key, CategoryOut)
        if cached is not None:
            return cached

        ancestors = Category.get_ancestors(session, category_id)
        schemas = [CategoryOut.model_validate(cat) for cat in ancestors]
        if schemas:
            cache.set_list("category", cache_key, schemas, ttl=cls.TTL_DETAIL)
        return schemas
    
    @classmethod
    def invalidate_category_cache(cls, category_id: Optional[UUID] = None):
        """
        Инвалидирует все кеши, связанные с категориями.
        - Если указан category_id – удаляет конкретную категорию и все её деревья/цепочки.
        - Если не указан – удаляет всё.
        """
        if category_id:
            cache.invalidate("category", str(category_id))
            # Также удаляем деревья и хлебные крошки, где могла фигурировать эта категория
            cache._delete_pattern(f"{cache.PREFIX}:category:tree:*")
            cache._delete_pattern(f"{cache.PREFIX}:category:breadcrumbs:*")
        else:
            cache.invalidate("category")
    