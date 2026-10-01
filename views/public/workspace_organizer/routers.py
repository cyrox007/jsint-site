from flask import Flask, redirect, url_for

from views.public.workspace_organizer import views


def legacy_notes_redirect():
    return redirect(url_for("workspace_organizer"), code=301)


def install(app: Flask) -> None:
    app.add_url_rule(
        "/workspace-organizer",
        view_func=views.WorkspaceOrganizerPromoPage.as_view(
            "workspace_organizer"
        ),
        methods=["GET"],
    )
    app.add_url_rule(
        "/notes",
        endpoint="workspace_organizer_legacy_notes",
        view_func=legacy_notes_redirect,
        methods=["GET"],
    )
