from __future__ import annotations

import copy
import re
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy.orm import Session

from models.site import Site
from settings import config


DEFAULT_SITE_KEY = "jsinteractive"
SITE_KEY_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

DEFAULT_SETTINGS: dict[str, Any] = {
    "brand": {
        "name": "+УЛЬТРА",
        "subtitle": "на базе jsinteractive",
    },
    "seo": {
        "site_name": "JSInteractive",
        "title": "JSInteractive | +УЛЬТРА",
        "description": (
            "+УЛЬТРА — независимая инженерная мини-студия: backend, realtime, "
            "аудит и архитектура web-систем."
        ),
        "image_url": "",
        "locale": "ru_RU",
        "robots_index": True,
        "yandex_verification": "725d05a47d08b13d",
    },
    "contact": {
        "email": "cyrox007@gmail.com",
        "github_url": "https://github.com/cyrox007",
    },
    "navigation": [
        {"label": "Системы", "href": "#systems"},
        {"label": "Подход", "href": "#philosophy"},
        {"label": "О студии", "href": "#about"},
    ],
    "footer": {
        "description": "Инженерная мини-студия на базе jsinteractive.",
        "location": "Удалённая работа",
        "note": "backend systems · realtime infrastructure · аудит систем",
    },
    "api": {
        "allowed_origins": [],
    },
}


def _deep_merge(defaults: dict, custom: dict | None) -> dict:
    result = copy.deepcopy(defaults)
    for key, value in (custom or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


class SiteService:
    @staticmethod
    def validate_key(value: str) -> str:
        key = value.strip().lower()
        if not SITE_KEY_RE.fullmatch(key):
            raise ValueError("Ключ сайта должен содержать только a-z, 0-9 и одиночные дефисы")
        return key

    @staticmethod
    def validate_base_url(value: str | None) -> str | None:
        raw = (value or "").strip().rstrip("/")
        if not raw:
            return None
        parsed = urlparse(raw)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise ValueError("Базовый URL должен быть origin-адресом без пути, query и fragment")
        return raw

    @classmethod
    def get_default(cls, session: Session) -> Site:
        site = (
            session.query(Site)
            .filter(Site.is_active.is_(True), Site.is_default.is_(True))
            .order_by(Site.created_at.asc())
            .first()
        )
        if site is not None:
            return site

        site = (
            session.query(Site)
            .filter(Site.is_active.is_(True))
            .order_by(Site.created_at.asc())
            .first()
        )
        if site is None:
            raise RuntimeError("Не настроен ни один активный сайт")
        return site

    @staticmethod
    def get_by_id(session: Session, site_id: UUID) -> Site | None:
        return session.query(Site).filter(Site.id == site_id).first()

    @staticmethod
    def get_by_key(session: Session, key: str, *, active_only: bool = True) -> Site | None:
        query = session.query(Site).filter(Site.key == key)
        if active_only:
            query = query.filter(Site.is_active.is_(True))
        return query.first()

    @staticmethod
    def list_sites(session: Session) -> list[Site]:
        return session.query(Site).order_by(Site.is_default.desc(), Site.name.asc()).all()

    @classmethod
    def create(
        cls,
        session: Session,
        *,
        key: str,
        name: str,
        base_url: str | None,
        theme_key: str = "ultra",
    ) -> Site:
        key = cls.validate_key(key)
        name = name.strip()
        if not name or len(name) > 160:
            raise ValueError("Укажите название сайта длиной до 160 символов")
        if cls.get_by_key(session, key, active_only=False) is not None:
            raise ValueError("Сайт с таким ключом уже существует")

        site = Site(
            key=key,
            name=name,
            base_url=cls.validate_base_url(base_url),
            theme_key=(theme_key.strip() or "ultra")[:80],
            settings={},
            is_active=True,
            is_default=False,
        )
        session.add(site)
        session.flush()

        # Новая витрина сразу получает управляемую главную страницу.
        from services.page import PageService

        PageService.create_default_home(session, site.id)
        session.commit()
        session.refresh(site)
        return site

    @classmethod
    def update(
        cls,
        session: Session,
        site: Site,
        *,
        name: str,
        base_url: str | None,
        theme_key: str,
        settings: dict,
        is_active: bool,
        is_default: bool,
        commit: bool = True,
    ) -> Site:
        name = name.strip()
        if not name or len(name) > 160:
            raise ValueError("Укажите название сайта длиной до 160 символов")

        if is_default:
            session.query(Site).filter(Site.id != site.id).update(
                {Site.is_default: False},
                synchronize_session=False,
            )
            is_active = True

        site.name = name
        site.base_url = cls.validate_base_url(base_url)
        site.theme_key = (theme_key.strip() or "ultra")[:80]
        site.settings = settings
        site.is_active = is_active
        site.is_default = is_default
        session.add(site)
        session.flush()
        if commit:
            session.commit()
        session.refresh(site)
        return site

    @staticmethod
    def settings(site: Site) -> dict:
        return _deep_merge(DEFAULT_SETTINGS, site.settings)

    @classmethod
    def public_config(cls, site: Site) -> dict:
        settings = cls.settings(site)
        return {
            "id": str(site.id),
            "key": site.key,
            "name": site.name,
            "base_url": site.base_url or (config.SITE_BASE_URL if site.is_default else ""),
            "theme": site.theme_key,
            "settings": settings,
        }
