from flask import render_template
from flask.views import MethodView

from components.auth.decorator import login_required, with_db_session
from database import Database
from models.articles import Article


class MainPage(MethodView):
    decorators = [with_db_session]
    def get(self, db_session):
        """Главная страница"""
        articles = Article.get_posts(db_session)
        
        context = {
            'articles': articles
        }
        return render_template('home/index.html', **context)