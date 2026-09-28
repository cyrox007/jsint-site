"""Добавить каналы публикации для нескольких сайтов.

Revision ID: 9a4f2d7c1b60
Revises: 7e1d5b2c9f40
Create Date: 2026-09-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "9a4f2d7c1b60"
down_revision = "7e1d5b2c9f40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "publication_sites",
        sa.Column("publication_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["publication_id"],
            ["publications.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["site_id"],
            ["sites.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("publication_id", "site_id"),
        sa.UniqueConstraint(
            "site_id",
            "slug",
            name="uq_publication_sites_site_slug",
        ),
    )
    op.create_index("ix_publication_sites_site_id", "publication_sites", ["site_id"])
    op.create_index(
        "ix_publication_sites_category_id",
        "publication_sites",
        ["category_id"],
    )
    op.create_index(
        "ix_publication_sites_is_published",
        "publication_sites",
        ["is_published"],
    )

    # Каждая существующая публикация получает канал своего текущего сайта.
    op.execute(
        sa.text(
            """
            INSERT INTO publication_sites (
                publication_id,
                site_id,
                slug,
                category_id,
                is_published,
                published_at,
                created_at,
                updated_at
            )
            SELECT
                id,
                site_id,
                slug,
                category_id,
                is_published,
                published_at,
                created_at,
                updated_at
            FROM publications
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_publication_sites_is_published", table_name="publication_sites")
    op.drop_index("ix_publication_sites_category_id", table_name="publication_sites")
    op.drop_index("ix_publication_sites_site_id", table_name="publication_sites")
    op.drop_table("publication_sites")
