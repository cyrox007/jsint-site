"""Добавить срок хранения отключённых лицензий.

Revision ID: b7d4e2f190ab
Revises: a4c8d12e7b60
Create Date: 2026-09-29
"""

from alembic import op
import sqlalchemy as sa


revision = "b7d4e2f190ab"
down_revision = "a4c8d12e7b60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "license_registry",
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_license_registry_revoked_at",
        "license_registry",
        ["revoked_at"],
    )

    # Для ранее отключённых лицензий используем время их последнего изменения.
    # Это позволяет начать отсчёт не с момента установки этой миграции.
    op.execute(
        sa.text(
            """
            UPDATE license_registry
            SET revoked_at = updated_at
            WHERE status = 'revoked'
              AND revoked_at IS NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_license_registry_revoked_at", table_name="license_registry")
    op.drop_column("license_registry", "revoked_at")
