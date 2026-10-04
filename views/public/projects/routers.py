from flask import Flask

from views.public.projects import the_game, views


def install(app: Flask) -> None:
    app.add_url_rule(
        "/projects/the-game",
        view_func=the_game.TheGameProjectPage.as_view("the_game_project"),
        methods=["GET"],
    )
    app.add_url_rule(
        "/projects/<project_slug>",
        view_func=views.ProjectPromoPage.as_view("project_promo"),
        methods=["GET"],
    )
