from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from models.publication import Publication, PublicationSite


@dataclass(frozen=True)
class PublicPublicationView:
    id: UUID
    title: str
    slug: str
    content: str
    source_type: str
    extra_data: dict[str, Any]
    category: Any
    technologies: list[Any]
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None


class PublicationChannelService:
    @staticmethod
    def _to_view(publication: Publication, placement: PublicationSite) -> PublicPublicationView:
        return PublicPublicationView(
            id=publication.id,
            title=publication.title,
            slug=placement.slug,
            content=publication.content,
            source_type=publication.source_type,
            extra_data=publication.extra_data or {},
            category=placement.category,
            technologies=list(publication.technologies or []),
            created_at=publication.created_at,
            updated_at=publication.updated_at,
            published_at=placement.published_at,
        )

    @staticmethod
    def sync_owner(session: Session, publication: Publication) -> PublicationSite:
        placement = (
            session.query(PublicationSite)
            .filter(
                PublicationSite.publication_id == publication.id,
                PublicationSite.site_id == publication.site_id,
            )
            .first()
        )
        if placement is None:
            placement = PublicationSite(
                publication_id=publication.id,
                site_id=publication.site_id,
            )

        placement.slug = publication.slug
        placement.category_id = publication.category_id
        placement.is_published = publication.is_published
        placement.published_at = publication.published_at
        session.add(placement)
        session.flush()
        return placement

    @classmethod
    def list_public(
        cls,
        session: Session,
        *,
        site_id: UUID,
        limit: int = 20,
        offset: int = 0,
        category_id: UUID | None = None,
        source_type: str | None = None,
    ) -> list[PublicPublicationView]:
        query = (
            session.query(Publication, PublicationSite)
            .join(
                PublicationSite,
                PublicationSite.publication_id == Publication.id,
            )
            .options(
                selectinload(Publication.technologies),
                selectinload(PublicationSite.category),
            )
            .filter(
                PublicationSite.site_id == site_id,
                PublicationSite.is_published.is_(True),
            )
        )
        if category_id is not None:
            query = query.filter(PublicationSite.category_id == category_id)
        if source_type:
            query = query.filter(Publication.source_type == source_type)

        rows = (
            query.order_by(
                PublicationSite.published_at.desc(),
                Publication.updated_at.desc(),
            )
            .offset(max(offset, 0))
            .limit(max(1, min(limit, 100)))
            .all()
        )
        return [cls._to_view(publication, placement) for publication, placement in rows]

    @staticmethod
    def count_public(
        session: Session,
        *,
        site_id: UUID,
        category_id: UUID | None = None,
        source_type: str | None = None,
    ) -> int:
        query = (
            session.query(PublicationSite)
            .join(Publication, Publication.id == PublicationSite.publication_id)
            .filter(
                PublicationSite.site_id == site_id,
                PublicationSite.is_published.is_(True),
            )
        )
        if category_id is not None:
            query = query.filter(PublicationSite.category_id == category_id)
        if source_type:
            query = query.filter(Publication.source_type == source_type)
        return query.count()

    @classmethod
    def get_public_by_slug(
        cls,
        session: Session,
        *,
        site_id: UUID,
        slug: str,
        category_id: UUID | None = None,
    ) -> PublicPublicationView | None:
        query = (
            session.query(Publication, PublicationSite)
            .join(
                PublicationSite,
                PublicationSite.publication_id == Publication.id,
            )
            .options(
                selectinload(Publication.technologies),
                selectinload(PublicationSite.category),
            )
            .filter(
                PublicationSite.site_id == site_id,
                PublicationSite.slug == slug,
                PublicationSite.is_published.is_(True),
            )
        )
        if category_id is not None:
            query = query.filter(PublicationSite.category_id == category_id)

        row = query.first()
        if row is None:
            return None
        publication, placement = row
        return cls._to_view(publication, placement)

    @staticmethod
    def list_placements(session: Session, publication_id: UUID) -> list[PublicationSite]:
        return (
            session.query(PublicationSite)
            .options(selectinload(PublicationSite.category))
            .filter(PublicationSite.publication_id == publication_id)
            .order_by(PublicationSite.created_at.asc())
            .all()
        )

    @staticmethod
    def set_placement(
        session: Session,
        *,
        publication_id: UUID,
        site_id: UUID,
        slug: str,
        category_id: UUID | None,
        is_published: bool,
    ) -> PublicationSite:
        placement = (
            session.query(PublicationSite)
            .filter(
                PublicationSite.publication_id == publication_id,
                PublicationSite.site_id == site_id,
            )
            .first()
        )
        if placement is None:
            placement = PublicationSite(
                publication_id=publication_id,
                site_id=site_id,
            )

        placement.slug = slug
        placement.category_id = category_id
        if is_published and not placement.published_at:
            placement.published_at = datetime.now(timezone.utc)
        elif not is_published:
            placement.published_at = None
        placement.is_published = is_published
        session.add(placement)
        session.flush()
        return placement

    @staticmethod
    def remove_placement(
        session: Session,
        *,
        publication_id: UUID,
        site_id: UUID,
    ) -> None:
        placement = (
            session.query(PublicationSite)
            .filter(
                PublicationSite.publication_id == publication_id,
                PublicationSite.site_id == site_id,
            )
            .first()
        )
        if placement is not None:
            session.delete(placement)
            session.flush()
