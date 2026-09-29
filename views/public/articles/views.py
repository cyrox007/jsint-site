import math
import re
from datetime import timezone

from flask import abort, make_response, render_template
from flask.views import MethodView

from components.auth.decorator import with_db_session
from models.categories import Category
from services.page import PageService
from services.publication_channel import PublicationChannelService
from services.site import SiteService


class ArticleDetailView(MethodView):
    @with_db_session
    def get(self, db_session, categories_slug: str, publication_slug: str):
        site_model = SiteService.get_default(db_session)
        site = SiteService.public_config(site_model)
        _, home_anchor_ids = PageService.apply_public_navigation(
            db_session,
            site_model.id,
            site,
        )
        category = Category.get_by_slug(db_session, categories_slug, site_model.id)
        if category is None:
            abort(404)

        publication = PublicationChannelService.get_public_by_slug(
            db_session,
            site_id=site_model.id,
            slug=publication_slug,
            category_id=category.id,
        )
        if publication is None:
            abort(404)

        extra = publication.extra_data or {}
        plain_text = re.sub(r"<[^>]+>", " ", publication.content or "")
        plain_text = re.sub(r"\s+", " ", plain_text).strip()
        site_name = site["settings"]["seo"].get("site_name") or site["name"]
        seo_title = (
            extra.get("seo_title")
            or f"{publication.title} | {site_name}"
        ).strip()
        seo_description = (extra.get("seo_description") or plain_text[:180]).strip()
        word_count = len(re.findall(r"\b\w+\b", plain_text, flags=re.UNICODE))
        reading_minutes = max(1, math.ceil(word_count / 180))
        canonical_url = (
            f"{site['base_url']}/category/{category.slug}/article/{publication.slug}"
            if site["base_url"]
            else None
        )

        published_at = publication.published_at or publication.created_at
        modified_at = publication.updated_at or published_at

        def iso_datetime(value):
            if value is None:
                return None
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc).isoformat()

        structured_data_items = [
            {
                "@context": "https://schema.org",
                "@type": "Article",
                "headline": publication.title,
                "description": seo_description,
                "datePublished": iso_datetime(published_at),
                "dateModified": iso_datetime(modified_at),
                "mainEntityOfPage": {
                    "@type": "WebPage",
                    "@id": canonical_url,
                },
                "publisher": {
                    "@type": "Organization",
                    "name": site_name,
                    "url": site["base_url"],
                },
            },
            {
                "@context": "https://schema.org",
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": 1,
                        "name": site_name,
                        "item": f"{site['base_url']}/",
                    },
                    {
                        "@type": "ListItem",
                        "position": 2,
                        "name": publication.title,
                        "item": canonical_url,
                    },
                ],
            },
        ]

        response = make_response(
            render_template(
                "public/articles/detail.html",
                site=site,
                publication=publication,
                seo_title=seo_title,
                seo_description=seo_description,
                canonical_url=canonical_url,
                og_type="article",
                article_excerpt=seo_description,
                reading_minutes=reading_minutes,
                home_has_systems="systems" in home_anchor_ids,
                structured_data_items=structured_data_items,
            )
        )
        if modified_at is not None:
            if modified_at.tzinfo is None:
                modified_at = modified_at.replace(tzinfo=timezone.utc)
            response.last_modified = modified_at.astimezone(timezone.utc)
        return response
