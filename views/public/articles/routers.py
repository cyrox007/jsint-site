from flask import Flask

from views.public.articles import views

def install(app: Flask):
    app.add_url_rule(
        '/category/<categories_slug>/article/<publication_slug>',
        view_func=views.ArticleDetailView.as_view('public.articles.show')
    )