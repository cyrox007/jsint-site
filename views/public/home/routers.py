from flask import Flask

from views.public.home import views

def install(app: Flask):
    app.add_url_rule(
        '/',
        view_func=views.MainPage.as_view('index')
    )