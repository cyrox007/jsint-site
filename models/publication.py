from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, String, Text,
    UUID as PG_UUID, Table, Column
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Database

if TYPE_CHECKING:
    from models.technology import Technology
    from models.categories import Category
    from models.users import User


class Publication(Database.Base):
    __tablename__ = 'publications'

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Основные поля
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Тип и источник (полиморфная связь)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'article', 'task', 'case', 'changelog'
    source_uid: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)

    # Гибкие метаданные
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)

    # Категория (для статей/кейсов)
    category_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey('categories.id'), nullable=True)
    category = relationship("Category", lazy="selectin")

    # Автор
    author_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    author = relationship("User", lazy="selectin")

    # Статус публикации
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Технологии (многие-ко-многим)
    technologies: Mapped[List["Technology"]] = relationship(
        "Technology",
        secondary="publication_technologies",
        lazy="selectin"
    )

    # Отметки времени
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Publication {self.title} ({self.source_type})>"


# Связующая таблица Publication-Technology (определена здесь, чтобы ссылаться на классы)
publication_technologies = Table(
    'publication_technologies',
    Database.Base.metadata,
    Column('publication_id', PG_UUID(as_uuid=True), ForeignKey('publications.id', ondelete='CASCADE'), primary_key=True),
    Column('technology_id', PG_UUID(as_uuid=True), ForeignKey('technologies.id', ondelete='CASCADE'), primary_key=True),
)