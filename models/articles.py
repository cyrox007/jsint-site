from typing import TYPE_CHECKING, Optional, Self

from uuid import (
    UUID as UUIDType,
    uuid4
)

from sqlalchemy import (
    UUID as PG_UUID,
    Column, 
    Integer, 
    String, 
    DateTime, 
    Text, 
    ForeignKey
)

from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from database import Database
from datetime import datetime, timezone
from models.users import User

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
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc), 
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc), 
    )
    
    title: Mapped[str] = mapped_column(
        String(50), 
        nullable=False
    )

    content: Mapped[str] = mapped_column(
        Text, 
        nullable=False
    )

    author: Mapped["User"] = relationship(
        "User",  # или lambda: User
        back_populates="articles",
        lazy="selectin"
    )

    @classmethod
    def get_posts(cls, session: Session):
        return session.query(cls).order_by(cls.created_at.asc()).all()
    
    @classmethod
    def get_post(cls, session: Session, id: UUIDType):
        return session.query(cls).filter(
            cls.id == id
        ).first()

    @classmethod
    def insert_new_post(cls, session: Session, author_id: UUIDType, title: str, content: str = ''):
        post = cls(
            author_id=author_id,
            created_at=lambda: datetime.now(timezone.utc),
            title=title,
            content=content 
        )

        session.add(post)
        try:
            session.commit()
            return post
        except Exception as ex:
            print(ex)
            session.rollback()
            return None

    @classmethod
    def update_post(session: Session, article, title: str, text: str = ''):
        
        article.title = title
        article.body = text
        article.updated_at = datetime.now(timezone.utc)
        session.add(article)
        try:
            session.commit()
            return article
        except Exception as ex:
            print(ex)
            session.rollback()
            return None

    @classmethod
    def delete_post(cls, session: Session, article):
        session.delete(article)
        try:
            session.commit()
            return True
        except Exception as ex:
            print(ex)
            session.rollback()
            return False
