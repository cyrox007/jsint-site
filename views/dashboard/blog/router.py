from flask import Flask

from views.dashboard.blog import views

from settings import config

def install(app: Flask):
    """ app.add_url_rule(
        '/',
        view_func=views.MainPage.as_view('index')
    ) """
    app.add_url_rule(
        f'{config.ADMIN_ROUTE_PREFIX}/list',
        view_func=views.PublicationListPage.as_view('admin.publication.index')
    )
    app.add_url_rule(
        '/create',
        view_func=views.CreatePost.as_view('blog.create')
    )
    app.add_url_rule(
        '/<int:uuid>/update',
        view_func=views.UpdatePost.as_view('blog.update')
    )
    app.add_url_rule(
        '/<int:uuid>/delete',
        view_func=views.DeletePost.as_view('blog.delete')
    )