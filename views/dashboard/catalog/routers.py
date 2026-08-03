from flask import Flask

from settings import config
from views.dashboard.catalog import views

def install(app: Flask):
    app.add_url_rule(
        f'{config.ADMIN_ROUTE_PREFIX}/catalog',
        view_func=views.CatalogList.as_view('admin.catalog.index')
    )