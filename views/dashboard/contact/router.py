from flask import Flask

from settings import config
from views.dashboard.contact import views


def install(app: Flask) -> None:
    app.add_url_rule(
        f"{config.ADMIN_ROUTE_PREFIX}/contact",
        view_func=views.ContactInboxPage.as_view("admin.contact.index"),
        methods=["GET", "POST"],
    )
