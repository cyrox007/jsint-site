from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from models.categories import Category
from models.publication import Publication, PublicationSite
from models.site import Site
from utils.validation import validate_slug


@dataclass(frozen=True)
class PublicationChannelView:
    id: UUID
    owner_site_id: UUID
    title: str
    slug: str
    content: str
    source_type: str
    extra_data: dict[str, Any]
    category: Any
    technologies: list[Any]
    is_published: bool
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None


class PublicationChannelService:
    @staticmethod
    def _to_view(
        publication: Publication,
        placement: PublicationSite,
    ) -> PublicationChannelView:
        return PublicationChannelView(
            id=publication.id,
            owner_site_id=publication.site_id,
            title=publication.title,
            slug=placement.slug,
            content=publication.content,
            source_type=publication.source_type,
            extra_data=publication.extra_data or {},
            category=placement.category,
            technologies=list(publication.technologies or []),
            is_published=placement.is_published,
            created_at=publication.created_at,
            updated_at=publication.updated_at,
            published_at=placement.published_at,
        )

    @staticmethod
    def _base_query(session: Session, site_id: UUID):
        return (
            session.query(Publication, PublicationSite)
            .join(
                PublicationSite,
                PublicationSite.publication_id == Publication.id,
            )
            .options(
                selectinload(Publication.technologies),
                selectinload(PublicationSite.category),
            )
            .filter(PublicationSite.site_id == site_id)
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
    ) -> list[PublicationChannelView]:
        query = cls._base_query(session, site_id).filter(
            PublicationSite.is_published.is_(True)
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
    def list_for_admin(
        cls,
        session: Session,
        *,
        site_id: UUID,
        is_published: bool | None = None,
        category_ids: list[UUID] | None = None,
        search: str | None = None,
    ) -> list[PublicationChannelView]:
        query = cls._base_query(session, site_id)
        if is_published is not None:
            query = query.filter(PublicationSite.is_published == is_published)
        if category_ids:
            query = query.filter(PublicationSite.category_id.in_(category_ids))
        if search:
            term = f"%{search}%"
            query = query.filter(
                or_(
                    Publication.title.ilike(term),
                    Publication.content.ilike(term),
                    PublicationSite.slug.ilike(term),
                )
            )

        rows = query.order_by(
            Publication.updated_at.desc(),
            Publication.created_at.desc(),
        ).all()
        return [cls._to_view(publication, placement) for publication, placement in rows]

    @staticmethod
    def count_for_admin(session: Session, *, site_id: UUID) -> int:
        return (
            session.query(PublicationSite)
            .filter(PublicationSite.site_id == site_id)
            .count()
        )

    @staticmethod
    def category_counts(
        session: Session,
        *,
        site_id: UUID,
    ) -> list[tuple[UUID, int]]:
        return (
            session.query(
                PublicationSite.category_id,
                func.count(PublicationSite.publication_id),
            )
            .filter(
                PublicationSite.site_id == site_id,
                PublicationSite.category_id.is_not(None),
            )
            .group_by(PublicationSite.category_id)
            .all()
        )

    @classmethod
    def get_public_by_slug(
        cls,
        session: Session,
        *,
        site_id: UUID,
        slug: str,
        category_id: UUID | None = None,
    ) -> PublicationChannelView | None:
        query = cls._base_query(session, site_id).filter(
            PublicationSite.slug == slug,
            PublicationSite.is_published.is_(True),
        )
        if category_id is not None:
            query = query.filter(PublicationSite.category_id == category_id)

        row = query.first()
        if row is None:
            return None
        publication, placement = row
        return cls._to_view(publication, placement)

    @staticmethod
    def list_placements(
        session: Session,
        publication_id: UUID,
    ) -> list[PublicationSite]:
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
        publication = Publication.get_by_id(session, publication_id)
        if publication is None:
            raise ValueError("Публикация не найдена")
        if site_id == publication.site_id:
            raise ValueError("Основной канал изменяется через основные поля публикации")
        if session.query(Site).filter(Site.id == site_id).first() is None:
            raise ValueError("Сайт размещения не найден")

        normalized_slug = validate_slug(slug)
        if category_id is not None and Category.get_by_id(
            session,
            category_id,
            site_id,
        ) is None:
            raise ValueError("Рубрика не принадлежит выбранному сайту")
        if is_published and category_id is None:
            raise ValueError("Для опубликованного размещения выберите рубрику")

        duplicate = (
            session.query(PublicationSite)
            .filter(
                PublicationSite.site_id == site_id,
                PublicationSite.slug == normalized_slug,
                PublicationSite.publication_id != publication_id,
            )
            .first()
        )
        if duplicate is not None:
            raise ValueError("На этом сайте уже используется такой URL публикации")

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

        placement.slug = normalized_slug
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
        publication = Publication.get_by_id(session, publication_id)
        if publication is not None and site_id == publication.site_id:
            raise ValueError("Основной канал публикации нельзя удалить")

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
