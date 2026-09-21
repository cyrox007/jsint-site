from flask import abort, render_template
from flask.views import MethodView

from components.auth.decorator import with_db_session
from models.categories import Category
from models.publication import Publication
from schemas.publication import PublicationOut


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

        return render_template(
            "public/articles/detail.html",
            publication=PublicationOut.model_validate(publication),
        )
