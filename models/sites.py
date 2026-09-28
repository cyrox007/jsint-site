from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from database import Database


class Site(Database.Base):
    __tablename__ = "sites"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    brand_subtitle: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    base_url: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    github_url: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    seo_title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    seo_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    hero_badge: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    hero_title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    hero_accent: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    hero_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    philosophy_title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    philosophy_subtitle: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    philosophy_body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    about_title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    about_primary_title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    about_primary_body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    about_secondary_title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    about_secondary_body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    footer_note: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
