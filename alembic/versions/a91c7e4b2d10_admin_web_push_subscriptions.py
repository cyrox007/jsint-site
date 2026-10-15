"""Добавить подписки Web Push для устройств администратора.

Revision ID: a91c7e4b2d10
Revises: f6b1d4c7e820
Create Date: 2026-10-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "a91c7e4b2d10"
down_revision = "f6b1d4c7e820"
branch_labels = None
depends_on = None

_TABLE = "admin_web_push_subscriptions"


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if _TABLE in set(inspector.get_table_names()):
        return

    op.create_table(
        _TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("endpoint", sa.Text(), nullable=False, unique=True),
        sa.Column("p256dh", sa.Text(), nullable=False),
        sa.Column("auth", sa.Text(), nullable=False),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("device_label", sa.String(length=120), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
    )
    op.create_index(
        "ix_admin_web_push_subscriptions_user_id",
        _TABLE,
        ["user_id"],
    )
    op.create_index(
        "ix_admin_web_push_subscriptions_enabled",
        _TABLE,
        ["enabled"],
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if _TABLE in set(inspector.get_table_names()):
        op.drop_table(_TABLE)
