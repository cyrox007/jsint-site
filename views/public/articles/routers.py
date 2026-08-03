from flask import Flask

from views.public.articles import views

def install(app: Flask):
    app.add_url_rule(
        '/articles/<string:categories_slug>/',
        view_func=views.ArticlesListPage.as_view('public.articles.index')
    )

    app.add_url_rule(
        '/articles/<string:categories_slug>/<string:publication_slug>',
        view_func=views.ArticlesDetailPage.as_view('public.articles.show')
    )