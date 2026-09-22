"""Единый реестр лицензий и релизов Workspace Organizer.

Revision ID: 7f40a9d2c3b1
Revises: 0d129106af49
Create Date: 2026-09-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "7f40a9d2c3b1"
down_revision = "0d129106af49"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "license_registry",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("installation_id", sa.UUID(), nullable=False),
        sa.Column("license_id", sa.String(length=128), nullable=False),
        sa.Column("signed_license", sa.Text(), nullable=False),
        sa.Column("key_id", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("updates_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_version", sa.Integer(), nullable=True),
        sa.Column("customer", sa.String(length=160), nullable=True),
        sa.Column("edition", sa.String(length=64), nullable=False),
        sa.Column("max_users", sa.Integer(), nullable=True),
        sa.Column("features", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("activation_hash", sa.String(length=64), nullable=True),
        sa.Column("credential_hash", sa.String(length=64), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("installation_id"),
        sa.UniqueConstraint("license_id"),
    )
    op.create_index("ix_license_registry_installation_id", "license_registry", ["installation_id"])
    op.create_index("ix_license_registry_license_id", "license_registry", ["license_id"])
    op.create_index("ix_license_registry_status", "license_registry", ["status"])

    op.create_table(
        "release_registry",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("version_code", sa.Integer(), nullable=False),
        sa.Column("manifest_name", sa.String(length=220), nullable=False),
        sa.Column("signature_name", sa.String(length=220), nullable=False),
        sa.Column("manifest_bytes", sa.Text(), nullable=False),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("package_name", sa.String(length=220), nullable=False),
        sa.Column("package_path", sa.Text(), nullable=False),
        sa.Column("package_size", sa.BigInteger(), nullable=False),
        sa.Column("package_sha256", sa.String(length=64), nullable=False),
        sa.Column("source_commit", sa.String(length=40), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel", "package_name", name="uq_release_channel_package_name"),
        sa.UniqueConstraint("channel", "version_code", name="uq_release_channel_version_code"),
    )
    op.create_index("ix_release_registry_channel", "release_registry", ["channel"])
    op.create_index("ix_release_registry_version_code", "release_registry", ["version_code"])
    op.create_index("ix_release_registry_is_active", "release_registry", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_release_registry_is_active", table_name="release_registry")
    op.drop_index("ix_release_registry_version_code", table_name="release_registry")
    op.drop_index("ix_release_registry_channel", table_name="release_registry")
    op.drop_table("release_registry")

    op.drop_index("ix_license_registry_status", table_name="license_registry")
    op.drop_index("ix_license_registry_license_id", table_name="license_registry")
    op.drop_index("ix_license_registry_installation_id", table_name="license_registry")
    op.drop_table("license_registry")
