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
        cat = Category.get_by_id(session, cat_id)
        if not cat:
            return None

        cache_key = f"{cat.site_id}:{cat_id}"
        cached = cache.get("category", cache_key, CategoryOut)
        if cached:
            return cached

        schema = CategoryOut.model_validate(cat)
        cache.set("category", cache_key, schema, ttl=cls.TTL_DETAIL)
        return schema

    @classmethod
    def get_category_tree(
        cls,
        session: Session,
        site_id: UUID,
        *,
        parent_id: UUID | None = None,
    ) -> List[dict]:
        cache_key = f"tree:{site_id}:{parent_id or 'root'}"
        cached = cache.get_list("category", cache_key, dict)
        if cached is not None:
            return cached

        tree = Category.get_tree(session, site_id, parent_id)
        if tree:
            cache.set_list("category", cache_key, tree, ttl=cls.TTL_LIST)
        return tree

    @classmethod
    def get_category_breadcrumbs(cls, session: Session, category_id: UUID) -> List[CategoryOut]:
        category = Category.get_by_id(session, category_id)
        if category is None:
            return []

        cache_key = f"breadcrumbs:{category.site_id}:{category_id}"
        cached = cache.get_list("category", cache_key, CategoryOut)
        if cached is not None:
            return cached

        schemas = [CategoryOut.model_validate(item) for item in Category.get_ancestors(session, category_id)]
        if schemas:
            cache.set_list("category", cache_key, schemas, ttl=cls.TTL_DETAIL)
        return schemas

    @classmethod
    def create_category(cls, session: Session, data: dict) -> Optional[CategoryOut]:
        site_id = data.get("site_id")
        title = str(data.get("title") or "").strip()
        slug = validate_slug(str(data.get("slug") or ""))
        description = str(data.get("description") or "").strip() or None
        parent_id = data.get("parent_id")

        if site_id is None or not title or len(title) > 50:
            return None
        if parent_id is not None and Category.get_by_id(session, parent_id, site_id) is None:
            return None
        if Category.get_by_slug(session, slug, site_id) is not None:
            return None

        category = Category(
            site_id=site_id,
            title=title,
            slug=slug,
            description=description,
            parent_id=parent_id,
        )
        session.add(category)
        session.commit()
        session.refresh(category)

        cls.invalidate_category_cache(site_id=site_id)
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

        existing = Category.get_by_slug(session, slug, category.site_id)
        if existing is not None and existing.id != cat_id:
            return None

        if parent_id is not None:
            if parent_id == cat_id or Category.get_by_id(session, parent_id, category.site_id) is None:
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
        cls.invalidate_category_cache(site_id=category.site_id, category_id=cat_id)
        return CategoryOut.model_validate(category)

    @classmethod
    def delete_category(cls, session: Session, cat_id: UUID) -> bool:
        category = Category.get_by_id(session, cat_id)
        if not category:
            return False

        if (
            session.query(Category)
            .filter(Category.site_id == category.site_id, Category.parent_id == cat_id)
            .count()
            > 0
        ):
            return False

        from models.publication import Publication, PublicationSite

        owner_publications = (
            session.query(Publication)
            .filter(
                Publication.site_id == category.site_id,
                Publication.category_id == cat_id,
            )
            .count()
        )
        channel_publications = (
            session.query(PublicationSite)
            .filter(
                PublicationSite.site_id == category.site_id,
                PublicationSite.category_id == cat_id,
            )
            .count()
        )
        if owner_publications > 0 or channel_publications > 0:
            return False

        site_id = category.site_id
        session.delete(category)
        session.commit()
        cls.invalidate_category_cache(site_id=site_id)
        return True

    @classmethod
    def invalidate_category_cache(
        cls,
        *,
        site_id: UUID,
        category_id: Optional[UUID] = None,
    ) -> None:
        if category_id:
            cache.invalidate("category", f"{site_id}:{category_id}")
        cache.delete_pattern(f"{cache.PREFIX}:category:tree:{site_id}:*")
        cache.delete_pattern(f"{cache.PREFIX}:category:breadcrumbs:{site_id}:*")
        cache.invalidate("publications")
