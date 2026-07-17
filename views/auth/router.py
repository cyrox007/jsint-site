from flask import Flask

from views.auth import views

from settings import config

def install(app: Flask):
    app.add_url_rule(
        f'{config.ADMIN_ROUTE_PREFIX}/login',
        view_func=views.LoginPage.as_view('auth.login')
    )
    app.add_url_rule(
        '/register',
        view_func=views.RegisterPage.as_view('auth.register')
    )
    app.add_url_rule(
        '/logout',
        view_func=views.LogoutUser.as_view('auth.logout')
    )