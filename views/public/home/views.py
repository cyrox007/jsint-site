from flask import abort, render_template
from flask.views import MethodView

from components.auth.decorator import with_db_session
from services.publication import PublicationService
from services.sites import SiteService
from settings import config


class MainPage(MethodView):
    decorators = [with_db_session]

    def get(self, db_session):
        site = SiteService.get_current(db_session, config.PUBLIC_SITE_SLUG)
        if site is None:
            abort(503)

        articles = PublicationService.get_publications(db_session, is_published=True, limit=5)
        return render_template(
            "public/home/index.html",
            articles=articles,
            site=site,
            seo_title=site.seo_title,
            seo_description=site.seo_description,
            canonical_url=f"{site.base_url}/",
        )
