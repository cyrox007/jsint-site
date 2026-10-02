"""Добавить фактические IMDb ratings к снимкам Vanga.

Revision ID: f6b1d4c7e820
Revises: e8c4a91d2f70
Create Date: 2026-10-02
"""

from alembic import op
import sqlalchemy as sa


revision = "f6b1d4c7e820"
down_revision = "e8c4a91d2f70"
branch_labels = None
depends_on = None

_TABLE = "vanga_predictions"


def _columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if _TABLE not in set(inspector.get_table_names()):
        return set()
    return {column["name"] for column in inspector.get_columns(_TABLE)}


def _ensure_index(index_name: str, columns: list[str]) -> None:
    inspector = sa.inspect(op.get_bind())
    existing = {item["name"] for item in inspector.get_indexes(_TABLE)}
    if index_name not in existing:
        op.create_index(index_name, _TABLE, columns)


def upgrade() -> None:
    existing = _columns()
    if not existing:
        raise RuntimeError(
            "Таблица vanga_predictions отсутствует: сначала примените "
            "миграцию e8c4a91d2f70."
        )

    additions = (
        (
            "actual_rating",
            sa.Column("actual_rating", sa.Numeric(precision=4, scale=2), nullable=True),
        ),
        (
            "actual_num_votes",
            sa.Column("actual_num_votes", sa.BigInteger(), nullable=True),
        ),
        (
            "absolute_error",
            sa.Column("absolute_error", sa.Numeric(precision=4, scale=2), nullable=True),
        ),
        (
            "actual_rating_updated_at",
            sa.Column("actual_rating_updated_at", sa.DateTime(timezone=True), nullable=True),
        ),
    )
    for name, column in additions:
        if name not in existing:
            op.add_column(_TABLE, column)

    for name, columns in (
        ("ix_vanga_predictions_actual_rating", ["actual_rating"]),
        ("ix_vanga_predictions_absolute_error", ["absolute_error"]),
        (
            "ix_vanga_predictions_actual_rating_updated_at",
            ["actual_rating_updated_at"],
        ),
    ):
        _ensure_index(name, columns)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if _TABLE not in set(inspector.get_table_names()):
        return

    existing_indexes = {item["name"] for item in inspector.get_indexes(_TABLE)}
    for name in (
        "ix_vanga_predictions_actual_rating_updated_at",
        "ix_vanga_predictions_absolute_error",
        "ix_vanga_predictions_actual_rating",
    ):
        if name in existing_indexes:
            op.drop_index(name, table_name=_TABLE)

    existing = _columns()
    for name in (
        "actual_rating_updated_at",
        "absolute_error",
        "actual_num_votes",
        "actual_rating",
    ):
        if name in existing:
            op.drop_column(_TABLE, name)
