from flask import Flask
from sqlalchemy.ext.declarative import declarative_base
from settings import config


def create_app() -> Flask:

    from views.home import routers as home_router
    
    app = Flask(__name__, static_folder='static')
    app.config.from_mapping(
        SECRET_KEY=config.SECRET_KEY
    )


    home_router.install(app)
    return app