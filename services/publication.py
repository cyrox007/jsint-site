# services/publication.py
from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from models.publication import Publication
from models.technology import Technology
from schemas.publication import (
    PublicationCreate, 
    PublicationUpdate, 
    PublicationOut
)
from cache.manager import cache
import hashlib

class PublicationService:
    TTL_DETAIL = 300
    TTL_LIST = 120

    @staticmethod
    def _hash_params(**kwargs) -> str:
        items = sorted((k, str(v)) for k, v in kwargs.items() if v is not None)
        raw = "&".join(f"{k}={v}" for k, v in items)
        return hashlib.md5(raw.encode()).hexdigest()

    @classmethod
    def get_publication(cls, session: Session, pub_id: UUID) -> Optional[PublicationOut]:
        # Кеш по id
        cached = cache.get("publications", str(pub_id), PublicationOut)
        if cached:
            return cached

        pub = Publication.get_by_id(session, pub_id)
        if not pub:
            return None

        schema = PublicationOut.model_validate(pub)
        cache.set("publications", str(pub_id), schema, ttl=cls.TTL_DETAIL)
        return schema

    @classmethod
    def get_publications(cls, session: Session, **filters) -> List[PublicationOut]:
        # Подготавливаем параметры для хеша
        filter_copy = {k: v for k, v in filters.items() if v is not None}
        params_hash = cls._hash_params(**filter_copy)

        # Проверяем кеш
        cached = cache.get_list("publications", params_hash, PublicationOut)
        if cached is not None:
            return cached

        # Запрос к БД через модель
        pubs = Publication.get_all(session, **filters)

        # Преобразуем в Pydantic
        schemas = [PublicationOut.model_validate(p) for p in pubs]

        # Сохраняем в кеш (только если есть данные, чтобы не кешировать пустоту)
        if schemas:
            cache.set_list("publications", params_hash, schemas, ttl=cls.TTL_LIST)
        return schemas

    @classmethod
    def create_publication(cls, session: Session, data: PublicationCreate) -> Optional[PublicationOut]:
        # Проверяем уникальность slug
        existing = Publication.get_by_slug(session, data.slug)
        if existing:
            return None

        # Создаём через модель
        pub = Publication.create(
            session,
            title=data.title,
            slug=data.slug,
            content=data.content,
            source_type=data.source_type,
            source_uid=data.source_uid,
            extra_data=data.extra_data or {},
            category_id=data.category_id,
            author_id=data.author_id,
            is_published=data.is_published,
            published_at=datetime.now(timezone.utc) if data.is_published else None,
        )

        # Привязываем технологии
        if data.technology_ids:
            techs = session.query(Technology).filter(Technology.id.in_(data.technology_ids)).all()
            pub.technologies = techs

        session.commit()
        session.refresh(pub)

        # Инвалидируем кеш списков
        cache.invalidate("publications")

        return PublicationOut.model_validate(pub)

    @classmethod
    def update_publication(cls, session: Session, pub_id: UUID, data: PublicationUpdate) -> Optional[PublicationOut]:
        update_data = data.model_dump(exclude_unset=True)

        # Обрабатываем технологии отдельно
        technology_ids = update_data.pop('technology_ids', None)
        if technology_ids is not None:
            techs = session.query(Technology).filter(Technology.id.in_(technology_ids)).all()
            update_data['technologies'] = techs

        # Обновляем через модель
        pub = Publication.update(session, pub_id, **update_data)
        if not pub:
            return None

        session.commit()
        session.refresh(pub)

        # Инвалидируем кеш
        cache.invalidate("publications", str(pub_id))

        return PublicationOut.model_validate(pub)

    @classmethod
    def delete_publication(cls, session: Session, pub_id: UUID) -> bool:
        success = Publication.delete(session, pub_id)
        if success:
            session.commit()
            cache.invalidate("publications", str(pub_id))
        return success