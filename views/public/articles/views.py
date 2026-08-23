from flask.views import MethodView
from flask import render_template, abort
from uuid import UUID
from components.auth.decorator import with_db_session
from models.categories import Category
from services.publication import PublicationService


class ArticleDetailView(MethodView):
    @with_db_session
    def get(self, db_session, categories_slug, publication_slug: str):
        """
        Публичная страница статьи по slug.
        Можно также использовать article_id, но slug удобнее для SEO.
        """
        # 1. Находим категорию по slug
        category = db_session.query(Category).filter(Category.slug == categories_slug).first()
        if not category:
            abort(404)
            
        # Получаем публикацию по slug через сервис (или напрямую через модель)
        from models.publication import Publication
        publication = db_session.query(Publication).filter(
            Publication.slug == publication_slug,
            Publication.is_published == True
        ).first()

        if not publication:
            abort(404)

        # Преобразуем в Pydantic-схему для удобства в шаблоне
        from schemas.publication import PublicationOut
        pub_schema = PublicationOut.model_validate(publication)

        return render_template('public/articles/detail.html', publication=pub_schema)