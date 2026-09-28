from flask import Flask

from settings import config
from views.dashboard.users import views


def install(app: Flask) -> None:
    app.add_url_rule(
        f"{config.ADMIN_ROUTE_PREFIX}/users",
        view_func=views.UserManagementPage.as_view("admin.users.index"),
        methods=["GET", "POST"],
    )
