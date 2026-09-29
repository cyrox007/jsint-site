from datetime import timezone\n\nfrom flask import make_response, render_template
from flask.views import MethodView

from components.auth.decorator import with_db_session
from services.page import PageService
from services.publication_channel import PublicationChannelService
from services.site import SiteService


class MainPage(MethodView):
    decorators = [with_db_session]

    def get(self, db_session):
        site_model = SiteService.get_default(db_session)
        site = SiteService.public_config(site_model)
        page = PageService.get_page(
            db_session,
            site_model.id,
            "home",
            published_only=True,
        )
        home_blocks, home_anchor_ids = PageService.apply_public_navigation(
            db_session,
            site_model.id,
            site,
        )

        articles = PublicationChannelService.list_public(
            db_session,
            site_id=site_model.id,
            limit=5,
        )

        seo_defaults = site["settings"]["seo"]
        seo_title = page.seo_title if page is not None and page.seo_title else seo_defaults["title"]
        seo_description = (
            page.seo_description
            if page is not None and page.seo_description
            else seo_defaults["description"]
        )
        canonical_url = f"{site['base_url']}/" if site["base_url"] else None

        response = make_response(
            render_template(
                "public/home/index.html",
                site=site,
                articles=articles,
                home_page=page,
                home_blocks=home_blocks,
                home_anchor_ids=home_anchor_ids,
                seo_title=seo_title,
                seo_description=seo_description,
                canonical_url=canonical_url,
            )
        )

        modified_candidates = [
            site_model.updated_at,
            page.updated_at if page is not None else None,
            *[
                article.updated_at or article.published_at or article.created_at
                for article in articles
            ],
        ]
        modified = [value for value in modified_candidates if value is not None]
        if modified:
            normalized = [
                value.replace(tzinfo=timezone.utc)
                if value.tzinfo is None
                else value.astimezone(timezone.utc)
                for value in modified
            ]
            response.last_modified = max(normalized)
        return response
