from flask.views import MethodView


class ArticlesListPage(MethodView):
    def get(self, categories_slug: str = None):
        print(categories_slug)
        return

class ArticlesDetailPage(MethodView):
    def get(self, categories_slug: str = None, publication_slug: str = None):
        print(categories_slug)
        return