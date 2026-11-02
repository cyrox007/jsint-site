from flask import Flask

from views.public.projects import impulse_arcade, the_game, views


def install(app: Flask) -> None:
    app.add_url_rule(
        "/projects/the-game",
        view_func=the_game.TheGameProjectPage.as_view("the_game_project"),
        methods=["GET"],
    )
    app.add_url_rule(
        "/projects/impulse-arcade",
        view_func=impulse_arcade.ImpulseArcadeProjectPage.as_view(
            "impulse_arcade_project"
        ),
        methods=["GET"],
    )
    app.add_url_rule(
        "/projects/<project_slug>",
        view_func=views.ProjectPromoPage.as_view("project_promo"),
        methods=["GET"],
    )
