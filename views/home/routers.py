from flask import Flask

from views.home import view

def install(app: Flask):
    app.add_url_rule(
        '/',
        view_func=view.MainPage.as_view('index')
    )