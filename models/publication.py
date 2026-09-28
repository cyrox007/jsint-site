from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    Table,
    Text,
    UniqueConstraint,
    UUID as PG_UUID,
    or_,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship, selectinload

from database import Database
from models.technology import Technology

if TYPE_CHECKING:
    from models.categories import Category
    from models.users import User


class Publication(Database.Base):
    __tablename__ = "publications"
    __table_args__ = (
        UniqueConstraint("site_id", "slug", name="uq_publications_site_slug"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    site_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_uid: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)

    category_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("categories.id"),
        nullable=True,
    )
    category = relationship("Category", back_populates="articles", lazy="selectin")

    author_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    author = relationship("User", back_populates="articles", lazy="selectin")

    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    technologies: Mapped[List["Technology"]] = relationship(
        "Technology",
        secondary="publication_technologies",
        lazy="selectin",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self):
        return f"<Publication {self.title} ({self.source_type})>"

    @classmethod
    def get_by_id(cls, session: Session, pub_id: UUID) -> Optional["Publication"]:
        return (
            session.query(cls)
            .options(
                selectinload(cls.technologies),
                selectinload(cls.category),
                selectinload(cls.author),
            )
            .filter(cls.id == pub_id)
            .first()
        )

    @classmethod
    def get_all(cls, session: Session, **filters) -> List["Publication"]:
        query = session.query(cls).options(
            selectinload(cls.technologies),
            selectinload(cls.category),
            selectinload(cls.author),
        )

        for key, value in filters.items():
            if value is None:
                continue

            if key == "site_id":
                query = query.filter(cls.site_id == value)
            elif key == "is_published":
                query = query.filter(cls.is_published == value)
            elif key == "category_id":
                query = query.filter(cls.category_id == value)
            elif key == "category_ids" and value:
                query = query.filter(cls.category_id.in_(value))
            elif key == "source_type":
                query = query.filter(cls.source_type == value)
            elif key == "author_id":
                query = query.filter(cls.author_id == value)
            elif key == "tech_slugs" and value:
                query = query.join(cls.technologies).filter(Technology.slug.in_(value))
            elif key == "tech_ids" and value:
                query = query.join(cls.technologies).filter(Technology.id.in_(value))
            elif key == "search" and value:
                search_term = f"%{value}%"
                query = query.filter(
                    or_(
                        cls.title.ilike(search_term),
                        cls.content.ilike(search_term),
                    )
                )

        order_field = filters.get("order_by", "created_at")
        order_direction = filters.get("order_direction", "desc")
        if hasattr(cls, order_field):
            order_column = getattr(cls, order_field)
            query = query.order_by(
                order_column.asc() if order_direction.lower() == "asc" else order_column.desc()
            )
        else:
            query = query.order_by(cls.created_at.desc())

        if filters.get("limit"):
            query = query.limit(filters["limit"])
        if filters.get("offset"):
            query = query.offset(filters["offset"])
        return query.all()

    @classmethod
    def get_published(
        cls,
        session: Session,
        *,
        site_id: UUID,
        limit: int = 10,
    ) -> List["Publication"]:
        return cls.get_all(
            session,
            site_id=site_id,
            is_published=True,
            order_by="published_at",
            order_direction="desc",
            limit=limit,
        )

    @classmethod
    def get_by_slug(
        cls,
        session: Session,
        slug: str,
        site_id: UUID | None = None,
    ) -> Optional["Publication"]:
        query = session.query(cls).filter(cls.slug == slug)
        if site_id is not None:
            query = query.filter(cls.site_id == site_id)
        return query.first()

    @classmethod
    def create(cls, session: Session, **kwargs) -> "Publication":
        publication = cls(**kwargs)
        session.add(publication)
        session.flush()
        return publication

    @classmethod
    def update(cls, session: Session, pub_id: UUID, **kwargs) -> Optional["Publication"]:
        publication = cls.get_by_id(session, pub_id)
        if not publication:
            return None

        for key, value in kwargs.items():
            if key == "technologies" and value is not None:
                publication.technologies = value
            elif hasattr(publication, key) and key not in {"id", "created_at", "updated_at"}:
                setattr(publication, key, value)

        if "is_published" in kwargs:
            if kwargs["is_published"] and not publication.published_at:
                publication.published_at = datetime.now(timezone.utc)
            elif not kwargs["is_published"]:
                publication.published_at = None

        session.add(publication)
        return publication

    @classmethod
    def delete(cls, session: Session, pub_id: UUID) -> bool:
        publication = cls.get_by_id(session, pub_id)
        if not publication:
            return False
        session.delete(publication)
        return True


publication_technologies = Table(
    "publication_technologies",
    Database.Base.metadata,
    Column(
        "publication_id",
        PG_UUID(as_uuid=True),
        ForeignKey("publications.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "technology_id",
        PG_UUID(as_uuid=True),
        ForeignKey("technologies.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
