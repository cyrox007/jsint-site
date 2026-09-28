"""Добавить управляемые страницы и блоки публичной витрины.

Revision ID: 7e1d5b2c9f40
Revises: 4c91f7a2d8e3
Create Date: 2026-09-28
"""

from datetime import datetime, timezone
from uuid import UUID

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "7e1d5b2c9f40"
down_revision = "4c91f7a2d8e3"
branch_labels = None
depends_on = None

DEFAULT_SITE_ID = UUID("00000000-0000-0000-0000-000000000001")
HOME_PAGE_ID = UUID("10000000-0000-0000-0000-000000000001")


def upgrade() -> None:
    op.create_table(
        "pages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("seo_title", sa.String(length=255), nullable=True),
        sa.Column("seo_description", sa.Text(), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("site_id", "slug", name="uq_pages_site_slug"),
    )
    op.create_index("ix_pages_site_id", "pages", ["site_id"])
    op.create_index("ix_pages_is_published", "pages", ["is_published"])

    op.create_table(
        "page_blocks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("block_type", sa.String(length=80), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["page_id"], ["pages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_page_blocks_page_id", "page_blocks", ["page_id"])
    op.create_index("ix_page_blocks_block_type", "page_blocks", ["block_type"])
    op.create_index("ix_page_blocks_position", "page_blocks", ["position"])
    op.create_index("ix_page_blocks_is_enabled", "page_blocks", ["is_enabled"])

    pages = sa.table(
        "pages",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("site_id", postgresql.UUID(as_uuid=True)),
        sa.column("slug", sa.String()),
        sa.column("title", sa.String()),
        sa.column("seo_title", sa.String()),
        sa.column("seo_description", sa.Text()),
        sa.column("is_published", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    blocks = sa.table(
        "page_blocks",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("page_id", postgresql.UUID(as_uuid=True)),
        sa.column("block_type", sa.String()),
        sa.column("position", sa.Integer()),
        sa.column("settings", postgresql.JSONB()),
        sa.column("is_enabled", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    now = datetime.now(timezone.utc)
    op.bulk_insert(
        pages,
        [
            {
                "id": HOME_PAGE_ID,
                "site_id": DEFAULT_SITE_ID,
                "slug": "home",
                "title": "Главная",
                "seo_title": None,
                "seo_description": None,
                "is_published": True,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )

    resume_settings = {
        "title": "Опыт работы",
        "subtitle": "Более 5 лет коммерческой разработки и поддержки ИТ-инфраструктуры",
        "items": [
            {
                "company": "Мебельный Рай",
                "period": "Июнь 2026 — настоящее время",
                "position": "Tech Lead / Веб-архитектор",
                "description": (
                    "Технический лидер и архитектор всего веб-направления компании. "
                    "Отвечаю за стратегию разработки, выбор стека, управление командой "
                    "и интеграцию веб-систем с бизнес-процессами."
                ),
                "achievements": [
                    "Создание и развитие веб-инфраструктуры компании с нуля: архитектура, стек, CI/CD.",
                    "Управление внешними подрядчиками: постановка задач, контроль качества и приёмка работ.",
                    "Проектирование интеграций между сайтами, 1С и внешними сервисами.",
                    "Оптимизация производительности, аудит безопасности и масштабирование решений.",
                    "Бюджетирование IT-проектов и поиск оптимальных технических решений.",
                    "Выстраивание коммуникации между бизнесом и IT-командой.",
                ],
                "technologies": [
                    "PHP",
                    "Laravel",
                    "JavaScript",
                    "React",
                    "MySQL",
                    "REST API",
                    "Git",
                    "Linux",
                    "Docker",
                    "CI/CD",
                ],
            },
            {
                "company": "Wondersoft",
                "period": "Февраль 2022 — Декабрь 2025 (3 года 11 месяцев)",
                "position": "Full-Stack разработчик / Ведущий разработчик",
                "description": (
                    "Разработка, сопровождение и развитие веб-проектов для коммерческих "
                    "и корпоративных заказчиков. Выступал основным техническим специалистом "
                    "в большинстве проектов."
                ),
                "achievements": [
                    "Поддержка и аудит проектов на PHP-стеке: WordPress, 1С-Битрикс, Laravel.",
                    "Разработка REST API, интеграция с CRM и платёжными системами.",
                    "Оптимизация производительности и рефакторинг легаси-кода.",
                    "Проектирование административных панелей и внутренних инструментов.",
                ],
                "technologies": [
                    "PHP",
                    "WordPress",
                    "1С-Битрикс",
                    "Laravel",
                    "JavaScript",
                    "Vue.js",
                    "MySQL",
                    "REST API",
                    "Git",
                    "Linux",
                ],
            },
            {
                "company": "ГУЗ Чаплыгинская РБ",
                "period": "Сентябрь 2024 — Июнь 2026 (1 год 10 месяцев)",
                "position": "Специалист по информационным технологиям / Системный администратор",
                "description": (
                    "Обеспечение бесперебойной работы ИТ-инфраструктуры медицинского учреждения, "
                    "техническая поддержка сотрудников и сопровождение медицинского ПО."
                ),
                "achievements": [
                    "Администрирование рабочих станций Windows и RedOS, а также локальной сети.",
                    "Поддержка медицинской информационной системы «Квазар».",
                    "Настройка ЭЦП и государственных информационных сервисов.",
                    "Удалённое и выездное устранение неисправностей в удалённых подразделениях.",
                ],
                "technologies": [
                    "Windows",
                    "RedOS",
                    "МИС «Квазар»",
                    "TCP/IP",
                    "Active Directory",
                    "ЭЦП",
                ],
            },
            {
                "company": "BeBrainee",
                "period": "Сентябрь 2021 — Декабрь 2022 (1 год 4 месяца)",
                "position": "Frontend-разработчик / Fullstack-разработчик",
                "description": (
                    "Разработка и сопровождение веб-приложений на Python-стеке. "
                    "Расширение зоны ответственности от frontend до fullstack."
                ),
                "achievements": [
                    "Разработка пользовательских интерфейсов на HTML, CSS, JavaScript и Vue.js.",
                    "Интеграция с backend на Flask и FastAPI.",
                    "Работа с Jinja2 и серверным рендерингом.",
                    "Поддержка legacy-кода на PHP и Laravel.",
                ],
                "technologies": [
                    "Python",
                    "Flask",
                    "FastAPI",
                    "PHP",
                    "Laravel",
                    "JavaScript",
                    "Vue.js",
                    "React",
                    "Jinja2",
                    "REST API",
                    "Git",
                ],
            },
        ],
    }

    op.bulk_insert(
        blocks,
        [
            {
                "id": UUID("20000000-0000-0000-0000-000000000001"),
                "page_id": HOME_PAGE_ID,
                "block_type": "hero",
                "position": 100,
                "settings": {},
                "is_enabled": True,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": UUID("20000000-0000-0000-0000-000000000002"),
                "page_id": HOME_PAGE_ID,
                "block_type": "philosophy",
                "position": 200,
                "settings": {},
                "is_enabled": True,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": UUID("20000000-0000-0000-0000-000000000003"),
                "page_id": HOME_PAGE_ID,
                "block_type": "systems",
                "position": 300,
                "settings": {},
                "is_enabled": True,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": UUID("20000000-0000-0000-0000-000000000004"),
                "page_id": HOME_PAGE_ID,
                "block_type": "about",
                "position": 400,
                "settings": {},
                "is_enabled": True,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": UUID("20000000-0000-0000-0000-000000000005"),
                "page_id": HOME_PAGE_ID,
                "block_type": "resume",
                "position": 500,
                "settings": resume_settings,
                "is_enabled": True,
                "created_at": now,
                "updated_at": now,
            },
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_page_blocks_is_enabled", table_name="page_blocks")
    op.drop_index("ix_page_blocks_position", table_name="page_blocks")
    op.drop_index("ix_page_blocks_block_type", table_name="page_blocks")
    op.drop_index("ix_page_blocks_page_id", table_name="page_blocks")
    op.drop_table("page_blocks")

    op.drop_index("ix_pages_is_published", table_name="pages")
    op.drop_index("ix_pages_site_id", table_name="pages")
    op.drop_table("pages")
