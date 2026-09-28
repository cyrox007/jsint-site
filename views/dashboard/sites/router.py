from flask import Flask

from settings import config
from views.dashboard.sites import views


def install(app: Flask) -> None:
    app.add_url_rule(
        f"{config.ADMIN_ROUTE_PREFIX}/sites",
        view_func=views.SitesPage.as_view("admin.sites.index"),
        methods=["GET", "POST"],
    )
