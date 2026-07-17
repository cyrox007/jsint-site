# models/technology.py
from uuid import UUID, uuid4
from sqlalchemy import String, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from database import Database

class Technology(Database.Base):
    __tablename__ = 'technologies'
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)