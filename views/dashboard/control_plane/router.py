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
        f"{prefix}/licenses/issue",
        view_func=views.LicenseIssueView.as_view("admin.licenses.issue"),
        methods=["POST"],
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
    app.add_url_rule(
        f"{prefix}/releases/github",
        view_func=views.ReleaseGitHubPrepareView.as_view("admin.releases.github"),
        methods=["POST"],
    )
    app.add_url_rule(
        "/api/operator/v1/release-upload",
        view_func=views.ReleaseUploadView.as_view("admin.releases.upload"),
        methods=["POST"],
    )
    app.add_url_rule(
        f"{prefix}/releases/publish",
        view_func=views.ReleasePublishView.as_view("admin.releases.publish"),
        methods=["POST"],
    )
    app.add_url_rule(
        f"{prefix}/releases/<uuid:release_row_id>/status",
        view_func=views.ReleaseStatusView.as_view("admin.releases.status"),
        methods=["POST"],
    )
