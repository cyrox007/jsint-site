from flask import Flask

from views.public.contact import views


def install(app: Flask) -> None:
    app.add_url_rule(
        "/contact",
        view_func=views.ContactPage.as_view("contact"),
        methods=["GET", "POST"],
    )
