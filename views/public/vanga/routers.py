from flask import Flask

from views.public.vanga import accuracy, future, potential, views


def install(app: Flask) -> None:
    app.add_url_rule(
        "/projects/vanga/methodology",
        endpoint="vanga_methodology",
        view_func=views.vanga_methodology,
        methods=["GET"],
    )
    app.add_url_rule(
        "/projects/vanga/accuracy",
        endpoint="vanga_accuracy",
        view_func=accuracy.vanga_accuracy,
        methods=["GET"],
    )
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
    app.add_url_rule(
        "/demo/vanga/predict-profile",
        endpoint="vanga_predict_profile_api",
        view_func=potential.vanga_predict_profile_api,
        methods=["POST"],
    )
    app.add_url_rule(
        "/demo/vanga/future-catalog",
        endpoint="vanga_future_catalog_api",
        view_func=future.vanga_future_catalog_api,
        methods=["GET"],
    )
    app.add_url_rule(
        "/demo/vanga/future-payload",
        endpoint="vanga_future_prediction_payload_api",
        view_func=future.vanga_future_prediction_payload_api,
        methods=["POST"],
    )
    app.add_url_rule(
        "/demo/vanga/p/<uuid:snapshot_id>",
        endpoint="vanga_snapshot",
        view_func=views.vanga_snapshot,
        methods=["GET"],
    )
    app.add_url_rule(
        "/demo/vanga/p/<uuid:snapshot_id>/share.svg",
        endpoint="vanga_snapshot_share_svg",
        view_func=accuracy.vanga_snapshot_share_svg,
        methods=["GET"],
    )
    app.add_url_rule(
        "/demo/vanga/p/<uuid:snapshot_id>/potential",
        endpoint="vanga_snapshot_potential",
        view_func=potential.vanga_snapshot_potential,
        methods=["GET"],
    )
