from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urljoin
from xml.sax.saxutils import escape

from flask import Response
from sqlalchemy.orm import Session

from components.auth.decorator import with_db_session
from services.page import PageService
from services.publication_channel import PublicationChannelService
from services.site import SiteService
from settings import config


_SITEMAP_PAGE_SIZE = 100
_SITEMAP_MAX_URLS = 50_000
_SITEMAP_STATIC_URLS = 6


def _utc_date(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).date().isoformat()


def _latest_datetime(values: list[datetime | None]) -> datetime | None:
    normalized: list[datetime] = []
    for value in values:
        if value is None:
            continue
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        normalized.append(value.astimezone(timezone.utc))
    return max(normalized) if normalized else None


def _all_publications(db_session: Session, site_id):
    offset = 0
    result = []
    while len(result) < _SITEMAP_MAX_URLS - _SITEMAP_STATIC_URLS:
        remaining = _SITEMAP_MAX_URLS - _SITEMAP_STATIC_URLS - len(result)
        batch = PublicationChannelService.list_public(
            db_session,
            site_id=site_id,
            limit=min(_SITEMAP_PAGE_SIZE, remaining),
            offset=offset,
        )
        if not batch:
            break
        result.extend(batch)
        if len(batch) < _SITEMAP_PAGE_SIZE:
            break
        offset += len(batch)
    return result


@with_db_session
def robots_txt(db_session: Session) -> Response:
    site_model = SiteService.get_default(db_session)
    site = SiteService.public_config(site_model)
    base_url = site["base_url"] or config.SITE_BASE_URL
    allow_indexing = bool(site["settings"]["seo"].get("robots_index", True))

    if allow_indexing:
        rules = [
            "User-agent: *",
            "Allow: /",
            "Disallow: /api/",
            "Disallow: /healthz",
            (
                "Clean-param: "
                "utm_source&utm_medium&utm_campaign&utm_content&utm_term&utm_referrer"
                "&ysclid&yrclid&gclid&fbclid"
            ),
            f"Sitemap: {base_url}/sitemap.xml",
            "",
        ]
    else:
        rules = [
            "User-agent: *",
            "Disallow: /",
            "",
        ]

    response = Response("\n".join(rules), mimetype="text/plain")
    response.headers["Cache-Control"] = "public, max-age=300"
    return response


@with_db_session
def sitemap_xml(db_session: Session) -> Response:
    site_model = SiteService.get_default(db_session)
    site = SiteService.public_config(site_model)
    base_url = site["base_url"] or config.SITE_BASE_URL
    publications = _all_publications(db_session, site_model.id)
    home_page = PageService.get_page(
        db_session,
        site_model.id,
        "home",
        published_only=True,
    )

    home_modified = _latest_datetime(
        [
            site_model.updated_at,
            home_page.updated_at if home_page is not None else None,
            *[
                publication.updated_at
                or publication.published_at
                or publication.created_at
                for publication in publications
            ],
        ]
    )

    urls: list[tuple[str, str | None]] = [
        (f"{base_url}/", _utc_date(home_modified)),
        (urljoin(f"{base_url}/", "demo/vanga"), None),
        (urljoin(f"{base_url}/", "workspace-organizer"), None),
        (urljoin(f"{base_url}/", "projects/vanga"), None),
        (urljoin(f"{base_url}/", "projects/the-game"), None),
        (urljoin(f"{base_url}/", "projects/churchcms"), None),
    ]
    for publication in publications:
        if publication.category is None:
            continue
        path = f"/category/{publication.category.slug}/article/{publication.slug}"
        updated_at = (
            publication.updated_at
            or publication.published_at
            or publication.created_at
        )
        urls.append(
            (
                urljoin(f"{base_url}/", path.lstrip("/")),
                _utc_date(updated_at),
            )
        )

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for location, lastmod in urls:
        parts.append("  <url>")
        parts.append(f"    <loc>{escape(location)}</loc>")
        if lastmod:
            parts.append(f"    <lastmod>{lastmod}</lastmod>")
        parts.append("  </url>")
    parts.append("</urlset>")
    parts.append("")

    response = Response("\n".join(parts), mimetype="application/xml")
    response.headers["Cache-Control"] = "public, max-age=300"
    return response


def indexnow_key() -> Response:
    if not config.YANDEX_INDEXNOW_ENABLED or not config.YANDEX_INDEXNOW_KEY:
        return Response("Not found\n", status=404, mimetype="text/plain")

    response = Response(
        f"{config.YANDEX_INDEXNOW_KEY}\n",
        mimetype="text/plain",
    )
    response.headers["Cache-Control"] = "public, max-age=86400"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response
