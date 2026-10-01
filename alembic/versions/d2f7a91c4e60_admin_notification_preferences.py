"""Добавить настраиваемый push-канал администратора.

Revision ID: d2f7a91c4e60
Revises: c1e6a42f90d3
Create Date: 2026-10-01
"""

from alembic import op
import sqlalchemy as sa


revision = "d2f7a91c4e60"
down_revision = "c1e6a42f90d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_notification_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("push_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("push_url", sa.String(length=1024), nullable=True),
        sa.Column("push_token_encrypted", sa.Text(), nullable=True),
        sa.Column("notify_contact", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notify_diagnostic", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notify_urgent", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("admin_notification_preferences")
