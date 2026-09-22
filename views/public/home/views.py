from flask import render_template
from flask.views import MethodView

from components.auth.decorator import with_db_session

from services.publication import PublicationService
from settings import config


class MainPage(MethodView):
    decorators = [with_db_session]
    def get(self, db_session):
        """Главная страница"""
        articles = PublicationService.get_publications(db_session, is_published=True, limit=5)
        
        context = {
            "articles": articles,
            "canonical_url": f"{config.SITE_CANONICAL_URL}/",
            "og_type": "website",
        }
        return render_template('public/home/index.html', **context)