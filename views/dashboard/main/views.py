from flask import render_template
from flask.views import MethodView
from sqlalchemy.orm import Session

from cache.redis import redis_client
from components.auth.decorator import login_required, with_db_session
from components.background.status import get_background_status
from models.categories import Category
from models.control_plane import LicenseRecord, ReleaseRecord
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
        license_count = db_session.query(LicenseRecord).count()
        active_license_count = db_session.query(LicenseRecord).filter(LicenseRecord.status == "active").count()
        release_count = db_session.query(ReleaseRecord).count()
        background = get_background_status()

        return render_template(
            "dashboard/main/index.html",
            application_version=application_version(),
            database_ok=True,
            redis_ok=redis_client.ping(),
            background=background,
            total_publications=total_publications,
            published_count=published_count,
            draft_count=total_publications - published_count,
            category_count=category_count,
            license_count=license_count,
            active_license_count=active_license_count,
            release_count=release_count,
        )
