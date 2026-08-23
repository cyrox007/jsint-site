from uuid import UUID

from flask import flash, jsonify, render_template, request, redirect, url_for
from flask.views import MethodView
from sqlalchemy.orm import Session

from components.auth.decorator import login_required, with_db_session
from services.catalog import CatalogService
from models.categories import Category
from models.publication import Publication


class CatalogIndexView(MethodView):
    """
    Управление категориями (список + создание)
    """
    @login_required
    @with_db_session
    def get(self, db_session: Session):
        # Все категории
        categories = db_session.query(Category).order_by(Category.title).all()

        # Статистика
        total = db_session.query(Publication).count()
        published = db_session.query(Publication).filter(Publication.is_published == True).count()
        draft = total - published

        return render_template(
            'dashboard/catalog/index.html',
            categories=categories,
            total_publications=total,
            published_count=published,
            draft_count=draft
        )

    @login_required
    @with_db_session
    def post(self, db_session: Session):
        """Создание новой категории"""
        title = request.form.get('title', '').strip()
        slug = request.form.get('slug', '').strip()
        description = request.form.get('description', '').strip()

        if not title or not slug:
            flash('Название и URL обязательны', 'error')
            return redirect(url_for('admin.catalog.index'))

        # Проверка уникальности slug
        existing = Category.get_by_slug(db_session, slug)
        if existing:
            flash('Категория с таким URL уже существует', 'error')
            return redirect(url_for('admin.catalog.index'))

        data = {
            'title': title,
            'slug': slug,
            'description': description,
            'parent_id': None  # пока без иерархии, можно добавить позже
        }
        category = CatalogService.create_category(db_session, data)
        if category:
            flash('Категория создана', 'success')
        else:
            flash('Ошибка создания', 'error')
        return redirect(url_for('admin.catalog.index'))


class CategoryTreeView(MethodView):
    """Возвращает дерево категорий в JSON (для AJAX)"""
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


class CategoryDeleteView(MethodView):
    """Удаление категории (с проверкой)"""
    @login_required
    @with_db_session
    def get(self, db_session: Session, cat_id: UUID):
        category = Category.get_by_id(db_session, cat_id)
        if not category:
            flash('Категория не найдена', 'error')
            return redirect(url_for('admin.catalog.index'))

        # Проверка на дочерние категории
        children = Category.get_children(db_session, cat_id)
        if children:
            flash('Невозможно удалить категорию, у которой есть подкатегории', 'error')
            return redirect(url_for('admin.catalog.index'))

        # Проверка на публикации в этой категории
        pubs = db_session.query(Publication).filter(Publication.category_id == cat_id).count()
        if pubs > 0:
            flash('Невозможно удалить категорию, в которой есть публикации', 'error')
            return redirect(url_for('admin.catalog.index'))

        success = CatalogService.delete_category(db_session, cat_id)
        if success:
            flash('Категория удалена', 'success')
        else:
            flash('Ошибка удаления', 'error')
        return redirect(url_for('admin.catalog.index'))


class CategoryEditView(MethodView):
    """Редактирование категории"""
    @login_required
    @with_db_session
    def get(self, db_session: Session, cat_id: UUID):
        category = Category.get_by_id(db_session, cat_id)
        if not category:
            flash('Категория не найдена', 'error')
            return redirect(url_for('admin.catalog.index'))

        # Список всех категорий, кроме текущей (для выбора родителя)
        all_categories = db_session.query(Category).filter(Category.id != cat_id).order_by(Category.title).all()
        return render_template('dashboard/catalog/edit.html', category=category, all_categories=all_categories)

    @login_required
    @with_db_session
    def post(self, db_session: Session, cat_id: UUID):
        title = request.form.get('title', '').strip()
        slug = request.form.get('slug', '').strip()
        description = request.form.get('description', '').strip()
        parent_id = request.form.get('parent_id')

        if not title or not slug:
            flash('Название и URL обязательны', 'error')
            return redirect(url_for('admin.catalog.edit', cat_id=cat_id))

        data = {
            'title': title,
            'slug': slug,
            'description': description,
            'parent_id': UUID(parent_id) if parent_id else None
        }
        updated = CatalogService.update_category(db_session, cat_id, data)
        if updated:
            flash('Категория обновлена', 'success')
        else:
            flash('Ошибка обновления (возможно, такой slug уже занят)', 'error')
        return redirect(url_for('admin.catalog.edit', cat_id=cat_id))