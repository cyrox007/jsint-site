from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from database import Database


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class VangaPrediction(Database.Base):
    """Публичный снимок прогноза Vanga без персональных данных посетителя."""

    __tablename__ = "vanga_predictions"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    site_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    imdb_id: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    model_generation: Mapped[str | None] = mapped_column(
        String(96),
        nullable=True,
        index=True,
    )
    rating: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    request_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    result_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        index=True,
    )
