from flask import Flask
from settings import config


def create_app() -> Flask:

    from views.public.home import routers as home_router
    from views.public.articles import routers as article_router

    from views.auth import router as auth_router

    from views.dashboard.main import router as d_main_router
    from views.dashboard.blog import routers as d_blog_router
    from views.dashboard.catalog import routers as d_catalog_router
    
    app = Flask(__name__, static_folder='static')
    app.config.from_mapping(
        SECRET_KEY=config.SECRET_KEY
    )

    home_router.install(app)
    article_router.install(app)

    auth_router.install(app)
    d_main_router.install(app)
    d_blog_router.install(app)
    d_catalog_router.install(app)
    
    return app