from __future__ import annotations

from uuid import UUID

from flask import session
from sqlalchemy.orm import Session

from services.site import SiteService


ADMIN_SITE_SESSION_KEY = "admin_site_id"


def _site_from_value(db_session: Session, raw: str | UUID | None):
    if raw is None:
        return None

    value = str(raw).strip()
    if not value:
        return None

    try:
        site_id = UUID(value)
    except (TypeError, ValueError):
        return None

    return SiteService.get_by_id(db_session, site_id)


def resolve_admin_site(
    db_session: Session,
    raw: str | UUID | None = None,
    *,
    fallback: bool = True,
):
    """Возвращает выбранный в админке сайт и сохраняет его как рабочий контекст."""
    explicit = _site_from_value(db_session, raw)
    if explicit is not None:
        session[ADMIN_SITE_SESSION_KEY] = str(explicit.id)
        return explicit

    stored = _site_from_value(db_session, session.get(ADMIN_SITE_SESSION_KEY))
    if stored is not None:
        return stored

    if not fallback:
        return None

    site = SiteService.get_default(db_session)
    session[ADMIN_SITE_SESSION_KEY] = str(site.id)
    return site
