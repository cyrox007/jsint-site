from __future__ import annotations

from datetime import timezone
from urllib.parse import urljoin

from flask import Response
from sqlalchemy.orm import Session

from components.auth.decorator import with_db_session
from models.publication import Publication
from services.site import SiteService
from settings import config


@with_db_session
def robots_txt(db_session: Session) -> Response:
    site = SiteService.public_config(SiteService.get_default(db_session))
    base_url = site["base_url"] or config.SITE_BASE_URL
    body = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            f"Disallow: {config.ADMIN_ROUTE_PREFIX}/",
            f"Disallow: {config.NOTES_UPDATE_API_PREFIX}/",
            "Disallow: /healthz",
            f"Sitemap: {base_url}/sitemap.xml",
            "",
        ]
    )
    return Response(body, mimetype="text/plain")


@with_db_session
def sitemap_xml(db_session: Session) -> Response:
    site_model = SiteService.get_default(db_session)
    site = SiteService.public_config(site_model)
    base_url = site["base_url"] or config.SITE_BASE_URL
    publications = (
        db_session.query(Publication)
        .filter(
            Publication.site_id == site_model.id,
            Publication.is_published.is_(True),
            Publication.category_id.is_not(None),
        )
        .order_by(Publication.updated_at.desc())
        .all()
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
        parts.append(f"    <loc>{location}</loc>")
        if lastmod:
            parts.append(f"    <lastmod>{lastmod}</lastmod>")
        parts.append("  </url>")
    parts.append("</urlset>")
    parts.append("")

    response = Response("\n".join(parts), mimetype="application/xml")
    response.headers["Cache-Control"] = "public, max-age=300"
    return response
