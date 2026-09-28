import re

from flask import abort, render_template
from flask.views import MethodView

from components.auth.decorator import with_db_session
from models.categories import Category
from models.publication import Publication
from schemas.publication import PublicationOut
from services.sites import SiteService
from settings import config


class ArticleDetailView(MethodView):
    @with_db_session
    def get(self, db_session, categories_slug: str, publication_slug: str):
        site = SiteService.get_current(db_session, config.PUBLIC_SITE_SLUG)
        if site is None:
            abort(503)

        category = db_session.query(Category).filter(Category.slug == categories_slug).first()
        if category is None:
            abort(404)

        publication = (
            db_session.query(Publication)
            .filter(
                Publication.slug == publication_slug,
                Publication.category_id == category.id,
                Publication.is_published.is_(True),
            )
            .first()
        )
        if publication is None:
            abort(404)

        publication_out = PublicationOut.model_validate(publication)
        extra = publication_out.extra_data or {}
        plain_text = re.sub(r"<[^>]+>", " ", publication_out.content or "")
        plain_text = re.sub(r"\s+", " ", plain_text).strip()
        seo_title = (extra.get("seo_title") or publication_out.title).strip()
        seo_description = (extra.get("seo_description") or plain_text[:180]).strip()
        canonical_url = f"{site.base_url}/category/{category.slug}/article/{publication_out.slug}"

        return render_template(
            "public/articles/detail.html",
            site=site,
            publication=publication_out,
            seo_title=seo_title,
            seo_description=seo_description,
            canonical_url=canonical_url,
            og_type="article",
        )
