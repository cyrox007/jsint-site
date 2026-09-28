import re

from flask import abort, render_template
from flask.views import MethodView

from components.auth.decorator import with_db_session
from models.categories import Category
from services.publication_channel import PublicationChannelService
from services.site import SiteService


class ArticleDetailView(MethodView):
    @with_db_session
    def get(self, db_session, categories_slug: str, publication_slug: str):
        site_model = SiteService.get_default(db_session)
        site = SiteService.public_config(site_model)
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
        seo_title = (extra.get("seo_title") or publication.title).strip()
        seo_description = (extra.get("seo_description") or plain_text[:180]).strip()
        canonical_url = (
            f"{site['base_url']}/category/{category.slug}/article/{publication.slug}"
            if site["base_url"]
            else None
        )

        return render_template(
            "public/articles/detail.html",
            site=site,
            publication=publication,
            seo_title=seo_title,
            seo_description=seo_description,
            canonical_url=canonical_url,
            og_type="article",
        )
