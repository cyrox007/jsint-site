from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from database import Database


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AdminNotification(Database.Base):
    __tablename__ = "admin_notifications"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    site_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="info", index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="new", index=True)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    push_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    push_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    push_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DiagnosticReport(Database.Base):
    __tablename__ = "diagnostic_reports"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    installation_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    license_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    customer: Mapped[str | None] = mapped_column(String(160), nullable=True)
    client_version: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    client_version_code: Mapped[int | None] = mapped_column(nullable=True)
    reason: Mapped[str] = mapped_column(String(64), nullable=False, default="manual")
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    package_name: Mapped[str | None] = mapped_column(String(220), nullable=True)
    package_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    package_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    package_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
