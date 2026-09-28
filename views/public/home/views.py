from flask import render_template
from flask.views import MethodView

from components.auth.decorator import with_db_session
from services.publication import PublicationService
from services.site import SiteService


class MainPage(MethodView):
    decorators = [with_db_session]

    def get(self, db_session):
        site_model = SiteService.get_default(db_session)
        site = SiteService.public_config(site_model)
        articles = PublicationService.get_publications(
            db_session,
            site_id=site_model.id,
            is_published=True,
            order_by="published_at",
            order_direction="desc",
            limit=5,
        )
        return render_template(
            "public/home/index.html",
            site=site,
            articles=articles,
        )
