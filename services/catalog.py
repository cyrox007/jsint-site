from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from cache.manager import cache
from models.categories import Category
from schemas.category import CategoryOut


class CatalogService:
    TTL_DETAIL = 300
    TTL_LIST = 120

    # ========== ЧТЕНИЕ ==========

    @classmethod
    def get_category(cls, session: Session, cat_id: UUID) -> Optional[CategoryOut]:
        cached = cache.get("category", str(cat_id), CategoryOut)
        if cached:
            return cached

        cat = Category.get_by_id(session, cat_id)
        if not cat:
            return None

        schema = CategoryOut.model_validate(cat)
        cache.set("category", str(cat_id), schema, ttl=cls.TTL_DETAIL)  # исправлено
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

    # ========== СОЗДАНИЕ ==========

    @classmethod
    def create_category(cls, session: Session, data: dict) -> Optional[CategoryOut]:
        """Создать новую категорию."""
        title = data.get('title')
        slug = data.get('slug')
        description = data.get('description')
        parent_id = data.get('parent_id')

        # Проверка обязательных полей
        if not title or not slug:
            return None

        # Проверка уникальности slug
        existing = Category.get_by_slug(session, slug)
        if existing:
            return None

        category = Category(
            title=title,
            slug=slug,
            description=description,
            parent_id=parent_id
        )
        session.add(category)
        session.commit()
        session.refresh(category)

        # Инвалидируем кеш деревьев
        cls.invalidate_category_cache()
        return CategoryOut.model_validate(category)

    # ========== ОБНОВЛЕНИЕ ==========

    @classmethod
    def update_category(cls, session: Session, cat_id: UUID, data: dict) -> Optional[CategoryOut]:
        """Обновить категорию."""
        category = Category.get_by_id(session, cat_id)
        if not category:
            return None

        # Проверка слага (если меняется)
        new_slug = data.get('slug')
        if new_slug and new_slug != category.slug:
            existing = Category.get_by_slug(session, new_slug)
            if existing and existing.id != cat_id:
                return None

        # Применяем изменения
        if 'title' in data:
            category.title = data['title']
        if 'slug' in data:
            category.slug = data['slug']
        if 'description' in data:
            category.description = data['description']
        if 'parent_id' in data:
            category.parent_id = data['parent_id']

        session.commit()
        session.refresh(category)

        # Инвалидируем кеш (конкретную категорию и все деревья)
        cls.invalidate_category_cache(category_id=cat_id)
        return CategoryOut.model_validate(category)

    # ========== УДАЛЕНИЕ ==========

    @classmethod
    def delete_category(cls, session: Session, cat_id: UUID) -> bool:
        """Удалить категорию (только если нет дочерних и публикаций)."""
        category = Category.get_by_id(session, cat_id)
        if not category:
            return False

        # Проверка на дочерние категории
        from models.categories import Category as CategoryModel
        children = session.query(CategoryModel).filter(CategoryModel.parent_id == cat_id).count()
        if children > 0:
            return False

        # Проверка на публикации
        from models.publication import Publication
        pubs = session.query(Publication).filter(Publication.category_id == cat_id).count()
        if pubs > 0:
            return False

        session.delete(category)
        session.commit()

        # Инвалидируем кеш
        cls.invalidate_category_cache()
        return True

    # ========== ИНВАЛИДАЦИЯ КЕША ==========

    @classmethod
    def invalidate_category_cache(cls, category_id: Optional[UUID] = None):
        """
        Инвалидирует все кеши, связанные с категориями.
        - Если указан category_id – удаляет конкретную категорию и все деревья/цепочки.
        - Если не указан – удаляет всё.
        """
        if category_id:
            cache.invalidate("category", str(category_id))
            # Удаляем деревья и хлебные крошки (паттерны)
            cache._delete_pattern(f"{cache.PREFIX}:category:tree:*")
            cache._delete_pattern(f"{cache.PREFIX}:category:breadcrumbs:*")
        else:
            cache.invalidate("category")