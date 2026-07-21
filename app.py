from flask import Flask
from settings import config


def create_app() -> Flask:

    from views.home import routers as home_router

    from views.auth import router as auth_router
    from views.dashboard.blog import router as d_blog_router
    from views.dashboard.catalog import router as d_catalog_router
    
    app = Flask(__name__, static_folder='static')
    app.config.from_mapping(
        SECRET_KEY=config.SECRET_KEY
    )

    home_router.install(app)

    auth_router.install(app)
    d_blog_router.install(app)
    d_catalog_router.install(app)
    
    return app