from flask import Flask

from settings import config
from views.dashboard.media import views


def install(app: Flask) -> None:
    app.add_url_rule(
        f"{config.ADMIN_ROUTE_PREFIX}/media",
        view_func=views.MediaLibraryPage.as_view("admin.media.index"),
        methods=["GET", "POST"],
    )
