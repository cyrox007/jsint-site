from flask import Flask

from settings import config
from views.dashboard.control_plane import views


def install(app: Flask) -> None:
    prefix = config.ADMIN_ROUTE_PREFIX
    app.add_url_rule(
        f"{prefix}/licenses",
        view_func=views.LicenseListView.as_view("admin.licenses.index"),
        methods=["GET", "POST"],
    )
    app.add_url_rule(
        f"{prefix}/licenses/<uuid:license_row_id>/status",
        view_func=views.LicenseStatusView.as_view("admin.licenses.status"),
        methods=["POST"],
    )
    app.add_url_rule(
        f"{prefix}/licenses/<uuid:license_row_id>/activation",
        view_func=views.LicenseActivationView.as_view("admin.licenses.activation"),
        methods=["POST"],
    )
    app.add_url_rule(
        f"{prefix}/releases",
        view_func=views.ReleaseListView.as_view("admin.releases.index"),
        methods=["GET", "POST"],
    )
