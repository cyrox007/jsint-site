"""Добавить неизменяемый журнал control plane.

Revision ID: d4e9a61b7c20
Revises: c8d2f51a6e90
Create Date: 2026-09-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "d4e9a61b7c20"
down_revision = "c8d2f51a6e90"
branch_labels = None
depends_on = None

_TABLE = "control_plane_audit"
_INDEXED_COLUMNS = (
    "actor_kind",
    "actor_user_id",
    "action",
    "outcome",
    "target_type",
    "target_id",
    "installation_id",
    "license_id",
    "release_id",
    "created_at",
)
_REQUIRED_COLUMNS = {
    "id",
    "actor_kind",
    "actor_user_id",
    "actor_label",
    "action",
    "outcome",
    "target_type",
    "target_id",
    "installation_id",
    "license_id",
    "release_id",
    "details",
    "created_at",
}


def _create_audit_table() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_kind", sa.String(length=16), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_label", sa.String(length=320), nullable=True),
        sa.Column("action", sa.String(length=96), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("target_type", sa.String(length=48), nullable=True),
        sa.Column("target_id", sa.String(length=160), nullable=True),
        sa.Column("installation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("license_id", sa.String(length=128), nullable=True),
        sa.Column("release_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def _verify_existing_table(inspector: sa.Inspector) -> None:
    columns = {column["name"] for column in inspector.get_columns(_TABLE)}
    missing = sorted(_REQUIRED_COLUMNS - columns)
    if missing:
        raise RuntimeError(
            "Таблица control_plane_audit уже существует, но её структура "
            f"не соответствует миграции. Не хватает колонок: {', '.join(missing)}"
        )

    primary_key = inspector.get_pk_constraint(_TABLE).get("constrained_columns") or []
    if primary_key != ["id"]:
        raise RuntimeError(
            "Таблица control_plane_audit уже существует, но её PRIMARY KEY "
            f"неожиданный: {primary_key!r}. Ожидался ['id']."
        )


def _ensure_indexes(bind) -> None:
    inspector = sa.inspect(bind)
    existing = {
        item["name"]
        for item in inspector.get_indexes(_TABLE)
        if item.get("name")
    }
    for column in _INDEXED_COLUMNS:
        name = f"ix_control_plane_audit_{column}"
        if name in existing:
            continue
        op.create_index(name, _TABLE, [column])


def _ensure_immutable_trigger() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION reject_control_plane_audit_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'control_plane_audit is append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_control_plane_audit_immutable
        ON control_plane_audit
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_control_plane_audit_immutable
        BEFORE UPDATE OR DELETE ON control_plane_audit
        FOR EACH ROW EXECUTE FUNCTION reject_control_plane_audit_mutation()
        """
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table(_TABLE):
        # Поддерживаем БД, где таблица уже была создана до фиксации
        # alembic_version. Данные не удаляем и таблицу не пересоздаём.
        _verify_existing_table(inspector)
    else:
        _create_audit_table()

    _ensure_indexes(bind)
    _ensure_immutable_trigger()


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_control_plane_audit_immutable "
        "ON control_plane_audit"
    )
    op.execute("DROP FUNCTION IF EXISTS reject_control_plane_audit_mutation()")
    op.drop_table(_TABLE)
