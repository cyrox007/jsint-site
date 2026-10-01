from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID as UUIDType, uuid4

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from database import Database


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LicenseRecord(Database.Base):
    __tablename__ = "license_registry"

    id: Mapped[UUIDType] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    installation_id: Mapped[UUIDType] = mapped_column(PG_UUID(as_uuid=True), unique=True, nullable=False, index=True)
    license_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    signed_license: Mapped[str] = mapped_column(Text, nullable=False)
    key_id: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    updates_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    max_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    customer: Mapped[str | None] = mapped_column(String(160), nullable=True)
    edition: Mapped[str] = mapped_column(String(64), nullable=False)
    max_users: Mapped[int | None] = mapped_column(Integer, nullable=True)
    features: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    activation_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    credential_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    license_not_before: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    license_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_seen_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_seen_action: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_client_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_client_version_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_client_channel: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class ControlPlaneAuditRecord(Database.Base):
    __tablename__ = "control_plane_audit"

    id: Mapped[UUIDType] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    actor_kind: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    actor_user_id: Mapped[UUIDType | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    actor_label: Mapped[str | None] = mapped_column(String(320), nullable=True)
    action: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False, default="success", index=True)
    target_type: Mapped[str | None] = mapped_column(String(48), nullable=True, index=True)
    target_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    installation_id: Mapped[UUIDType | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)
    license_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    release_id: Mapped[UUIDType | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)


class ReleaseRecord(Database.Base):
    __tablename__ = "release_registry"
    __table_args__ = (
        UniqueConstraint("channel", "version_code", name="uq_release_channel_version_code"),
        UniqueConstraint("channel", "package_name", name="uq_release_channel_package_name"),
    )

    id: Mapped[UUIDType] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    channel: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    version_code: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    manifest_name: Mapped[str] = mapped_column(String(220), nullable=False)
    signature_name: Mapped[str] = mapped_column(String(220), nullable=False)
    manifest_bytes: Mapped[str] = mapped_column(Text, nullable=False)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    package_name: Mapped[str] = mapped_column(String(220), nullable=False)
    package_path: Mapped[str] = mapped_column(Text, nullable=False)
    package_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    package_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_commit: Mapped[str] = mapped_column(String(40), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
