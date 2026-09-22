from __future__ import annotations

from xml.sax.saxutils import escape

from flask import Response
from sqlalchemy.orm import selectinload

from components.auth.decorator import with_db_session
from models.publication import Publication
from settings import config


def _site_url(path: str = "") -> str:
    base = config.SITE_CANONICAL_URL.rstrip("/")
    if not path:
        return f"{base}/"
    return f"{base}/{path.lstrip('/')}"


def robots_txt() -> Response:
    lines = [
        "User-agent: *",
        "Allow: /",
        f"Disallow: {config.ADMIN_ROUTE_PREFIX}/",
        f"Disallow: {config.NOTES_UPDATE_API_PREFIX}/",
        "Disallow: /healthz",
        f"Sitemap: {_site_url('sitemap.xml')}",
        "",
    ]
    return Response("\n".join(lines), mimetype="text/plain")


@with_db_session
def sitemap_xml(db_session) -> Response:
    publications = (
        db_session.query(Publication)
        .options(selectinload(Publication.category))
        .filter(
            Publication.is_published.is_(True),
            Publication.category_id.is_not(None),
        )
        .order_by(Publication.updated_at.desc())
        .all()
    )

    urls = [
        "  <url>",
        f"    <loc>{escape(_site_url())}</loc>",
        "    <changefreq>weekly</changefreq>",
        "    <priority>1.0</priority>",
        "  </url>",
    ]

    for publication in publications:
        if publication.category is None:
            continue
        location = _site_url(
            f"category/{publication.category.slug}/article/{publication.slug}"
        )
        lastmod = (publication.updated_at or publication.published_at or publication.created_at).date().isoformat()
        urls.extend(
            [
                "  <url>",
                f"    <loc>{escape(location)}</loc>",
                f"    <lastmod>{lastmod}</lastmod>",
                "    <changefreq>monthly</changefreq>",
                "    <priority>0.7</priority>",
                "  </url>",
            ]
        )

    body = "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
            *urls,
            "</urlset>",
            "",
        ]
    )
    return Response(body, mimetype="application/xml")


def install(app) -> None:
    app.add_url_rule("/robots.txt", endpoint="robots_txt", view_func=robots_txt, methods=["GET"])
    app.add_url_rule("/sitemap.xml", endpoint="sitemap_xml", view_func=sitemap_xml, methods=["GET"])
