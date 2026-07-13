from typing import TYPE_CHECKING, List
from uuid import (
    UUID as UUIDType,
    uuid4
)

from sqlalchemy import (
    UUID as PG_UUID,
    String
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Database

if TYPE_CHECKING:
    from models.articles import Article


class User(Database.Base):
    __tablename__ = 'users'

    id: Mapped[UUIDType] = mapped_column(
        PG_UUID(as_uuid=True),
        default=uuid4,
        primary_key=True,
    )

    email: Mapped[str] = mapped_column(
        unique=True, 
        nullable=False, 
        index=True
    )

    hash_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    firstname: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
        default="John"
    )

    lastname: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
        default="Doe"
    )

    articles: Mapped[List["Article"]] = relationship(
        "Article",
        back_populates="author",
        primaryjoin="User.id == Article.author_id",
        lazy="selectin"
    )