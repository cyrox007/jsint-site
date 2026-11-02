from __future__ import annotations

from flask import render_template
from flask.views import MethodView

from components.auth.decorator import with_db_session
from services.page import PageService
from services.public_seo import author_entity, breadcrumb_schema, share_image_url
from services.site import SiteService


# Адрес демо соответствует опубликованному GitHub Pages проекта.
# Исходники и версия приводятся по репозиторию cyrox007/impulse-arcade.
IMPULSE_DEMO_URL = "https://cyrox007.github.io/impulse-arcade/"
IMPULSE_REPOSITORY_URL = "https://github.com/cyrox007/impulse-arcade"
IMPULSE_VERSION = "1.0.0-rc.1"

IMPULSE_FEATURES = (
    "Пять секторов с нарастающей сложностью",
    "Два босса: Страж ядра и Реактор",
    "Разрушаемые, призматические, взрывные и направленные кирпичи",
    "Мультишар, магнитная платформа, барьер и пробивной импульс",
    "Управление на компьютере и сенсорном экране",
    "Локальная контрольная точка между секторами",
    "Настройки звука, чувствительности и визуальных эффектов",
)


class ImpulseArcadeProjectPage(MethodView):
    """Промостраница новой аркады; сама игра остаётся на GitHub Pages."""

    decorators = [with_db_session]

    def get(self, db_session):
        site_model = SiteService.get_default(db_session)
        site = SiteService.public_config(site_model)
        PageService.apply_public_navigation(db_session, site_model.id, site)

        base_url = (site["base_url"] or "").rstrip("/")
        canonical_url = f"{base_url}/projects/impulse-arcade" if base_url else None

        structured_data_items = [
            {
                "@context": "https://schema.org",
                "@type": "VideoGame",
                "@id": f"{canonical_url}#game" if canonical_url else None,
                "name": "Импульс",
                "url": canonical_url,
                "sameAs": IMPULSE_REPOSITORY_URL,
                "description": (
                    "Бесплатный браузерный арканоид на JavaScript и Canvas 2D: "
                    "пять секторов, два босса, бонусы и локальное сохранение."
                ),
                "genre": "Арканоид",
                "gamePlatform": "Веб-браузер на ПК и смартфоне",
                "playMode": "SinglePlayer",
                "applicationCategory": "GameApplication",
                "operatingSystem": "Web",
                "softwareVersion": IMPULSE_VERSION,
                "isAccessibleForFree": True,
                "inLanguage": "ru-RU",
                "creator": author_entity(site),
                "featureList": list(IMPULSE_FEATURES),
                "potentialAction": {
                    "@type": "PlayAction",
                    "target": IMPULSE_DEMO_URL,
                },
            },
            breadcrumb_schema(
                [
                    ("JSInteractive", f"{base_url}/" if base_url else "/"),
                    ("Проекты", f"{base_url}/#systems" if base_url else "/#systems"),
                    ("Импульс", canonical_url),
                ]
            ),
        ]

        return render_template(
            "public/projects/impulse_arcade.html",
            site=site,
            canonical_url=canonical_url,
            demo_url=IMPULSE_DEMO_URL,
            repository_url=IMPULSE_REPOSITORY_URL,
            game_version=IMPULSE_VERSION,
            seo_title="Импульс — арканоид на JavaScript и Canvas | JSInteractive",
            seo_description=(
                "Импульс — бесплатная браузерная аркада с пятью секторами, "
                "двумя боссами, мультишаром и бонусами. Играйте на ПК и "
                "смартфоне; релиз-кандидат 1.0.0-rc.1."
            ),
            seo_image_url=share_image_url(site),
            seo_image_alt="Импульс — браузерный арканоид JSInteractive",
            structured_data_items=structured_data_items,
        )
