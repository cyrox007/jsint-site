from flask import Flask

from settings import config
from views.dashboard.pages import views


def install(app: Flask) -> None:
    app.add_url_rule(
        f"{config.ADMIN_ROUTE_PREFIX}/pages",
        view_func=views.PageList.as_view("admin.pages.index"),
        methods=["GET", "POST"],
    )
    app.add_url_rule(
        f"{config.ADMIN_ROUTE_PREFIX}/pages/<uuid:page_id>",
        view_func=views.PageEdit.as_view("admin.pages.edit"),
        methods=["GET", "POST"],
    )
