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


def _users_id_is_referenceable(inspector: sa.Inspector) -> bool:
    """Проверяет, можно ли безопасно создать FK на users.id.

    На старых production-инсталляциях таблица users могла существовать ещё до
    актуальной Alembic-схемы и не иметь PK/UNIQUE на id. PostgreSQL запрещает
    ссылаться внешним ключом на такой столбец, поэтому для legacy-схемы связь
    остаётся логической на уровне приложения, а для нормальной схемы FK
    создаётся как обычно.
    """
    primary_key = inspector.get_pk_constraint("users") or {}
    if set(primary_key.get("constrained_columns") or []) == {"id"}:
        return True

    for constraint in inspector.get_unique_constraints("users"):
        if list(constraint.get("column_names") or []) == ["id"]:
            return True
    return False


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if _TABLE in set(inspector.get_table_names()):
        return

    user_id_constraints = []
    if _users_id_is_referenceable(inspector):
        user_id_constraints.append(sa.ForeignKey("users.id", ondelete="CASCADE"))

    op.create_table(
        _TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            *user_id_constraints,
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
