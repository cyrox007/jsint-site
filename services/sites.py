from __future__ import annotations

from urllib.parse import urlparse

from sqlalchemy.orm import Session

from models.sites import Site
from utils.validation import validate_slug


class SiteService:
    @staticmethod
    def list_sites(session: Session) -> list[Site]:
        return session.query(Site).order_by(Site.is_default.desc(), Site.name.asc()).all()

    @staticmethod
    def get_by_slug(session: Session, slug: str) -> Site | None:
        return session.query(Site).filter(Site.slug == slug, Site.is_active.is_(True)).first()

    @classmethod
    def get_current(cls, session: Session, preferred_slug: str = "") -> Site | None:
        if preferred_slug:
            site = cls.get_by_slug(session, preferred_slug)
            if site is not None:
                return site
        return session.query(Site).filter(Site.is_active.is_(True)).order_by(Site.is_default.desc(), Site.created_at.asc()).first()

    @classmethod
    def create(cls, session: Session, data: dict) -> Site:
        slug = validate_slug(str(data.get("slug") or ""))
        if session.query(Site).filter(Site.slug == slug).first() is not None:
            raise ValueError("Сайт с таким идентификатором уже существует")
        site = Site(slug=slug, name=str(data.get("name") or slug).strip())
        cls._apply(site, data)
        session.add(site)
        cls._save(session, site)
        return site

    @classmethod
    def update(cls, session: Session, site: Site, data: dict) -> Site:
        slug = validate_slug(str(data.get("slug") or ""))
        duplicate = session.query(Site).filter(Site.slug == slug, Site.id != site.id).first()
        if duplicate is not None:
            raise ValueError("Сайт с таким идентификатором уже существует")
        site.slug = slug
        cls._apply(site, data)
        cls._save(session, site)
        return site

    @staticmethod
    def _apply(site: Site, data: dict) -> None:
        fields = (
            "name", "brand_subtitle", "base_url", "contact_email", "github_url",
            "seo_title", "seo_description", "hero_badge", "hero_title", "hero_accent",
            "hero_description", "philosophy_title", "philosophy_subtitle", "philosophy_body",
            "about_title", "about_primary_title", "about_primary_body",
            "about_secondary_title", "about_secondary_body", "footer_note",
        )
        for field in fields:
            if field in data:
                setattr(site, field, str(data.get(field) or "").strip())

        SiteService._validate_url(site.base_url, "Базовый URL")
        SiteService._validate_url(site.github_url, "Ссылка GitHub", allow_empty=True)
        site.is_active = bool(data.get("is_active", False))
        site.is_default = bool(data.get("is_default", False))

    @staticmethod
    def _validate_url(value: str, label: str, *, allow_empty: bool = False) -> None:
        if not value and allow_empty:
            return
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError(f"{label}: укажите абсолютный http/https URL")

    @staticmethod
    def _save(session: Session, site: Site) -> None:
        if site.is_default:
            session.query(Site).filter(Site.id != site.id, Site.is_default.is_(True)).update({Site.is_default: False}, synchronize_session=False)
        session.commit()
        session.refresh(site)
