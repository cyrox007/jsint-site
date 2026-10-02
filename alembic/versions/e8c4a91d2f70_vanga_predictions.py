"""Добавить снимки прогнозов Vanga.

Revision ID: e8c4a91d2f70
Revises: d2f7a91c4e60
Create Date: 2026-10-02
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "e8c4a91d2f70"
down_revision = "d2f7a91c4e60"
branch_labels = None
depends_on = None

_TABLE = "vanga_predictions"


def _ensure_index(index_name: str, columns: list[str]) -> None:
    inspector = sa.inspect(op.get_bind())
    existing = {item["name"] for item in inspector.get_indexes(_TABLE)}
    if index_name not in existing:
        op.create_index(index_name, _TABLE, columns)


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing_tables = set(inspector.get_table_names())

    if _TABLE not in existing_tables:
        op.create_table(
            _TABLE,
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
            ),
            sa.Column(
                "site_id",
                postgresql.UUID(as_uuid=True),
                nullable=False,
            ),
            sa.Column("imdb_id", sa.String(length=16), nullable=True),
            sa.Column("title", sa.String(length=240), nullable=False),
            sa.Column("year", sa.Integer(), nullable=False),
            sa.Column(
                "model_generation",
                sa.String(length=96),
                nullable=True,
            ),
            sa.Column("rating", sa.Numeric(precision=4, scale=2), nullable=False),
            sa.Column(
                "request_data",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
            ),
            sa.Column(
                "result_data",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(
                ["site_id"],
                ["sites.id"],
                ondelete="CASCADE",
            ),
        )

    for name, columns in (
        ("ix_vanga_predictions_site_id", ["site_id"]),
        ("ix_vanga_predictions_imdb_id", ["imdb_id"]),
        ("ix_vanga_predictions_title", ["title"]),
        ("ix_vanga_predictions_year", ["year"]),
        ("ix_vanga_predictions_model_generation", ["model_generation"]),
        ("ix_vanga_predictions_created_at", ["created_at"]),
    ):
        _ensure_index(name, columns)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if _TABLE in set(inspector.get_table_names()):
        op.drop_table(_TABLE)
