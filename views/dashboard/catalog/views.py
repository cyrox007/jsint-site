from uuid import UUID

from flask import flash, jsonify, render_template, request
from flask.views import MethodView
from sqlalchemy.orm import Session

from components.auth.decorator import login_required, with_db_session
from services.catalog import CatalogService
from services.publication import PublicationService


class CatalogList(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session):
        # 1. Получаем дерево категорий (корневые)
        tree = CatalogService.get_category_tree(db_session, parent_id=None)

        # 2. Получаем параметр фильтра из запроса (категория)
        category_id = request.args.get('category_id')
        if category_id:
            try:
                cat_uuid = UUID(category_id)
                # Получаем все публикации в этой категории (включая вложенные?)
                # Для простоты – только прямые
                publications = PublicationService.get_publications(
                    db_session,
                    category_id=cat_uuid,
                    is_published=None   # в админке показываем все
                )
            except ValueError:
                flash('Неверный ID категории', 'error')
                publications = PublicationService.get_publications(db_session, is_published=None)
        else:
            publications = PublicationService.get_publications(db_session, is_published=None)

        # 3. Для удобства навигации добавим в дерево количество публикаций
        # Для каждой категории можно посчитать количество публикаций (прямых и всех потомков)
        # Реализуем это отдельной функцией, чтобы не нагружать запросы.
        # Можно сделать через подзапрос, но для простоты пока оставим без подсчёта.
        # В будущем можно добавить метод в модель Category, который возвращает число публикаций.

        context = {
            'tree': tree,
            'publications': publications,
            'selected_category_id': category_id,
        }
        return render_template('dashboard/catalog/index.html', **context)
    
    
class CategoryTreeView(MethodView):
    """
    Возвращает дерево категорий в JSON (для AJAX, например, для построения меню).
    """
    @login_required
    @with_db_session
    def get(self, db_session: Session):
        parent_id = request.args.get('parent_id')
        if parent_id:
            try:
                parent_uuid = UUID(parent_id)
                tree = CatalogService.get_category_tree(db_session, parent_id=parent_uuid)
            except ValueError:
                tree = []
        else:
            tree = CatalogService.get_category_tree(db_session)
        return jsonify(tree)