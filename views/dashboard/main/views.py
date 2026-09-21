from flask import render_template
from flask.views import MethodView
from sqlalchemy.orm import Session

from cache.redis import redis_client
from components.auth.decorator import login_required, with_db_session
from models.categories import Category
from models.publication import Publication
from version import application_version


class DashboardMain(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session):
        total_publications = db_session.query(Publication).count()
        published_count = (
            db_session.query(Publication)
            .filter(Publication.is_published.is_(True))
            .count()
        )
        category_count = db_session.query(Category).count()

        return render_template(
            "dashboard/main/index.html",
            application_version=application_version(),
            database_ok=True,
            redis_ok=redis_client.ping(),
            total_publications=total_publications,
            published_count=published_count,
            draft_count=total_publications - published_count,
            category_count=category_count,
        )
