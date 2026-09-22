from __future__ import annotations

import logging

from flask import Flask, render_template
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
    from views.public import seo as seo_router
    from views.auth import router as auth_router
    from views.dashboard.main import router as d_main_router
    from views.dashboard.blog import routers as d_blog_router
    from views.dashboard.catalog import routers as d_catalog_router
    from views.dashboard.control_plane import router as d_control_plane_router
    from views import notes_api

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
    )

    if config.BEHIND_PROXY:
        # Безопасно только когда WSGI-порт доступен исключительно доверенному
        # reverse proxy (рекомендуемый production deployment).
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=1,
            x_proto=1,
            x_host=1,
        )

    init_csrf(app)
    app.after_request(apply_security_headers)
    app.jinja_env.filters["safe_rich_text"] = safe_rich_text

    home_router.install(app)
    article_router.install(app)
    seo_router.install(app)
    auth_router.install(app)
    d_main_router.install(app)
    d_blog_router.install(app)
    d_catalog_router.install(app)
    d_control_plane_router.install(app)
    notes_api.install(app)

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
