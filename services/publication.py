from datetime import datetime, timezone
import hashlib
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from cache.manager import cache
from models.publication import Publication
from models.technology import Technology
from schemas.publication import PublicationCreate, PublicationOut, PublicationUpdate
from services.publication_channel import PublicationChannelService


class PublicationService:
    TTL_DETAIL = 300
    TTL_LIST = 120

    @staticmethod
    def _hash_params(**kwargs) -> str:
        items = sorted((key, str(value)) for key, value in kwargs.items() if value is not None)
        raw = "&".join(f"{key}={value}" for key, value in items)
        return hashlib.md5(raw.encode()).hexdigest()

    @classmethod
    def get_publication(cls, session: Session, pub_id: UUID) -> Optional[PublicationOut]:
        pub = Publication.get_by_id(session, pub_id)
        if not pub:
            return None

        cache_key = f"{pub.site_id}:{pub_id}"
        cached = cache.get("publications", cache_key, PublicationOut)
        if cached:
            return cached

        schema = PublicationOut.model_validate(pub)
        cache.set("publications", cache_key, schema, ttl=cls.TTL_DETAIL)
        return schema

    @classmethod
    def get_publications(cls, session: Session, **filters) -> List[PublicationOut]:
        filter_copy = {key: value for key, value in filters.items() if value is not None}
        params_hash = cls._hash_params(**filter_copy)

        cached = cache.get_list("publications", params_hash, PublicationOut)
        if cached is not None:
            return cached

        schemas = [PublicationOut.model_validate(item) for item in Publication.get_all(session, **filters)]
        if schemas:
            cache.set_list("publications", params_hash, schemas, ttl=cls.TTL_LIST)
        return schemas

    @classmethod
    def create_publication(
        cls,
        session: Session,
        data: PublicationCreate,
    ) -> Optional[PublicationOut]:
        if Publication.get_by_slug(session, data.slug, data.site_id):
            return None

        publication = Publication.create(
            session,
            site_id=data.site_id,
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

        if data.technology_ids:
            publication.technologies = (
                session.query(Technology)
                .filter(Technology.id.in_(data.technology_ids))
                .all()
            )

        PublicationChannelService.sync_owner(session, publication)
        session.commit()
        session.refresh(publication)
        cache.invalidate("publications")
        return PublicationOut.model_validate(publication)

    @classmethod
    def update_publication(
        cls,
        session: Session,
        pub_id: UUID,
        data: PublicationUpdate,
        *,
        commit: bool = True,
    ) -> Optional[PublicationOut]:
        publication = Publication.get_by_id(session, pub_id)
        if publication is None:
            return None

        existing = Publication.get_by_slug(session, data.slug, data.site_id)
        if existing is not None and existing.id != pub_id:
            return None

        update_data = data.model_dump(exclude_unset=True)
        technology_ids = update_data.pop("technology_ids", None)
        if technology_ids is not None:
            update_data["technologies"] = (
                session.query(Technology)
                .filter(Technology.id.in_(technology_ids))
                .all()
            )

        publication = Publication.update(session, pub_id, **update_data)
        if not publication:
            return None

        PublicationChannelService.sync_owner(session, publication)
        session.flush()
        if commit:
            session.commit()
        session.refresh(publication)
        cache.invalidate("publications")
        return PublicationOut.model_validate(publication)

    @classmethod
    def delete_publication(cls, session: Session, pub_id: UUID) -> bool:
        publication = Publication.get_by_id(session, pub_id)
        if publication is None:
            return False

        success = Publication.delete(session, pub_id)
        if success:
            session.commit()
            cache.invalidate("publications")
        return success
