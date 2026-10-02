from flask import Flask

from views.public.projects import views


def install(app: Flask) -> None:
    app.add_url_rule(
        "/projects/<project_slug>",
        view_func=views.ProjectPromoPage.as_view("project_promo"),
        methods=["GET"],
    )
