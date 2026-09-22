"""Добавить состояние связи клиентов Workspace Organizer.

Revision ID: 2b6d8d9f4a11
Revises: 7f40a9d2c3b1
Create Date: 2026-09-22
"""

from alembic import op
import sqlalchemy as sa


revision = "2b6d8d9f4a11"
down_revision = "7f40a9d2c3b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("license_registry", sa.Column("license_not_before", sa.DateTime(timezone=True), nullable=True))
    op.add_column("license_registry", sa.Column("license_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("license_registry", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("license_registry", sa.Column("last_seen_ip", sa.String(length=64), nullable=True))
    op.add_column("license_registry", sa.Column("last_seen_action", sa.String(length=64), nullable=True))
    op.add_column("license_registry", sa.Column("last_client_version", sa.String(length=64), nullable=True))
    op.add_column("license_registry", sa.Column("last_client_version_code", sa.Integer(), nullable=True))
    op.add_column("license_registry", sa.Column("last_client_channel", sa.String(length=16), nullable=True))
    op.create_index("ix_license_registry_last_seen_at", "license_registry", ["last_seen_at"])


def downgrade() -> None:
    op.drop_index("ix_license_registry_last_seen_at", table_name="license_registry")
    op.drop_column("license_registry", "last_client_channel")
    op.drop_column("license_registry", "last_client_version_code")
    op.drop_column("license_registry", "last_client_version")
    op.drop_column("license_registry", "last_seen_action")
    op.drop_column("license_registry", "last_seen_ip")
    op.drop_column("license_registry", "last_seen_at")
    op.drop_column("license_registry", "license_expires_at")
    op.drop_column("license_registry", "license_not_before")
