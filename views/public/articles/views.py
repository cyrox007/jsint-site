from __future__ import annotations

import html
import re

from flask import abort, render_template
from flask.views import MethodView

from components.auth.decorator import with_db_session
from models.categories import Category
from models.publication import Publication
from schemas.publication import PublicationOut
from settings import config


def _plain_text_excerpt(value: str, limit: int = 160) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text

    shortened = text[: limit + 1].rsplit(" ", 1)[0].strip()
    if not shortened:
        shortened = text[:limit].strip()
    return f"{shortened.rstrip('.,;:')}…"


class ArticleDetailView(MethodView):
    @with_db_session
    def get(self, db_session, categories_slug: str, publication_slug: str):
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
        canonical_url = (
            f"{config.SITE_CANONICAL_URL}/category/"
            f"{category.slug}/article/{publication.slug}"
        )
        seo_description = _plain_text_excerpt(publication.content)
        if not seo_description:
            seo_description = f"{publication.title} — материал +УЛЬТРА."

        article_schema = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": publication.title,
            "description": seo_description,
            "mainEntityOfPage": canonical_url,
            "datePublished": (
                publication.published_at or publication.created_at
            ).isoformat(),
            "dateModified": publication.updated_at.isoformat(),
            "author": {
                "@type": "Organization",
                "name": "JSInteractive",
            },
            "publisher": {
                "@type": "Organization",
                "name": "JSInteractive",
            },
        }

        return render_template(
            "public/articles/detail.html",
            publication=publication_out,
            canonical_url=canonical_url,
            seo_description=seo_description,
            og_type="article",
            article_schema=article_schema,
        )
