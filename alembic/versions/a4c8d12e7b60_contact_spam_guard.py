"""Усилить дедупликацию обращений.

Revision ID: a4c8d12e7b60
Revises: f3b7e91c2a40
Create Date: 2026-09-29
"""

from alembic import op
import sqlalchemy as sa


revision = "a4c8d12e7b60"
down_revision = "f3b7e91c2a40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "contact_messages",
        sa.Column("fingerprint", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "uq_contact_messages_fingerprint",
        "contact_messages",
        ["fingerprint"],
        unique=True,
        postgresql_where=sa.text("fingerprint IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_contact_messages_fingerprint", table_name="contact_messages")
    op.drop_column("contact_messages", "fingerprint")
