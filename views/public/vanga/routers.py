from flask import Flask

from views.public.vanga import views


def install(app: Flask) -> None:
    app.add_url_rule(
        "/demo/vanga",
        view_func=views.VangaDemoPage.as_view("vanga_demo"),
        methods=["GET", "POST"],
    )
    app.add_url_rule(
        "/demo/vanga/search",
        endpoint="vanga_search",
        view_func=views.vanga_search,
        methods=["GET"],
    )
    app.add_url_rule(
        "/demo/vanga/predict",
        endpoint="vanga_predict_api",
        view_func=views.vanga_predict_api,
        methods=["POST"],
    )
