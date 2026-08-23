from flask import Flask

from settings import config
from views.dashboard.catalog import views

def install(app: Flask):
    # Список категорий + создание (GET/POST)
    app.add_url_rule(
        f'{config.ADMIN_ROUTE_PREFIX}/catalog',
        view_func=views.CatalogIndexView.as_view('admin.catalog.index')
    )

    # Дерево категорий (JSON для AJAX)
    app.add_url_rule(
        f'{config.ADMIN_ROUTE_PREFIX}/catalog/tree',
        view_func=views.CategoryTreeView.as_view('admin.catalog.tree')
    )

    # Удаление категории (GET)
    app.add_url_rule(
        f'{config.ADMIN_ROUTE_PREFIX}/catalog/delete/<uuid:cat_id>',
        view_func=views.CategoryDeleteView.as_view('admin.catalog.delete')
    )

    # Редактирование категории (GET/POST)
    app.add_url_rule(
        f'{config.ADMIN_ROUTE_PREFIX}/catalog/edit/<uuid:cat_id>',
        view_func=views.CategoryEditView.as_view('admin.catalog.edit')
    )