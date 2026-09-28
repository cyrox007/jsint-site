from __future__ import annotations

import copy
from uuid import UUID

from sqlalchemy.orm import Session

from models.page import Page, PageBlock


HOME_BLOCK_TYPES = ("hero", "philosophy", "systems", "about", "resume")
HOME_BLOCK_LABELS = {
    "hero": "Первый экран",
    "philosophy": "Подход",
    "systems": "Публикации",
    "about": "О проекте",
    "resume": "Опыт работы",
}
HOME_BLOCK_DEFAULTS = {
    "hero": {
        "badge": "",
        "title": "",
        "accent": "",
        "description": "",
        "note": "",
        "terminal_lines": [],
        "metrics": [],
        "tags": [],
    },
    "philosophy": {
        "title": "Подход",
        "subtitle": "",
        "text": "",
    },
    "systems": {
        "title": "Публикации",
        "subtitle": "",
    },
    "about": {
        "title": "О проекте",
        "cards": [],
    },
    "resume": {
        "title": "Опыт работы",
        "subtitle": "",
        "items": [],
    },
}


class PageService:
    @staticmethod
    def get_page(
        session: Session,
        site_id: UUID,
        slug: str,
        *,
        published_only: bool = False,
    ) -> Page | None:
        query = session.query(Page).filter(Page.site_id == site_id, Page.slug == slug)
        if published_only:
            query = query.filter(Page.is_published.is_(True))
        return query.first()

    @classmethod
    def create_default_home(cls, session: Session, site_id: UUID) -> Page:
        existing = cls.get_page(session, site_id, "home")
        if existing is not None:
            return existing

        page = Page(
            site_id=site_id,
            slug="home",
            title="Главная",
            is_published=True,
        )
        session.add(page)
        session.flush()

        for position, block_type in enumerate(HOME_BLOCK_TYPES, start=1):
            session.add(
                PageBlock(
                    page_id=page.id,
                    block_type=block_type,
                    position=position * 100,
                    settings=copy.deepcopy(HOME_BLOCK_DEFAULTS[block_type]),
                    is_enabled=block_type != "resume",
                )
            )
        session.flush()
        return page

    @staticmethod
    def list_blocks(page: Page, *, enabled_only: bool = False) -> list[PageBlock]:
        blocks = sorted(
            page.blocks,
            key=lambda item: (
                item.position,
                item.created_at.isoformat() if item.created_at else "",
                str(item.id),
            ),
        )
        if enabled_only:
            return [item for item in blocks if item.is_enabled]
        return blocks

    @classmethod
    def block_settings(cls, page: Page | None) -> dict[str, dict]:
        if page is None:
            return {
                key: copy.deepcopy(value)
                for key, value in HOME_BLOCK_DEFAULTS.items()
            }

        result = {
            key: copy.deepcopy(value)
            for key, value in HOME_BLOCK_DEFAULTS.items()
        }
        for block in page.blocks:
            if block.block_type in result:
                result[block.block_type].update(block.settings or {})
        return result

    @classmethod
    def public_blocks(cls, page: Page) -> list[dict]:
        return [
            {
                "id": str(block.id),
                "type": block.block_type,
                "position": block.position,
                "settings": block.settings or {},
            }
            for block in cls.list_blocks(page, enabled_only=True)
        ]

    @classmethod
    def update_home(
        cls,
        session: Session,
        site_id: UUID,
        *,
        seo_title: str,
        seo_description: str,
        block_states: dict[str, dict],
        block_settings: dict[str, dict],
        commit: bool = True,
    ) -> Page:
        page = cls.get_page(session, site_id, "home")
        if page is None:
            page = cls.create_default_home(session, site_id)

        page.seo_title = seo_title.strip()[:255] or None
        page.seo_description = seo_description.strip()[:1000] or None

        by_type = {block.block_type: block for block in page.blocks}
        for block_type in HOME_BLOCK_TYPES:
            block = by_type.get(block_type)
            if block is None:
                block = PageBlock(
                    page_id=page.id,
                    block_type=block_type,
                    settings=copy.deepcopy(HOME_BLOCK_DEFAULTS[block_type]),
                )
                session.add(block)
                by_type[block_type] = block

            state = block_states.get(block_type, {})
            block.position = max(0, min(int(state.get("position", 100)), 9999))
            block.is_enabled = bool(state.get("enabled", False))
            block.settings = copy.deepcopy(
                block_settings.get(
                    block_type,
                    block.settings or HOME_BLOCK_DEFAULTS[block_type],
                )
            )
            session.add(block)

        session.add(page)
        session.flush()
        if commit:
            session.commit()
        session.refresh(page)
        return page
