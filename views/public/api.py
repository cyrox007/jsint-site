from __future__ import annotations

import re

from flask import Flask, abort, jsonify, request, url_for
from sqlalchemy.orm import Session

from components.auth.decorator import with_db_session
from components.security.html import sanitize_rich_text
from models.categories import Category
from services.media import MediaService
from services.page import PageService
from services.publication_channel import PublicationChannelService
from services.publication_profile import public_profile
from services.site import SiteService


PUBLIC_API_CONTRACT = "jsint-public-v1"


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
    response.headers["X-JSInt-Public-API"] = PUBLIC_API_CONTRACT
    response.add_etag()

    origin = request.headers.get("Origin", "").rstrip("/")
    allowed_origins = SiteService.settings(site).get("api", {}).get("allowed_origins", [])
    if origin and origin in allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET"
        response.headers["Access-Control-Expose-Headers"] = "ETag, X-JSInt-Public-API"
        response.headers["Vary"] = "Origin"

    response.make_conditional(request)
    return response


def _site_payload(site) -> dict:
    """Публичная идентичность витрины без навязывания её UI/SEO-контракта."""
    return {
        "id": str(site.id),
        "key": site.key,
        "name": site.name,
        "base_url": site.base_url,
    }


def _category_payload(category: Category) -> dict:
    return {
        "id": str(category.id),
        "site_id": str(category.site_id),
        "parent_id": str(category.parent_id) if category.parent_id else None,
        "title": category.title,
        "slug": category.slug,
        "description": category.description,
    }


def _media_payload(asset) -> dict:
    filename = MediaService.public_filename(asset)
    return {
        "id": str(asset.id),
        "name": asset.original_name,
        "mime_type": asset.mime_type,
        "size_bytes": asset.size_bytes,
        "alt_text": asset.alt_text,
        "path": url_for(
            "public.media.file",
            asset_id=asset.id,
            filename=filename,
        ),
        "url": url_for(
            "public.media.file",
            asset_id=asset.id,
            filename=filename,
            _external=True,
        ),
    }


def _publication_payload(
    publication,
    *,
    include_content: bool,
    site_key: str,
) -> dict:
    extra = publication.extra_data or {}
    plain_text = re.sub(r"<[^>]+>", " ", publication.content or "")
    plain_text = re.sub(r"\s+", " ", plain_text).strip()
    payload = {
        "id": str(publication.id),
        "title": publication.title,
        "slug": publication.slug,
        "source_type": publication.source_type,
        "excerpt": plain_text[:240],
        "data": public_profile(extra, site_key),
        "category": _category_payload(publication.category) if publication.category else None,
        "published_at": publication.published_at.isoformat() if publication.published_at else None,
        "created_at": publication.created_at.isoformat() if publication.created_at else None,
        "updated_at": publication.updated_at.isoformat() if publication.updated_at else None,
    }
    if include_content:
        payload["content"] = sanitize_rich_text(publication.content)
    return payload


@with_db_session
def site_config(db_session: Session, site_key: str):
    site = _site_or_404(db_session, site_key)
    return _api_response(site, {"site": _site_payload(site)})


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
def site_media(db_session: Session, site_key: str):
    site = _site_or_404(db_session, site_key)
    assets = [
        asset
        for asset in MediaService.list_for_site(db_session, site.id)
        if asset.is_public
    ]
    return _api_response(
        site,
        {
            "site": {"key": site.key, "name": site.name},
            "items": [_media_payload(asset) for asset in assets],
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

    category_id = None
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
        category_id = category.id

    source_type = request.args.get("type", "").strip() or None
    try:
        limit = min(max(int(request.args.get("limit", "20")), 1), 100)
        offset = max(int(request.args.get("offset", "0")), 0)
    except ValueError:
        abort(400)

    publications = PublicationChannelService.list_public(
        db_session,
        site_id=site.id,
        category_id=category_id,
        source_type=source_type,
        limit=limit,
        offset=offset,
    )
    total = PublicationChannelService.count_public(
        db_session,
        site_id=site.id,
        category_id=category_id,
        source_type=source_type,
    )
    return _api_response(
        site,
        {
            "site": {"key": site.key, "name": site.name},
            "items": [_publication_payload(item, include_content=False, site_key=site.key) for item in publications],
            "pagination": {"limit": limit, "offset": offset, "total": total},
        },
    )

@with_db_session
def site_publication_detail(db_session: Session, site_key: str, publication_slug: str):
    site = _site_or_404(db_session, site_key)
    publication = PublicationChannelService.get_public_by_slug(
        db_session,
        site_id=site.id,
        slug=publication_slug,
    )
    if publication is None:
        abort(404)
    return _api_response(
        site,
        {
            "site": {"key": site.key, "name": site.name},
            "item": _publication_payload(publication, include_content=True, site_key=site.key),
        },
    )

@with_db_session
def site_bootstrap(db_session: Session, site_key: str):
    """Минимальный стартовый снимок для внешнего frontend без собственного backend."""
    site = _site_or_404(db_session, site_key)
    try:
        limit = min(max(int(request.args.get("limit", "12")), 1), 24)
    except ValueError:
        abort(400)

    categories = (
        db_session.query(Category)
        .filter(Category.site_id == site.id)
        .order_by(Category.title.asc())
        .all()
    )
    publications = PublicationChannelService.list_public(
        db_session,
        site_id=site.id,
        limit=limit,
        offset=0,
    )

    return _api_response(
        site,
        {
            "contract": PUBLIC_API_CONTRACT,
            "site": _site_payload(site),
            "categories": [_category_payload(item) for item in categories],
            "latest_publications": [
                _publication_payload(item, include_content=False)
                for item in publications
            ],
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
        "/api/public/v1/sites/<string:site_key>/bootstrap",
        endpoint="public.api.bootstrap",
        view_func=site_bootstrap,
        methods=["GET"],
    )
    app.add_url_rule(
        "/api/public/v1/sites/<string:site_key>/pages/<string:page_slug>",
        endpoint="public.api.page",
        view_func=site_page,
        methods=["GET"],
    )
    app.add_url_rule(
        "/api/public/v1/sites/<string:site_key>/media",
        endpoint="public.api.media",
        view_func=site_media,
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
