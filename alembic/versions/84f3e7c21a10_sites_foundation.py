"""Базовая мультисайтовая конфигурация публичной части.

Revision ID: 84f3e7c21a10
Revises: 2b6d8d9f4a11
Create Date: 2026-09-28
"""

from alembic import op
import sqlalchemy as sa


revision = "84f3e7c21a10"
down_revision = "2b6d8d9f4a11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sites",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("brand_subtitle", sa.String(length=160), nullable=False),
        sa.Column("base_url", sa.String(length=255), nullable=False),
        sa.Column("contact_email", sa.String(length=255), nullable=False),
        sa.Column("github_url", sa.String(length=255), nullable=False),
        sa.Column("seo_title", sa.String(length=255), nullable=False),
        sa.Column("seo_description", sa.Text(), nullable=False),
        sa.Column("hero_badge", sa.String(length=255), nullable=False),
        sa.Column("hero_title", sa.String(length=255), nullable=False),
        sa.Column("hero_accent", sa.String(length=255), nullable=False),
        sa.Column("hero_description", sa.Text(), nullable=False),
        sa.Column("philosophy_title", sa.String(length=255), nullable=False),
        sa.Column("philosophy_subtitle", sa.String(length=255), nullable=False),
        sa.Column("philosophy_body", sa.Text(), nullable=False),
        sa.Column("about_title", sa.String(length=255), nullable=False),
        sa.Column("about_primary_title", sa.String(length=255), nullable=False),
        sa.Column("about_primary_body", sa.Text(), nullable=False),
        sa.Column("about_secondary_title", sa.String(length=255), nullable=False),
        sa.Column("about_secondary_body", sa.Text(), nullable=False),
        sa.Column("footer_note", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_sites_slug", "sites", ["slug"], unique=True)
    op.create_index("ix_sites_is_active", "sites", ["is_active"])
    op.create_index("ix_sites_is_default", "sites", ["is_default"])

    sites = sa.table(
        "sites",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("slug", sa.String),
        sa.column("name", sa.String),
        sa.column("brand_subtitle", sa.String),
        sa.column("base_url", sa.String),
        sa.column("contact_email", sa.String),
        sa.column("github_url", sa.String),
        sa.column("seo_title", sa.String),
        sa.column("seo_description", sa.Text),
        sa.column("hero_badge", sa.String),
        sa.column("hero_title", sa.String),
        sa.column("hero_accent", sa.String),
        sa.column("hero_description", sa.Text),
        sa.column("philosophy_title", sa.String),
        sa.column("philosophy_subtitle", sa.String),
        sa.column("philosophy_body", sa.Text),
        sa.column("about_title", sa.String),
        sa.column("about_primary_title", sa.String),
        sa.column("about_primary_body", sa.Text),
        sa.column("about_secondary_title", sa.String),
        sa.column("about_secondary_body", sa.Text),
        sa.column("footer_note", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("is_default", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.execute(sites.insert().values(
        id="0f6a9d64-8f23-4a89-baf4-8bd6e576c2d1",
        slug="jsinteractive",
        name="+УЛЬТРА",
        brand_subtitle="на базе jsinteractive",
        base_url="https://jsinteractive.ru",
        contact_email="cyrox007@gmail.com",
        github_url="https://github.com/cyrox007",
        seo_title="JSInteractive | +УЛЬТРА",
        seo_description="+УЛЬТРА — независимая инженерная мини-студия: backend, realtime, аудит и архитектура web-систем.",
        hero_badge="Независимая инженерная мини-студия",
        hero_title="+УЛЬТРА",
        hero_accent="архитектура сложных web-систем",
        hero_description="+УЛЬТРА — независимая студия, специализирующаяся на backend-системах, realtime-инфраструктуре, аудите архитектуры и доработке сложных web-платформ.\n\nОсновное направление — исправление технических проблем, оптимизация production-систем и развитие независимой инфраструктуры.",
        philosophy_title="Философия",
        philosophy_subtitle="Сложные backend-системы, realtime взаимодействие и независимая инфраструктура.",
        philosophy_body="+УЛЬТРА — независимая инженерная мини-студия, ориентированная на создание, доработку и восстановление сложных web-систем.\n\nОсновной фокус — backend-архитектура, realtime взаимодействие, self-hosted платформы, аудит production-среды и исправление критических инфраструктурных проблем.",
        about_title="О студии",
        about_primary_title="Интерактивная инженерия",
        about_primary_body="Разработка систем для быстрой обработки данных и обмена информацией в реальном времени: API, backend и web-приложения.",
        about_secondary_title="Независимый открытый исходный код",
        about_secondary_body="Большая часть проектов развивается как независимые платформы, которые пользователь может контролировать сам.",
        footer_note="backend systems · realtime infrastructure · аудит систем",
        is_active=True,
        is_default=True,
        created_at=sa.func.now(),
        updated_at=sa.func.now(),
    ))


def downgrade() -> None:
    op.drop_index("ix_sites_is_default", table_name="sites")
    op.drop_index("ix_sites_is_active", table_name="sites")
    op.drop_index("ix_sites_slug", table_name="sites")
    op.drop_table("sites")
