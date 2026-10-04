from __future__ import annotations

from flask import render_template
from flask.views import MethodView

from components.auth.decorator import with_db_session
from services.page import PageService
from services.public_seo import author_entity, breadcrumb_schema, share_image_url
from services.site import SiteService


class TheGameProjectPage(MethodView):
    """Промо-страница исторического учебного проекта The-Game."""

    decorators = [with_db_session]

    def get(self, db_session):
        site_model = SiteService.get_default(db_session)
        site = SiteService.public_config(site_model)
        PageService.apply_public_navigation(db_session, site_model.id, site)

        base_url = (site["base_url"] or "").rstrip("/")
        canonical_url = f"{base_url}/projects/the-game" if base_url else None
        demo_url = "https://cyrox007.github.io/The-Game/"

        structured_data_items = [
            {
                "@context": "https://schema.org",
                "@type": "SoftwareApplication",
                "@id": f"{canonical_url}#software" if canonical_url else None,
                "name": "The-Game",
                "url": canonical_url,
                "description": (
                    "Учебный архив двух браузерных Canvas-игр 2022 года: "
                    "Dino и Breakout."
                ),
                "applicationCategory": "GameApplication",
                "operatingSystem": "Web",
                "isAccessibleForFree": True,
                "creator": author_entity(site),
                "featureList": [
                    "Dino runner",
                    "Breakout",
                    "Canvas API",
                    "requestAnimationFrame",
                    "sessionStorage",
                    "GitHub Pages live demo",
                ],
                "inLanguage": "ru-RU",
            },
            breadcrumb_schema(
                [
                    ("JSInteractive", f"{base_url}/" if base_url else "/"),
                    ("Проекты", f"{base_url}/#systems" if base_url else "/#systems"),
                    ("The-Game", canonical_url),
                ]
            ),
        ]

        return render_template(
            "public/projects/the_game.html",
            site=site,
            canonical_url=canonical_url,
            demo_url=demo_url,
            seo_title="The-Game — учебные Canvas-игры Dino и Breakout | JSInteractive",
            seo_description=(
                "The-Game — сохранённый учебный проект 2022 года на чистом JavaScript. "
                "Две браузерные Canvas-игры, Dino и Breakout, восстановлены и доступны как live demo."
            ),
            seo_image_url=share_image_url(site),
            seo_image_alt="The-Game — учебные браузерные игры JSInteractive",
            structured_data_items=structured_data_items,
        )
