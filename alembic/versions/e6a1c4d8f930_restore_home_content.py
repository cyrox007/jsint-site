"""Восстановить содержимое главной после переноса в page_blocks.

Revision ID: e6a1c4d8f930
Revises: d4e9a61b7c20
Create Date: 2026-09-29
"""

from alembic import op
import sqlalchemy as sa


revision = "e6a1c4d8f930"
down_revision = "d4e9a61b7c20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Исправляем только основной встроенный сайт и только пустые значения.
    # Уже заполненные пользователем поля не перезаписываются.
    op.execute(
        sa.text(
            """
            UPDATE page_blocks AS block
            SET settings = COALESCE(block.settings, '{}'::jsonb) || jsonb_build_object(
                'badge', CASE
                    WHEN COALESCE(block.settings ->> 'badge', '') = ''
                    THEN 'Независимая инженерная мини-студия'
                    ELSE block.settings ->> 'badge'
                END,
                'title', CASE
                    WHEN COALESCE(block.settings ->> 'title', '') = ''
                    THEN '+УЛЬТРА'
                    ELSE block.settings ->> 'title'
                END,
                'accent', CASE
                    WHEN COALESCE(block.settings ->> 'accent', '') = ''
                    THEN 'архитектура сложных web-систем'
                    ELSE block.settings ->> 'accent'
                END,
                'description', CASE
                    WHEN COALESCE(block.settings ->> 'description', '') = ''
                    THEN E'+УЛЬТРА — независимая студия, специализирующаяся на backend-системах, realtime-инфраструктуре, аудите архитектуры и доработке сложных web-платформ.\n\nОсновной фокус — исправление технических проблем, развитие production-систем и независимой инфраструктуры.'
                    ELSE block.settings ->> 'description'
                END,
                'note', CASE
                    WHEN COALESCE(block.settings ->> 'note', '') = ''
                    THEN '+УЛЬТРА · backend · realtime · инфраструктура · аудит систем'
                    ELSE block.settings ->> 'note'
                END,
                'terminal_lines', CASE
                    WHEN jsonb_typeof(block.settings -> 'terminal_lines') = 'array'
                         AND jsonb_array_length(block.settings -> 'terminal_lines') > 0
                    THEN block.settings -> 'terminal_lines'
                    ELSE '["backend-архитектура","realtime-взаимодействие","self-hosted платформы","аудит production-среды"]'::jsonb
                END,
                'tags', CASE
                    WHEN jsonb_typeof(block.settings -> 'tags') = 'array'
                         AND jsonb_array_length(block.settings -> 'tags') > 0
                    THEN block.settings -> 'tags'
                    ELSE '["Backend","Realtime","Архитектура","Self-hosted","Аудит систем"]'::jsonb
                END
            )
            FROM pages AS page, sites AS site
            WHERE block.page_id = page.id
              AND page.site_id = site.id
              AND site.is_default IS TRUE
              AND page.slug = 'home'
              AND block.block_type = 'hero'
            """
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE page_blocks AS block
            SET settings = COALESCE(block.settings, '{}'::jsonb) || jsonb_build_object(
                'title', CASE
                    WHEN COALESCE(block.settings ->> 'title', '') = ''
                    THEN 'Подход'
                    ELSE block.settings ->> 'title'
                END,
                'subtitle', CASE
                    WHEN COALESCE(block.settings ->> 'subtitle', '') = ''
                    THEN 'Сложные backend-системы, realtime-взаимодействие и независимая инфраструктура.'
                    ELSE block.settings ->> 'subtitle'
                END,
                'text', CASE
                    WHEN COALESCE(block.settings ->> 'text', '') = ''
                    THEN E'+УЛЬТРА — не просто персональное портфолио, а независимая инженерная мини-студия, ориентированная на создание, доработку и восстановление сложных web-систем.\n\nОсновной фокус — backend-архитектура, realtime-взаимодействие, self-hosted платформы, аудит production-среды и исправление критических инфраструктурных проблем.\n\nПодход — идти дальше типового решения: разбирать систему целиком, устранять первопричину и оставлять архитектуру, которую можно поддерживать и развивать.'
                    ELSE block.settings ->> 'text'
                END
            )
            FROM pages AS page, sites AS site
            WHERE block.page_id = page.id
              AND page.site_id = site.id
              AND site.is_default IS TRUE
              AND page.slug = 'home'
              AND block.block_type = 'philosophy'
            """
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE page_blocks AS block
            SET settings = COALESCE(block.settings, '{}'::jsonb) || jsonb_build_object(
                'title', CASE
                    WHEN COALESCE(block.settings ->> 'title', '') = ''
                    THEN 'Публикации'
                    ELSE block.settings ->> 'title'
                END,
                'subtitle', CASE
                    WHEN COALESCE(block.settings ->> 'subtitle', '') = ''
                    THEN 'Разборы архитектуры, разработки и практические материалы.'
                    ELSE block.settings ->> 'subtitle'
                END
            )
            FROM pages AS page, sites AS site
            WHERE block.page_id = page.id
              AND page.site_id = site.id
              AND site.is_default IS TRUE
              AND page.slug = 'home'
              AND block.block_type = 'systems'
            """
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE page_blocks AS block
            SET settings = COALESCE(block.settings, '{}'::jsonb) || jsonb_build_object(
                'title', CASE
                    WHEN COALESCE(block.settings ->> 'title', '') = ''
                    THEN 'О студии'
                    ELSE block.settings ->> 'title'
                END,
                'cards', CASE
                    WHEN jsonb_typeof(block.settings -> 'cards') = 'array'
                         AND jsonb_array_length(block.settings -> 'cards') > 0
                    THEN block.settings -> 'cards'
                    ELSE jsonb_build_array(
                        jsonb_build_object(
                            'title', 'Интерактивная инженерия',
                            'text', 'Разработка и доработка систем с интенсивным обменом данными: backend, API, realtime-взаимодействие и web-интерфейсы.'
                        ),
                        jsonb_build_object(
                            'title', 'Независимая инфраструктура',
                            'text', 'Особый интерес — self-hosted и открытые решения, которые можно контролировать, разворачивать и сопровождать без привязки к закрытой платформе.'
                        )
                    )
                END
            )
            FROM pages AS page, sites AS site
            WHERE block.page_id = page.id
              AND page.site_id = site.id
              AND site.is_default IS TRUE
              AND page.slug = 'home'
              AND block.block_type = 'about'
            """
        )
    )


def downgrade() -> None:
    # Автоматически удалять восстановленный текст нельзя: после миграции его
    # мог изменить оператор через CMS.
    pass
