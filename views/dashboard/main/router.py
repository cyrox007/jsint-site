from flask import Flask

from settings import config
from views.dashboard.main import views

def install(app: Flask):
    app.add_url_rule(
        f'{config.ADMIN_ROUTE_PREFIX}/',
        view_func=views.DashboardMain.as_view('admin.index')
    )