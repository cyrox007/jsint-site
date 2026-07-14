from flask import render_template
from flask.views import MethodView

from components.auth.decorator import with_db_session

from services.articles import ArticleService


class MainPage(MethodView):
    decorators = [with_db_session]
    def get(self, db_session):
        """Главная страница"""
        articles = ArticleService.get_latest_posts(db_session, limit=5)
        
        context = {
            'articles': articles
        }
        return render_template('home/index.html', **context)