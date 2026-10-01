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

_TABLE = "admin_notification_preferences"
_REQUIRED_COLUMNS = {
    "id",
    "push_enabled",
    "push_url",
    "push_token_encrypted",
    "notify_contact",
    "notify_diagnostic",
    "notify_urgent",
    "created_at",
    "updated_at",
}


def _existing_columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if _TABLE not in set(inspector.get_table_names()):
        return set()
    return {column["name"] for column in inspector.get_columns(_TABLE)}


def upgrade() -> None:
    existing_columns = _existing_columns()

    if existing_columns:
        missing = sorted(_REQUIRED_COLUMNS - existing_columns)
        if missing:
            raise RuntimeError(
                "Таблица admin_notification_preferences уже существует, "
                "но её структура неполная. Не хватает колонок: "
                + ", ".join(missing)
            )
        # Таблица могла остаться после аварийного rollback, когда DDL уже
        # применился, а alembic_version был восстановлен на предыдущую revision.
        # В этом случае повторный CREATE TABLE не нужен: Alembic после успешного
        # завершения upgrade сам зафиксирует revision d2f7a91c4e60.
        return

    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "push_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("push_url", sa.String(length=1024), nullable=True),
        sa.Column("push_token_encrypted", sa.Text(), nullable=True),
        sa.Column(
            "notify_contact",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "notify_diagnostic",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "notify_urgent",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if _TABLE in set(inspector.get_table_names()):
        op.drop_table(_TABLE)
