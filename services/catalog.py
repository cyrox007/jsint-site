from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from cache.manager import cache
from models.categories import Category
from schemas.category import CategoryOut
from utils.validation import validate_slug


class CatalogService:
    TTL_DETAIL = 300
    TTL_LIST = 120

    @classmethod
    def get_category(cls, session: Session, cat_id: UUID) -> Optional[CategoryOut]:
        cached = cache.get("category", str(cat_id), CategoryOut)
        if cached:
            return cached

        cat = Category.get_by_id(session, cat_id)
        if not cat:
            return None

        schema = CategoryOut.model_validate(cat)
        cache.set("category", str(cat_id), schema, ttl=cls.TTL_DETAIL)
        return schema

    @classmethod
    def get_category_tree(cls, session: Session, parent_id: Optional[UUID] = None) -> List[dict]:
        cache_key = f"tree:{parent_id or 'root'}"
        cached = cache.get_list("category", cache_key, dict)
        if cached is not None:
            return cached

        tree = Category.get_tree(session, parent_id)
        if tree:
            cache.set_list("category", cache_key, tree, ttl=cls.TTL_LIST)
        return tree

    @classmethod
    def get_category_breadcrumbs(cls, session: Session, category_id: UUID) -> List[CategoryOut]:
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
    def create_category(cls, session: Session, data: dict) -> Optional[CategoryOut]:
        title = str(data.get("title") or "").strip()
        slug = validate_slug(str(data.get("slug") or ""))
        description = str(data.get("description") or "").strip() or None
        parent_id = data.get("parent_id")

        if not title or len(title) > 50:
            return None
        if parent_id is not None and Category.get_by_id(session, parent_id) is None:
            return None
        if Category.get_by_slug(session, slug) is not None:
            return None

        category = Category(
            title=title,
            slug=slug,
            description=description,
            parent_id=parent_id,
        )
        session.add(category)
        session.commit()
        session.refresh(category)

        cls.invalidate_category_cache()
        return CategoryOut.model_validate(category)

    @classmethod
    def update_category(cls, session: Session, cat_id: UUID, data: dict) -> Optional[CategoryOut]:
        category = Category.get_by_id(session, cat_id)
        if not category:
            return None

        title = str(data.get("title") or "").strip()
        slug = validate_slug(str(data.get("slug") or ""))
        description = str(data.get("description") or "").strip() or None
        parent_id = data.get("parent_id")

        if not title or len(title) > 50:
            return None

        existing = Category.get_by_slug(session, slug)
        if existing is not None and existing.id != cat_id:
            return None

        if parent_id is not None:
            if parent_id == cat_id or Category.get_by_id(session, parent_id) is None:
                return None
            descendants = {item.id for item in Category.get_all_descendants(session, cat_id)}
            if parent_id in descendants:
                return None

        category.title = title
        category.slug = slug
        category.description = description
        category.parent_id = parent_id

        session.commit()
        session.refresh(category)
        cls.invalidate_category_cache(category_id=cat_id)
        return CategoryOut.model_validate(category)

    @classmethod
    def delete_category(cls, session: Session, cat_id: UUID) -> bool:
        category = Category.get_by_id(session, cat_id)
        if not category:
            return False

        if session.query(Category).filter(Category.parent_id == cat_id).count() > 0:
            return False

        from models.publication import Publication
        if session.query(Publication).filter(Publication.category_id == cat_id).count() > 0:
            return False

        session.delete(category)
        session.commit()
        cls.invalidate_category_cache()
        return True

    @classmethod
    def invalidate_category_cache(cls, category_id: Optional[UUID] = None) -> None:
        if category_id:
            cache.invalidate("category", str(category_id))
        cache.delete_pattern(f"{cache.PREFIX}:category:tree:*")
        cache.delete_pattern(f"{cache.PREFIX}:category:breadcrumbs:*")
        if category_id is None:
            cache.invalidate("category")
