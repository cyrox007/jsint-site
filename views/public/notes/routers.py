from flask import Flask

from views.public.notes import views


def install(app: Flask) -> None:
    app.add_url_rule(
        "/notes",
        view_func=views.NotesPromoPage.as_view("notes_promo"),
        methods=["GET"],
    )
