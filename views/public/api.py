from __future__ import annotations

import re

from flask import Flask, abort, jsonify, request
from sqlalchemy.orm import Session

from components.auth.decorator import with_db_session
from models.categories import Category
from models.publication import Publication
from services.page import PageService
from services.site import SiteService


def _site_or_404(db_session: Session, site_key: str):
    site = SiteService.get_by_key(db_session, site_key)
    if site is None:
        abort(404)
    return site


def _api_response(site, payload, status: int = 200):
    response = jsonify(payload)
    response.status_code = status
    response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=300"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.add_etag()

    origin = request.headers.get("Origin", "").rstrip("/")
    allowed_origins = SiteService.settings(site).get("api", {}).get("allowed_origins", [])
    if origin and origin in allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET"
        response.headers["Vary"] = "Origin"

    response.make_conditional(request)
    return response


def _category_payload(category: Category) -> dict:
    return {
        "id": str(category.id),
        "site_id": str(category.site_id),
        "parent_id": str(category.parent_id) if category.parent_id else None,
        "title": category.title,
        "slug": category.slug,
        "description": category.description,
    }


def _publication_payload(publication: Publication, *, include_content: bool) -> dict:
    extra = publication.extra_data or {}
    plain_text = re.sub(r"<[^>]+>", " ", publication.content or "")
    plain_text = re.sub(r"\s+", " ", plain_text).strip()
    payload = {
        "id": str(publication.id),
        "site_id": str(publication.site_id),
        "title": publication.title,
        "slug": publication.slug,
        "source_type": publication.source_type,
        "excerpt": plain_text[:240],
        "extra_data": extra,
        "category": _category_payload(publication.category) if publication.category else None,
        "published_at": publication.published_at.isoformat() if publication.published_at else None,
        "created_at": publication.created_at.isoformat() if publication.created_at else None,
        "updated_at": publication.updated_at.isoformat() if publication.updated_at else None,
    }
    if include_content:
        payload["content"] = publication.content
    return payload


@with_db_session
def site_config(db_session: Session, site_key: str):
    site = _site_or_404(db_session, site_key)
    return _api_response(site, {"site": SiteService.public_config(site)})


@with_db_session
def site_page(db_session: Session, site_key: str, page_slug: str):
    site = _site_or_404(db_session, site_key)
    page = PageService.get_page(
        db_session,
        site.id,
        page_slug,
        published_only=True,
    )
    if page is None:
        abort(404)

    return _api_response(
        site,
        {
            "site": {"key": site.key, "name": site.name},
            "page": {
                "slug": page.slug,
                "title": page.title,
                "seo": {
                    "title": page.seo_title,
                    "description": page.seo_description,
                },
                "blocks": PageService.public_blocks(page),
                "updated_at": page.updated_at.isoformat() if page.updated_at else None,
            },
        },
    )


@with_db_session
def site_categories(db_session: Session, site_key: str):
    site = _site_or_404(db_session, site_key)
    categories = (
        db_session.query(Category)
        .filter(Category.site_id == site.id)
        .order_by(Category.title.asc())
        .all()
    )
    return _api_response(
        site,
        {
            "site": {"key": site.key, "name": site.name},
            "items": [_category_payload(item) for item in categories],
        },
    )


@with_db_session
def site_publications(db_session: Session, site_key: str):
    site = _site_or_404(db_session, site_key)
    query = (
        db_session.query(Publication)
        .filter(
            Publication.site_id == site.id,
            Publication.is_published.is_(True),
        )
        .order_by(Publication.published_at.desc(), Publication.created_at.desc())
    )

    category_slug = request.args.get("category", "").strip()
    if category_slug:
        category = Category.get_by_slug(db_session, category_slug, site.id)
        if category is None:
            return _api_response(
                site,
                {
                    "site": {"key": site.key},
                    "items": [],
                    "pagination": {"limit": 20, "offset": 0, "total": 0},
                },
            )
        query = query.filter(Publication.category_id == category.id)

    source_type = request.args.get("type", "").strip()
    if source_type:
        query = query.filter(Publication.source_type == source_type)

    try:
        limit = min(max(int(request.args.get("limit", "20")), 1), 100)
        offset = max(int(request.args.get("offset", "0")), 0)
    except ValueError:
        abort(400)

    total = query.order_by(None).count()
    publications = query.offset(offset).limit(limit).all()
    return _api_response(
        site,
        {
            "site": {"key": site.key, "name": site.name},
            "items": [_publication_payload(item, include_content=False) for item in publications],
            "pagination": {"limit": limit, "offset": offset, "total": total},
        },
    )


@with_db_session
def site_publication_detail(db_session: Session, site_key: str, publication_slug: str):
    site = _site_or_404(db_session, site_key)
    publication = (
        db_session.query(Publication)
        .filter(
            Publication.site_id == site.id,
            Publication.slug == publication_slug,
            Publication.is_published.is_(True),
        )
        .first()
    )
    if publication is None:
        abort(404)
    return _api_response(
        site,
        {
            "site": {"key": site.key, "name": site.name},
            "item": _publication_payload(publication, include_content=True),
        },
    )


def install(app: Flask) -> None:
    app.add_url_rule(
        "/api/public/v1/sites/<string:site_key>",
        endpoint="public.api.site",
        view_func=site_config,
        methods=["GET"],
    )
    app.add_url_rule(
        "/api/public/v1/sites/<string:site_key>/pages/<string:page_slug>",
        endpoint="public.api.page",
        view_func=site_page,
        methods=["GET"],
    )
    app.add_url_rule(
        "/api/public/v1/sites/<string:site_key>/categories",
        endpoint="public.api.categories",
        view_func=site_categories,
        methods=["GET"],
    )
    app.add_url_rule(
        "/api/public/v1/sites/<string:site_key>/publications",
        endpoint="public.api.publications",
        view_func=site_publications,
        methods=["GET"],
    )
    app.add_url_rule(
        "/api/public/v1/sites/<string:site_key>/publications/<string:publication_slug>",
        endpoint="public.api.publication",
        view_func=site_publication_detail,
        methods=["GET"],
    )
