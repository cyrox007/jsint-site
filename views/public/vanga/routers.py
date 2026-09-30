from flask import Flask

from views.public.vanga import views


def install(app: Flask) -> None:
    app.add_url_rule(
        "/demo/vanga",
        view_func=views.VangaDemoPage.as_view("vanga_demo"),
        methods=["GET", "POST"],
    )
