from __future__ import annotations

from datetime import timezone
from urllib.parse import urljoin
from xml.sax.saxutils import escape

from flask import Response
from sqlalchemy.orm import Session

from components.auth.decorator import with_db_session
from services.publication_channel import PublicationChannelService
from services.site import SiteService
from settings import config


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
            f"Disallow: {config.ADMIN_ROUTE_PREFIX}/",
            f"Disallow: {config.NOTES_UPDATE_API_PREFIX}/",
            "Disallow: /api/",
            "Disallow: /healthz",
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
    publications = PublicationChannelService.list_public(
        db_session,
        site_id=site_model.id,
        limit=100,
    )

    urls: list[tuple[str, str | None]] = [(f"{base_url}/", None)]
    for publication in publications:
        if publication.category is None:
            continue
        path = f"/category/{publication.category.slug}/article/{publication.slug}"
        updated_at = publication.updated_at or publication.published_at or publication.created_at
        lastmod = None
        if updated_at is not None:
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
            lastmod = updated_at.astimezone(timezone.utc).date().isoformat()
        urls.append((urljoin(f"{base_url}/", path.lstrip("/")), lastmod))

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
