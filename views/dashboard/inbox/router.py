from flask import Flask

from settings import config
from views.dashboard.inbox import views


def install(app: Flask) -> None:
    prefix = f"{config.ADMIN_ROUTE_PREFIX}/inbox"
    app.add_url_rule(
        prefix,
        view_func=views.InboxPage.as_view("admin.inbox.index"),
        methods=["GET"],
    )
    app.add_url_rule(
        f"{prefix}/settings",
        view_func=views.InboxSettingsPage.as_view("admin.inbox.settings"),
        methods=["GET", "POST"],
    )
    app.add_url_rule(
        f"{prefix}/<uuid:notification_id>",
        view_func=views.InboxDetailPage.as_view("admin.inbox.detail"),
        methods=["GET", "POST"],
    )
    app.add_url_rule(
        f"{prefix}/<uuid:notification_id>/diagnostic.zip",
        view_func=views.DiagnosticDownload.as_view("admin.inbox.diagnostic"),
        methods=["GET"],
    )
