from flask import Flask

from settings import config
from views.auth import views


def install(app: Flask):
    app.add_url_rule(
        f"{config.ADMIN_ROUTE_PREFIX}/login",
        view_func=views.LoginPage.as_view("auth.login"),
    )
    app.add_url_rule(
        f"{config.ADMIN_ROUTE_PREFIX}/logout",
        view_func=views.LogoutUser.as_view("auth.logout"),
    )
