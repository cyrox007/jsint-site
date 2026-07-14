import hashlib
from typing import Optional
from uuid import UUID as UUIDType

from sqlalchemy.orm import Session

from cache.manager import cache
from models.articles import Article as ArticleModel
from schemas.articles import ArticleDetail, ArticleInList


class ArticleService:
    TTL_DETAIL = 300
    TTL_LIST = 120

    @staticmethod
    def _hash_params(**kwargs) -> str:
        items = sorted((k, str(v)) for k, v in kwargs.items() if v is not None)
        raw = "&".join(f"{k}={v}" for k, v in items)
        return hashlib.md5(raw.encode()).hexdigest()

    @classmethod
    def get_article(cls, session: Session, article_id: UUIDType) -> Optional[ArticleDetail]:
        # 1. Кеш
        cached = cache.get("articles", str(article_id), ArticleDetail)
        if cached is not None:
            return cached

        # 2. БД
        article = ArticleModel.get_post(session, article_id)
        if article is None:
            return None

        # 3. ORM → Pydantic
        schema = ArticleDetail.model_validate(article)

        # 4. В кеш
        cache.set("articles", str(article_id), schema, ttl=cls.TTL_DETAIL)
        return schema

    @classmethod
    def get_articles(cls, session: Session, **filters) -> list[ArticleInList]:
        params_hash = cls._hash_params(**filters)

        # 1. Кеш
        cached = cache.get_list("articles", params_hash, ArticleInList)
        if cached is not None:
            return cached

        # 2. БД
        articles = ArticleModel.get_posts(session, **filters)

        # 3. ORM → Pydantic
        schemas = [ArticleInList.model_validate(a) for a in articles]

        # 4. В кеш
        cache.set_list("articles", params_hash, schemas, ttl=cls.TTL_LIST)
        return schemas

    @classmethod
    def get_latest_posts(cls, session: Session, limit: int = 5) -> list[ArticleInList]:
        """
        Получить N последних опубликованных статей.
        Используется на главной странице.
        """
        return cls.get_articles(
            session,
            status="published",
            order_by="created_at",
            order_direction="desc",
            limit=limit,
        )

    # ==================== ЗАПИСЬ ====================

    @classmethod
    def create_article(cls, session: Session, data: dict) -> Optional[ArticleDetail]:
        article = ArticleModel.insert_new_post(session, **data)
        if article is None:
            return None
        cache.invalidate("articles")
        return ArticleDetail.model_validate(article)

    @classmethod
    def update_article(cls, session: Session, article_id: UUIDType, data: dict) -> Optional[ArticleDetail]:
        article = ArticleModel.get_post(session, article_id)
        if article is None:
            return None
        updated = ArticleModel.update_post(session, article, **data)
        if updated is None:
            return None
        cache.invalidate("articles", str(article_id))
        return ArticleDetail.model_validate(updated)

    @classmethod
    def delete_article(cls, session: Session, article_id: UUIDType) -> bool:
        article = ArticleModel.get_post(session, article_id)
        if article is None:
            return False
        success = ArticleModel.delete_post(session, article)
        if success:
            cache.invalidate("articles", str(article_id))
        return success