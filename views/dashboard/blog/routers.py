from flask import Flask

from settings import config
from views.dashboard.blog import views


def install(app: Flask):
    app.add_url_rule(
        f"{config.ADMIN_ROUTE_PREFIX}/publications/list",
        view_func=views.PublicationListPage.as_view("admin.publication.index"),
    )
    app.add_url_rule(
        f"{config.ADMIN_ROUTE_PREFIX}/publications/create",
        view_func=views.CreatePost.as_view("admin.publication.create"),
    )
    app.add_url_rule(
        f"{config.ADMIN_ROUTE_PREFIX}/publications/check-slug/<string:slug>",
        view_func=views.CheckSlug.as_view("admin.publication.check-slug"),
    )
    app.add_url_rule(
        f"{config.ADMIN_ROUTE_PREFIX}/publications/edit/<uuid:id>",
        view_func=views.UpdatePost.as_view("admin.publication.edit"),
    )
    app.add_url_rule(
        f"{config.ADMIN_ROUTE_PREFIX}/publications/delete/<uuid:id>",
        view_func=views.DeletePost.as_view("admin.publication.delete"),
    )
