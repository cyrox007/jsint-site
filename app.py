from __future__ import annotations

import logging

from flask import Flask, render_template, request, session
from werkzeug.middleware.proxy_fix import ProxyFix

from components.security.csrf import init_app as init_csrf
from components.security.headers import apply_security_headers
from components.security.html import safe_rich_text
from settings import config
from views.system import healthcheck


def create_app() -> Flask:
    config.validate()

    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    from views.public.home import routers as home_router
    from views.public.articles import routers as article_router
    from views.public.contact import routers as contact_router
    from views.public import api as public_api
    from views.public import media as public_media
    from views.public import seo as public_seo
    from views.auth import router as auth_router
    from views.dashboard.main import router as d_main_router
    from views.dashboard.blog import routers as d_blog_router
    from views.dashboard.catalog import routers as d_catalog_router
    from views.dashboard.control_plane import router as d_control_plane_router
    from views.dashboard.sites import router as d_sites_router
    from views.dashboard.media import router as d_media_router
    from views.dashboard.pages import router as d_pages_router
    from views.dashboard.users import router as d_users_router
    from views.dashboard.contact import router as d_contact_router
    from views import notes_api
    from views import demo_api

    app = Flask(__name__, static_folder="static")
    app.config.from_mapping(
        SECRET_KEY=config.SECRET_KEY,
        SESSION_COOKIE_SECURE=config.SESSION_COOKIE_SECURE,
        SESSION_COOKIE_HTTPONLY=config.SESSION_COOKIE_HTTPONLY,
        SESSION_COOKIE_SAMESITE=config.SESSION_COOKIE_SAMESITE,
        SESSION_COOKIE_NAME=config.SESSION_COOKIE_NAME,
        PERMANENT_SESSION_LIFETIME=config.PERMANENT_SESSION_LIFETIME,
        MAX_CONTENT_LENGTH=config.MAX_CONTENT_LENGTH,
        PREFERRED_URL_SCHEME=config.PREFERRED_URL_SCHEME,
        TRUSTED_HOSTS=config.ALLOWED_HOSTS or None,
        YANDEX_METRIKA_ID=config.YANDEX_METRIKA_ID,
        YANDEX_WEBMASTER_VERIFICATION=config.YANDEX_WEBMASTER_VERIFICATION,
        SITE_BASE_URL=config.SITE_BASE_URL,
    )

    if config.BEHIND_PROXY:
        # WSGI-порт должен быть доступен только доверенному reverse proxy.
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=1,
            x_proto=1,
            x_host=1,
        )

    init_csrf(app)
    app.after_request(apply_security_headers)
    app.jinja_env.filters["safe_rich_text"] = safe_rich_text

    @app.context_processor
    def inject_admin_site_workspace():
        if not session.get("user_id") or not request.path.startswith(config.ADMIN_ROUTE_PREFIX):
            return {}

        from components.admin.site_context import resolve_admin_site
        from database import Database
        from services.site import SiteService

        db_session = Database.connect_database()
        try:
            sites = SiteService.list_sites(db_session)
            selected_site = resolve_admin_site(db_session)
            return {
                "admin_sites": sites,
                "admin_selected_site": selected_site,
            }
        finally:
            db_session.close()

    home_router.install(app)
    article_router.install(app)
    contact_router.install(app)
    public_api.install(app)
    public_media.install(app)
    auth_router.install(app)
    d_main_router.install(app)
    d_blog_router.install(app)
    d_catalog_router.install(app)
    d_control_plane_router.install(app)
    d_sites_router.install(app)
    d_media_router.install(app)
    d_pages_router.install(app)
    d_users_router.install(app)
    d_contact_router.install(app)
    notes_api.install(app)
    demo_api.install(app)

    app.add_url_rule("/robots.txt", endpoint="robots", view_func=public_seo.robots_txt, methods=["GET"])
    app.add_url_rule("/sitemap.xml", endpoint="sitemap", view_func=public_seo.sitemap_xml, methods=["GET"])
    if config.YANDEX_INDEXNOW_KEY:
        app.add_url_rule(
            f"/{config.YANDEX_INDEXNOW_KEY}.txt",
            endpoint="yandex_indexnow_key",
            view_func=public_seo.indexnow_key,
            methods=["GET"],
        )
    app.add_url_rule("/healthz", endpoint="healthz", view_func=healthcheck, methods=["GET"])

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(413)
    def too_large(_error):
        return render_template("errors/413.html"), 413

    @app.errorhandler(500)
    def internal_error(_error):
        return render_template("errors/500.html"), 500

    return app
