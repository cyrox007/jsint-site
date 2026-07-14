from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from uuid import (
    UUID as UUIDType,
    uuid4
)

from sqlalchemy import (
    UUID as PG_UUID,
    String, 
    DateTime, 
    Text, 
    ForeignKey,
    asc,
    desc
)

from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from database import Database

if TYPE_CHECKING:
    from models.users import User
    from models.categories import Category


class Article(Database.Base):
    __tablename__ = 'articles'

    id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True), 
        primary_key=True,
        default=uuid4
    )
    
    author_id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True), 
        ForeignKey('users.id')
    )
    
    category_id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True), 
        ForeignKey('categories.id')
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
    
    title: Mapped[str] = mapped_column(
        String(50), 
        nullable=False
    )

    slug: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True
    )

    content: Mapped[str] = mapped_column(
        Text, 
        nullable=False
    )

    status: Mapped[str] = mapped_column(String(50), default="published")

    author: Mapped["User"] = relationship(
        "User",  # или lambda: User
        back_populates="articles",
        lazy="selectin"
    )
    
    category: Mapped["Category"] = relationship(
        "Category",
        back_populates="articles",
        lazy="selectin"
    )

    def __repr__(self):
        return f"<Article {self.id}>"

    @classmethod
    def get_posts(
        cls,
        session: Session,
        *,  # Все параметры после * должны передаваться по имени
        # Фильтрация
        author_id: Optional[UUIDType] = None,
        category_id: Optional[UUIDType] = None,
        title_contains: Optional[str] = None,
        status: Optional[str] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        # Дополнительные фильтры (для сложных случаев)
        filters: Optional[list] = None,
        # Сортировка
        order_by: Optional[str] = "created_at",  # "created_at", "title", "updated_at"
        order_direction: str = "desc",  # "asc" или "desc"
        # Пагинация
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> list["Article"]:
        query = session.query(cls)
    
        # Применяем базовые фильтры
        if author_id is not None:
            query = query.filter(cls.author_id == author_id)
        
        if category_id is not None:
            query = query.filter(cls.category_id == category_id)
        
        if title_contains is not None:
            query = query.filter(cls.title.ilike(f"%{title_contains}%"))
        
        if status is not None:
            query = query.filter(cls.status == status)
        
        if created_after is not None:
            query = query.filter(cls.created_at >= created_after)
        
        if created_before is not None:
            query = query.filter(cls.created_at <= created_before)
        
        # Применяем дополнительные фильтры
        if filters:
            for filter_expr in filters:
                query = query.filter(filter_expr)
        
        # Применяем сортировку
        if order_by:
            if hasattr(cls, order_by):
                order_column = getattr(cls, order_by)
                if order_direction.lower() == "asc":
                    query = query.order_by(asc(order_column))
                else:
                    query = query.order_by(desc(order_column))
            else:
                # Если поле не существует, используем created_at по умолчанию
                query = query.order_by(desc(cls.created_at))
        
        # Применяем пагинацию
        if offset is not None:
            query = query.offset(offset)
        
        if limit is not None:
            query = query.limit(limit)
        
        return query.all()
    
    @classmethod
    def get_post_by_id(cls, session: Session, article_id: UUIDType) -> Optional["Article"]:
        return session.query(cls).filter(cls.id == article_id).first()
    
    @classmethod
    def get_post_by_slug(cls, session: Session, slug: str) -> Optional["Article"]:
        return session.query(cls).filter(cls.slug == slug).first()

    @classmethod
    def insert_new_post(
        cls,
        session: Session,
        author_id: UUIDType,
        category_id: UUIDType,
        title: str,
        slug: str,
        content: str = ''
    ) -> Optional["Article"]:
        post = cls(
            author_id=author_id,
            category_id=category_id,  
            title=title,
            slug=slug,                
            content=content
        )

        session.add(post)
        try:
            session.commit()
            session.refresh(post)
            return post
        except Exception as ex:
            print(f"Ошибка при создании статьи: {ex}")
            session.rollback()
            return None

    @classmethod
    def update_post(
        cls,
        session: Session,
        article: "Article",
        title: Optional[str] = None,
        content: Optional[str] = None
    ) -> Optional["Article"]:
        if title is not None:
            article.title = title
        if content is not None:
            article.content = content

        session.add(article)
        try:
            session.commit()
            session.refresh(article)
            return article
        except Exception as ex:
            print(f"Ошибка при обновлении статьи: {ex}")
            session.rollback()
            return None

    @classmethod
    def delete_post(cls, session: Session, article: "Article") -> bool:
        session.delete(article)
        try:
            session.commit()
            return True
        except Exception as ex:
            print(f"Ошибка при удалении статьи: {ex}")
            session.rollback()
            return False
