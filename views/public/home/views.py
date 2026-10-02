from datetime import timezone

from flask import make_response, render_template
from flask.views import MethodView

from components.auth.decorator import with_db_session
from services.page import PageService
from services.public_seo import (
    AUTHOR_DESCRIPTION,
    HERO_IMAGE_URL,
    author_entity,
    share_image_url,
)
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
        home_settings = PageService.block_settings(page)
        home_blocks_by_type = {
            block["type"]: block
            for block in home_blocks
            if block.get("type")
        }

        articles = PublicationChannelService.list_public(
            db_session,
            site_id=site_model.id,
            limit=5,
        )

        seo_title = (
            page.seo_title
            if page is not None and page.seo_title
            else "JSInteractive — full-stack разработка и self-hosted проекты"
        )
        seo_description = (
            page.seo_description
            if page is not None and page.seo_description
            else (
                "Портфолио full-stack разработчика: backend, API, админ-панели, "
                "self-hosted сервисы, realtime, ML-эксперименты и технические публикации."
            )
        )
        canonical_url = f"{site['base_url']}/" if site["base_url"] else None
        base_url = (site["base_url"] or "").rstrip("/")
        structured_data_items = [
            {
                "@context": "https://schema.org",
                "@type": "ProfilePage",
                "@id": f"{base_url}/#profile" if base_url else "#profile",
                "url": canonical_url,
                "name": "JSInteractive — портфолио разработчика",
                "description": AUTHOR_DESCRIPTION,
                "mainEntity": author_entity(site),
            },
            {
                "@context": "https://schema.org",
                "@type": "ItemList",
                "name": "Проекты JSInteractive",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": 1,
                        "name": "Workspace Organizer",
                        "url": f"{base_url}/workspace-organizer" if base_url else "/workspace-organizer",
                    },
                    {
                        "@type": "ListItem",
                        "position": 2,
                        "name": "Vanga",
                        "url": f"{base_url}/projects/vanga" if base_url else "/projects/vanga",
                    },
                    {
                        "@type": "ListItem",
                        "position": 3,
                        "name": "The-Game",
                        "url": f"{base_url}/projects/the-game" if base_url else "/projects/the-game",
                    },
                    {
                        "@type": "ListItem",
                        "position": 4,
                        "name": "ChurchCMS",
                        "url": f"{base_url}/projects/churchcms" if base_url else "/projects/churchcms",
                    },
                ],
            },
        ]

        response = make_response(
            render_template(
                "public/home/index.html",
                site=site,
                articles=articles,
                home_page=page,
                home_blocks=home_blocks,
                home_blocks_by_type=home_blocks_by_type,
                home_anchor_ids=home_anchor_ids,
                home_settings=home_settings,
                seo_title=seo_title,
                seo_description=seo_description,
                canonical_url=canonical_url,
                seo_image_url=share_image_url(site),
                seo_image_alt="JSInteractive — разработка, проекты и публикации",
                seo_preload_image_url=HERO_IMAGE_URL,
                structured_data_items=structured_data_items,
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
