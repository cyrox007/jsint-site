"""Перенести содержимое главной из настроек сайта в блоки страницы.

Revision ID: c8d2f51a6e90
Revises: b3c8e12f4a71
Create Date: 2026-09-28
"""

from alembic import op
import sqlalchemy as sa


revision = "c8d2f51a6e90"
down_revision = "b3c8e12f4a71"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Переносим существующие настройки без потери пользовательских изменений.
    op.execute(
        sa.text(
            """
            UPDATE page_blocks AS block
            SET settings = CASE block.block_type
                WHEN 'hero' THEN COALESCE(site.settings -> 'hero', '{}'::jsonb)
                WHEN 'philosophy' THEN jsonb_build_object(
                    'title', COALESCE(site.settings #>> '{home,philosophy_title}', ''),
                    'subtitle', COALESCE(site.settings #>> '{home,philosophy_subtitle}', ''),
                    'text', COALESCE(site.settings #>> '{home,philosophy_text}', '')
                )
                WHEN 'systems' THEN jsonb_build_object(
                    'title', COALESCE(site.settings #>> '{home,systems_title}', ''),
                    'subtitle', COALESCE(site.settings #>> '{home,systems_subtitle}', '')
                )
                WHEN 'about' THEN jsonb_build_object(
                    'title', COALESCE(site.settings #>> '{home,about_title}', ''),
                    'cards', COALESCE(site.settings #> '{home,about_cards}', '[]'::jsonb)
                )
                ELSE block.settings
            END
            FROM pages AS page, sites AS site
            WHERE block.page_id = page.id
              AND page.site_id = site.id
              AND page.slug = 'home'
              AND block.block_type IN ('hero', 'philosophy', 'systems', 'about')
            """
        )
    )

    # После переноса page_blocks — единственный источник содержимого страниц.
    op.execute(
        sa.text(
            """
            UPDATE sites
            SET settings = (settings - 'hero' - 'home')
            WHERE settings ? 'hero' OR settings ? 'home'
            """
        )
    )


def downgrade() -> None:
    # Данные блоков не удаляем и не пытаемся сворачивать обратно:
    # это предотвратит потерю изменений, сделанных после миграции.
    pass
