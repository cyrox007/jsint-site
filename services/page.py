from __future__ import annotations

import copy
from uuid import UUID

from sqlalchemy.orm import Session

from models.page import Page, PageBlock
from utils.validation import validate_slug


HOME_BLOCK_TYPES = ("hero", "philosophy", "systems", "about", "resume")
HOME_BLOCK_ANCHORS = {
    "philosophy": "philosophy",
    "systems": "systems",
    "about": "about",
    "resume": "resume",
}
GENERIC_BLOCK_TYPES = ("rich_text", "publication_feed", "callout", "links")
GENERIC_BLOCK_LABELS = {
    "rich_text": "Текстовый блок",
    "publication_feed": "Лента публикаций",
    "callout": "Призыв к действию",
    "links": "Список ссылок",
}

HOME_BLOCK_LABELS = {
    "hero": "Первый экран",
    "philosophy": "Подход",
    "systems": "Публикации",
    "about": "О проекте",
    "resume": "Опыт работы",
}
HOME_BLOCK_DEFAULTS = {
    "hero": {
        "badge": "Независимая инженерная мини-студия",
        "title": "+УЛЬТРА",
        "accent": "архитектура сложных web-систем",
        "description": (
            "+УЛЬТРА — независимая студия, специализирующаяся на backend-системах, "
            "realtime-инфраструктуре, аудите архитектуры и доработке сложных web-платформ.\n\n"
            "Основной фокус — исправление технических проблем, развитие production-систем "
            "и независимой инфраструктуры."
        ),
        "note": "+УЛЬТРА · backend · realtime · инфраструктура · аудит систем",
        "materials_label": "Смотреть материалы",
        "contact_label": "Связаться",
        "console_eyebrow": "system / overview",
        "console_title": "Рабочий контур",
        "console_status": "online",
        "terminal_lines": [
            "backend-архитектура",
            "realtime-взаимодействие",
            "self-hosted платформы",
            "аудит production-среды",
        ],
        "metrics": [],
        "tags": [
            "Backend",
            "Realtime",
            "Архитектура",
            "Self-hosted",
            "Аудит систем",
        ],
    },
    "philosophy": {
        "kicker": "01 / Принципы",
        "title": "Подход",
        "subtitle": "Сложные backend-системы, realtime-взаимодействие и независимая инфраструктура.",
        "text": (
            "+УЛЬТРА — не просто персональное портфолио, а независимая инженерная "
            "мини-студия, ориентированная на создание, доработку и восстановление "
            "сложных web-систем.\n\n"
            "Основной фокус — backend-архитектура, realtime-взаимодействие, self-hosted "
            "платформы, аудит production-среды и исправление критических "
            "инфраструктурных проблем.\n\n"
            "Подход — идти дальше типового решения: разбирать систему целиком, устранять "
            "первопричину и оставлять архитектуру, которую можно поддерживать и развивать."
        ),
    },
    "systems": {
        "kicker": "02 / Материалы",
        "title": "Публикации",
        "subtitle": "Разборы архитектуры, разработки и практические материалы.",
        "article_label": "Открыть материал",
        "empty_text": "Пока нет опубликованных материалов.",
    },
    "about": {
        "kicker": "03 / Контекст",
        "title": "О студии",
        "cards": [
            {
                "title": "Интерактивная инженерия",
                "text": (
                    "Разработка и доработка систем с интенсивным обменом данными: "
                    "backend, API, realtime-взаимодействие и web-интерфейсы."
                ),
            },
            {
                "title": "Независимая инфраструктура",
                "text": (
                    "Особый интерес — self-hosted и открытые решения, которые можно "
                    "контролировать, разворачивать и сопровождать без привязки к закрытой платформе."
                ),
            },
        ],
    },
    "resume": {
        "kicker": "04 / Практика",
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
        result: list[dict] = []
        for block in cls.list_blocks(page, enabled_only=True):
            settings = block.settings or {}
            if block.block_type == "philosophy" and not str(settings.get("text") or "").strip():
                continue
            if block.block_type == "about" and not any(
                item.get("title") or item.get("text")
                for item in settings.get("cards", [])
                if isinstance(item, dict)
            ):
                continue
            if block.block_type == "resume" and not any(
                item.get("company") or item.get("position") or item.get("description")
                for item in settings.get("items", [])
                if isinstance(item, dict)
            ):
                continue

            result.append(
                {
                    "id": str(block.id),
                    "type": block.block_type,
                    "position": block.position,
                    "settings": settings,
                }
            )
        return result

    @staticmethod
    def home_anchor_ids(blocks: list[dict]) -> set[str]:
        return {
            HOME_BLOCK_ANCHORS[block["type"]]
            for block in blocks
            if block.get("type") in HOME_BLOCK_ANCHORS
        }

    @classmethod
    def filter_navigation(
        cls,
        navigation: list[dict],
        blocks: list[dict],
    ) -> list[dict]:
        anchors = cls.home_anchor_ids(blocks)
        result: list[dict] = []
        for item in navigation:
            href = str(item.get("href") or "").strip()
            if not href or href == "#":
                continue
            if href.startswith("#") and href[1:] not in anchors:
                continue
            result.append(item)
        return result

    @classmethod
    def apply_public_navigation(
        cls,
        session: Session,
        site_id: UUID,
        site: dict,
    ) -> tuple[list[dict], set[str]]:
        home = cls.get_page(session, site_id, "home", published_only=True)
        blocks = cls.public_blocks(home) if home is not None else []
        anchors = cls.home_anchor_ids(blocks)
        site["settings"]["navigation"] = cls.filter_navigation(
            site["settings"].get("navigation", []),
            blocks,
        )
        return blocks, anchors

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


    @staticmethod
    def list_pages(session: Session, site_id: UUID) -> list[Page]:
        return (
            session.query(Page)
            .filter(Page.site_id == site_id)
            .order_by(Page.slug.asc())
            .all()
        )

    @classmethod
    def create_page(
        cls,
        session: Session,
        site_id: UUID,
        *,
        slug: str,
        title: str,
        seo_title: str = "",
        seo_description: str = "",
        is_published: bool = False,
    ) -> Page:
        slug = validate_slug(slug)
        title = title.strip()
        if not title or len(title) > 200:
            raise ValueError("Укажите название страницы длиной до 200 символов")
        if cls.get_page(session, site_id, slug) is not None:
            raise ValueError("На этом сайте уже есть страница с таким URL")

        page = Page(
            site_id=site_id,
            slug=slug,
            title=title,
            seo_title=seo_title.strip()[:255] or None,
            seo_description=seo_description.strip()[:1000] or None,
            is_published=is_published,
        )
        session.add(page)
        session.commit()
        session.refresh(page)
        return page

    @classmethod
    def update_page(
        cls,
        session: Session,
        page: Page,
        *,
        slug: str,
        title: str,
        seo_title: str,
        seo_description: str,
        is_published: bool,
    ) -> Page:
        slug = validate_slug(slug)
        title = title.strip()
        if not title or len(title) > 200:
            raise ValueError("Укажите название страницы длиной до 200 символов")

        duplicate = (
            session.query(Page)
            .filter(
                Page.site_id == page.site_id,
                Page.slug == slug,
                Page.id != page.id,
            )
            .first()
        )
        if duplicate is not None:
            raise ValueError("На этом сайте уже есть страница с таким URL")
        if page.slug == "home" and slug != "home":
            raise ValueError("Системную главную страницу нельзя переименовать")

        page.slug = slug
        page.title = title
        page.seo_title = seo_title.strip()[:255] or None
        page.seo_description = seo_description.strip()[:1000] or None
        page.is_published = is_published
        session.add(page)
        session.commit()
        session.refresh(page)
        return page

    @staticmethod
    def get_by_id(session: Session, page_id: UUID) -> Page | None:
        return session.query(Page).filter(Page.id == page_id).first()

    @staticmethod
    def get_block(session: Session, page_id: UUID, block_id: UUID) -> PageBlock | None:
        return (
            session.query(PageBlock)
            .filter(PageBlock.id == block_id, PageBlock.page_id == page_id)
            .first()
        )

    @classmethod
    def add_block(
        cls,
        session: Session,
        page: Page,
        *,
        block_type: str,
        settings: dict,
        is_enabled: bool = True,
    ) -> PageBlock:
        if block_type not in GENERIC_BLOCK_TYPES:
            raise ValueError("Неизвестный тип блока")

        max_position = max((item.position for item in page.blocks), default=0)
        block = PageBlock(
            page_id=page.id,
            block_type=block_type,
            position=max_position + 100,
            settings=copy.deepcopy(settings),
            is_enabled=is_enabled,
        )
        session.add(block)
        session.commit()
        session.refresh(block)
        return block

    @classmethod
    def update_block(
        cls,
        session: Session,
        block: PageBlock,
        *,
        position: int,
        settings: dict,
        is_enabled: bool,
    ) -> PageBlock:
        if block.block_type not in GENERIC_BLOCK_TYPES:
            raise ValueError("Этот системный блок редактируется в настройках сайта")
        block.position = max(0, min(int(position), 9999))
        block.settings = copy.deepcopy(settings)
        block.is_enabled = is_enabled
        session.add(block)
        session.commit()
        session.refresh(block)
        return block

    @staticmethod
    def delete_block(session: Session, block: PageBlock) -> None:
        if block.block_type not in GENERIC_BLOCK_TYPES:
            raise ValueError("Системный блок нельзя удалить здесь")
        session.delete(block)
        session.commit()

    @staticmethod
    def delete_page(session: Session, page: Page) -> None:
        if page.slug == "home":
            raise ValueError("Главную страницу удалить нельзя")
        session.delete(page)
        session.commit()
