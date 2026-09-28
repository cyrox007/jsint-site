"""Добавить реестр сайтов и разделение публичного контента.

Revision ID: 4c91f7a2d8e3
Revises: 2b6d8d9f4a11
Create Date: 2026-09-28
"""

from datetime import datetime, timezone
from uuid import UUID

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "4c91f7a2d8e3"
down_revision = "2b6d8d9f4a11"
branch_labels = None
depends_on = None

DEFAULT_SITE_ID = UUID("00000000-0000-0000-0000-000000000001")


def _drop_slug_unique(table_name: str) -> None:
    inspector = sa.inspect(op.get_bind())
    for constraint in inspector.get_unique_constraints(table_name):
        if constraint.get("column_names") == ["slug"] and constraint.get("name"):
            op.drop_constraint(constraint["name"], table_name, type_="unique")


def upgrade() -> None:
    op.create_table(
        "sites",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("theme_key", sa.String(length=80), nullable=False),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_sites_key"),
    )
    op.create_index("ix_sites_key", "sites", ["key"])
    op.create_index("ix_sites_is_active", "sites", ["is_active"])
    op.create_index("ix_sites_is_default", "sites", ["is_default"])

    sites = sa.table(
        "sites",
        sa.column("id", sa.UUID()),
        sa.column("key", sa.String()),
        sa.column("name", sa.String()),
        sa.column("base_url", sa.Text()),
        sa.column("theme_key", sa.String()),
        sa.column("settings", postgresql.JSONB()),
        sa.column("is_active", sa.Boolean()),
        sa.column("is_default", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(timezone.utc)
    op.bulk_insert(
        sites,
        [
            {
                "id": DEFAULT_SITE_ID,
                "key": "jsinteractive",
                "name": "JSInteractive",
                "base_url": None,
                "theme_key": "ultra",
                "settings": {},
                "is_active": True,
                "is_default": True,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )

    op.add_column("categories", sa.Column("site_id", sa.UUID(), nullable=True))
    op.add_column("publications", sa.Column("site_id", sa.UUID(), nullable=True))

    op.execute(
        sa.text("UPDATE categories SET site_id = :site_id WHERE site_id IS NULL").bindparams(
            site_id=DEFAULT_SITE_ID
        )
    )
    op.execute(
        sa.text("UPDATE publications SET site_id = :site_id WHERE site_id IS NULL").bindparams(
            site_id=DEFAULT_SITE_ID
        )
    )

    op.alter_column("categories", "site_id", nullable=False)
    op.alter_column("publications", "site_id", nullable=False)
    op.create_foreign_key(
        "fk_categories_site_id_sites",
        "categories",
        "sites",
        ["site_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_publications_site_id_sites",
        "publications",
        "sites",
        ["site_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_categories_site_id", "categories", ["site_id"])
    op.create_index("ix_publications_site_id", "publications", ["site_id"])

    _drop_slug_unique("categories")
    _drop_slug_unique("publications")
    op.create_unique_constraint("uq_categories_site_slug", "categories", ["site_id", "slug"])
    op.create_unique_constraint("uq_publications_site_slug", "publications", ["site_id", "slug"])


def downgrade() -> None:
    op.drop_constraint("uq_publications_site_slug", "publications", type_="unique")
    op.drop_constraint("uq_categories_site_slug", "categories", type_="unique")
    op.create_unique_constraint("uq_publications_slug", "publications", ["slug"])
    op.create_unique_constraint("uq_categories_slug", "categories", ["slug"])

    op.drop_index("ix_publications_site_id", table_name="publications")
    op.drop_index("ix_categories_site_id", table_name="categories")
    op.drop_constraint("fk_publications_site_id_sites", "publications", type_="foreignkey")
    op.drop_constraint("fk_categories_site_id_sites", "categories", type_="foreignkey")
    op.drop_column("publications", "site_id")
    op.drop_column("categories", "site_id")

    op.drop_index("ix_sites_is_default", table_name="sites")
    op.drop_index("ix_sites_is_active", table_name="sites")
    op.drop_index("ix_sites_key", table_name="sites")
    op.drop_table("sites")
