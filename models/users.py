from uuid import (
    UUID as UUIDType,
    uuid4
)

from sqlalchemy import (
    UUID as PG_UUID,
    String
)
from sqlalchemy.orm import Mapped, mapped_column

from database import Database


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