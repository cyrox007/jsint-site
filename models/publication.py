from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, String, Text,
    UUID as PG_UUID, Table, Column, or_
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship, selectinload

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

    @classmethod
    def get_by_id(cls, session: Session, pub_id: UUID) -> Optional["Publication"]:
        return session.query(cls).options(
            selectinload(cls.technologies),
            selectinload(cls.category),
            selectinload(cls.author)
        ).filter(cls.id == pub_id).first()
    
    @classmethod
    def get_all(cls, session: Session, **filters) -> List["Publication"]:
        query = session.query(cls).options(
            selectinload(cls.technologies),
            selectinload(cls.category),
            selectinload(cls.author)
        )

        for key, value in filters.items():
            if value is None:
                continue

            if key == 'is_published':
                query = query.filter(cls.is_published == value)
            elif key == 'category_id':
                query = query.filter(cls.category_id == value)
            elif key == 'source_type':
                query = query.filter(cls.source_type == value)
            elif key == 'author_id':
                query = query.filter(cls.author_id == value)
            elif key == 'tech_slugs' and value:
                query = query.join(cls.technologies).filter(Technology.slug.in_(value))
            elif key == 'tech_ids' and value:
                query = query.join(cls.technologies).filter(Technology.id.in_(value))
            elif key == 'search' and value:
                # Поиск по заголовку и содержанию
                search_term = f"%{value}%"
                query = query.filter(
                    or_(
                        cls.title.ilike(search_term),
                        cls.content.ilike(search_term)
                    )
                )

        # Сортировка
        order_field = filters.get('order_by', 'created_at')
        order_direction = filters.get('order_direction', 'desc')
        if hasattr(cls, order_field):
            order_column = getattr(cls, order_field)
            if order_direction.lower() == 'asc':
                query = query.order_by(order_column.asc())
            else:
                query = query.order_by(order_column.desc())
        else:
            query = query.order_by(cls.created_at.desc())

        # Пагинация
        if 'limit' in filters and filters['limit']:
            query = query.limit(filters['limit'])
        if 'offset' in filters and filters['offset']:
            query = query.offset(filters['offset'])

        return query.all()
    
    @classmethod
    def get_published(cls, session: Session, limit: int = 10) -> List["Publication"]:
        """Получить последние опубликованные публикации."""
        return cls.get_all(
            session,
            is_published=True,
            order_by='published_at',
            order_direction='desc',
            limit=limit
        )

    @classmethod
    def get_by_slug(cls, session: Session, slug: str) -> Optional["Publication"]:
        """Получить публикацию по slug."""
        return session.query(cls).filter(cls.slug == slug).first()

    @classmethod
    def create(cls, session: Session, **kwargs) -> "Publication":
        """Создать новую публикацию."""
        pub = cls(**kwargs)
        session.add(pub)
        session.flush()  # Получаем ID
        return pub
    
    @classmethod
    def update(cls, session: Session, pub_id: UUID, **kwargs) -> Optional["Publication"]:
        """Обновить публикацию."""
        pub = cls.get_by_id(session, pub_id)
        if not pub:
            return None

        for key, value in kwargs.items():
            if key == 'technologies' and value is not None:
                pub.technologies = value
            elif hasattr(pub, key) and key not in ['id', 'created_at', 'updated_at']:
                setattr(pub, key, value)

        if 'is_published' in kwargs and kwargs['is_published'] and not pub.published_at:
            pub.published_at = datetime.now(timezone.utc)

        session.add(pub)
        return pub

    @classmethod
    def delete(cls, session: Session, pub_id: UUID) -> bool:
        """Удалить публикацию."""
        pub = cls.get_by_id(session, pub_id)
        if not pub:
            return False
        session.delete(pub)
        return True

# Связующая таблица Publication-Technology (определена здесь, чтобы ссылаться на классы)
publication_technologies = Table(
    'publication_technologies',
    Database.Base.metadata,
    Column('publication_id', PG_UUID(as_uuid=True), ForeignKey('publications.id', ondelete='CASCADE'), primary_key=True),
    Column('technology_id', PG_UUID(as_uuid=True), ForeignKey('technologies.id', ondelete='CASCADE'), primary_key=True),
)