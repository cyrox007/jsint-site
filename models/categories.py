from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID as UUIDType, uuid4

from sqlalchemy import (
    UUID as PG_UUID,
    DateTime,
    String,
    Text,
    asc,
    desc,
)
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from database import Database

if TYPE_CHECKING:
    from models.publication import Publication


class Category(Database.Base):
    __tablename__ = 'categories'

    id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
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

    title: Mapped[str] = mapped_column(String(50), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    articles: Mapped[List["Publication"]] = relationship(
        "Publication",
        back_populates="category",
        lazy="selectin"
    )

    def __repr__(self):
        return f"<Category {self.title} ({self.id})>"

    @classmethod
    def get_categories(
        cls,
        session: Session,
        *,
        # Фильтрация
        title_contains: Optional[str] = None,
        slug: Optional[str] = None,
        has_articles: Optional[bool] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        filters: Optional[list] = None,
        # Сортировка
        order_by: Optional[str] = "created_at",
        order_direction: str = "desc",
        # Пагинация
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List["Category"]:
        query = session.query(cls)

        if title_contains is not None:
            query = query.filter(cls.title.ilike(f"%{title_contains}%"))

        if slug is not None:
            query = query.filter(cls.slug == slug)

        if has_articles is True:
            query = query.filter(cls.articles.any())
        elif has_articles is False:
            query = query.filter(~cls.articles.any())

        if created_after is not None:
            query = query.filter(cls.created_at >= created_after)

        if created_before is not None:
            query = query.filter(cls.created_at <= created_before)

        if filters:
            for f in filters:
                query = query.filter(f)

        # Сортировка
        if order_by and hasattr(cls, order_by):
            col = getattr(cls, order_by)
            query = query.order_by(asc(col) if order_direction == "asc" else desc(col))
        else:
            query = query.order_by(desc(cls.created_at))

        # Пагинация
        if offset is not None:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)

        return query.all()

    @classmethod
    def get_category_by_id(cls, session: Session, category_id: UUIDType) -> Optional["Category"]:
        return session.query(cls).filter(cls.id == category_id).first()

    @classmethod
    def get_category_by_slug(cls, session: Session, slug: str) -> Optional["Category"]:
        return session.query(cls).filter(cls.slug == slug).first()
    

    @classmethod
    def update(
        cls,
        session: Session,
        category: "Category",
        title: Optional[str] = None,
        slug: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Optional["Category"]:
        if title is not None:
            category.title = title
        if slug is not None:
            category.slug = slug
        if description is not None:
            category.description = description

        # updated_at обновится автоматически (onupdate)
        session.add(category)
        try:
            session.commit()
            session.refresh(category)
            return category
        except Exception as ex:
            print(f"Ошибка при обновлении категории: {ex}")
            session.rollback()
            return None
        
    @classmethod
    def delete(cls, session: Session, category: "Category") -> bool:
        session.delete(category)
        try:
            session.commit()
            return True
        except Exception as ex:
            print(f"Ошибка при удалении категории: {ex}")
            session.rollback()
            return False