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

        pub = session.query(Publication).filter(
            Publication.id == pub_id
        ).first()
        if not pub:
            return None

        schema = PublicationOut.model_validate(pub)
        cache.set("publications", str(pub_id), schema, ttl=cls.TTL_DETAIL)
        return schema

    @classmethod
    def get_publications(cls, session: Session, **filters) -> List[PublicationOut]:
        # По умолчанию только опубликованные
        if 'is_published' in filters:
            if filters['is_published'] is None:
                pass  # не фильтруем
            else:
                query = query.filter(Publication.is_published == filters['is_published'])
            del filters['is_published']

        params_hash = cls._hash_params(**filters)
        cached = cache.get_list("publications", params_hash, PublicationOut)
        if cached is not None:
            return cached

        query = session.query(Publication)
        for key, value in filters.items():
            if hasattr(Publication, key):
                query = query.filter(getattr(Publication, key) == value)
            elif key == 'tech_slugs' and value:
                query = query.join(Publication.technologies).filter(Technology.slug.in_(value))

        query = query.order_by(Publication.published_at.desc())
        if 'limit' in filters:
            query = query.limit(filters['limit'])
        if 'offset' in filters:
            query = query.offset(filters['offset'])

        pubs = query.all()
        schemas = [PublicationOut.model_validate(p) for p in pubs]
        cache.set_list("publications", params_hash, schemas, ttl=cls.TTL_LIST)
        return schemas

    @classmethod
    def create_publication(cls, session: Session, data: PublicationCreate) -> Optional[PublicationOut]:
        # Валидация источника (если указан)
        if data.source_uid:
            # Проверяем существование источника (зависит от source_type)
            # Можно сделать через словарь хендлеров
            pass

        pub = Publication(
            title=data.title,
            slug=data.slug,
            content=data.content,
            source_type=data.source_type,
            source_uid=data.source_uid,
            metadata=data.extra_data or {},
            category_id=data.category_id,
            author_id=data.author_id,
            is_published=data.is_published,
            published_at=datetime.now(timezone.utc) if data.is_published else None,
        )
        session.add(pub)
        session.commit()
        session.refresh(pub)

        # Привязка технологий
        if data.technology_ids:
            techs = session.query(Technology).filter(Technology.id.in_(data.technology_ids)).all()
            pub.technologies = techs
            session.commit()

        # Инвалидация кеша списков
        cache.invalidate("publications")
        return PublicationOut.model_validate(pub)

    @classmethod
    def update_publication(cls, session: Session, pub_id: UUID, data: PublicationUpdate) -> Optional[PublicationOut]:
        pub = session.query(Publication).filter(Publication.id == pub_id).first()
        if not pub:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if key == 'technology_ids':
                if value is not None:
                    techs = session.query(Technology).filter(Technology.id.in_(value)).all()
                    pub.technologies = techs
                continue
            setattr(pub, key, value)

        if data.is_published and not pub.published_at:
            pub.published_at = datetime.now(timezone.utc)

        session.commit()
        session.refresh(pub)

        # Инвалидация кеша
        cache.invalidate("publications", str(pub_id))
        return PublicationOut.model_validate(pub)

    @classmethod
    def delete_publication(cls, session: Session, pub_id: UUID) -> bool:
        pub = session.query(Publication).filter(Publication.id == pub_id).first()
        if not pub:
            return False
        session.delete(pub)
        session.commit()
        cache.invalidate("publications", str(pub_id))
        return True