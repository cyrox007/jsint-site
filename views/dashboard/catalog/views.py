from __future__ import annotations

from uuid import UUID

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask.views import MethodView
from sqlalchemy.orm import Session

from components.auth.decorator import login_required, with_db_session
from models.categories import Category
from models.publication import Publication
from services.catalog import CatalogService
from utils.validation import validate_slug


class CatalogIndexView(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session):
        categories = db_session.query(Category).order_by(Category.title).all()
        total = db_session.query(Publication).count()
        published = db_session.query(Publication).filter(Publication.is_published.is_(True)).count()

        return render_template(
            "dashboard/catalog/index.html",
            categories=categories,
            total_publications=total,
            published_count=published,
            draft_count=total - published,
        )

    @login_required
    @with_db_session
    def post(self, db_session: Session):
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        try:
            slug = validate_slug(request.form.get("slug", ""))
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("admin.catalog.index"))

        category = CatalogService.create_category(
            db_session,
            {
                "title": title,
                "slug": slug,
                "description": description,
                "parent_id": None,
            },
        )
        flash(
            "Категория создана" if category else "Не удалось создать категорию",
            "success" if category else "error",
        )
        return redirect(url_for("admin.catalog.index"))


class CategoryTreeView(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session):
        parent_id = request.args.get("parent_id")
        if parent_id:
            try:
                tree = CatalogService.get_category_tree(db_session, parent_id=UUID(parent_id))
            except ValueError:
                return jsonify({"error": "Некорректный parent_id"}), 400
        else:
            tree = CatalogService.get_category_tree(db_session)
        return jsonify(tree)


class CategoryDeleteView(MethodView):
    @login_required
    @with_db_session
    def post(self, db_session: Session, cat_id: UUID):
        if CatalogService.delete_category(db_session, cat_id):
            flash("Категория удалена", "success")
        else:
            flash("Категорию нельзя удалить: проверьте дочерние категории и публикации", "error")
        return redirect(url_for("admin.catalog.index"))


class CategoryEditView(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session, cat_id: UUID):
        category = Category.get_by_id(db_session, cat_id)
        if not category:
            flash("Категория не найдена", "error")
            return redirect(url_for("admin.catalog.index"))

        invalid_ids = {cat_id}
        invalid_ids.update(item.id for item in Category.get_all_descendants(db_session, cat_id))
        all_categories = (
            db_session.query(Category)
            .filter(~Category.id.in_(invalid_ids))
            .order_by(Category.title)
            .all()
        )
        return render_template(
            "dashboard/catalog/edit.html",
            category=category,
            all_categories=all_categories,
        )

    @login_required
    @with_db_session
    def post(self, db_session: Session, cat_id: UUID):
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        parent_raw = request.form.get("parent_id", "").strip()

        try:
            slug = validate_slug(request.form.get("slug", ""))
            parent_id = UUID(parent_raw) if parent_raw else None
        except ValueError as exc:
            flash(str(exc) or "Некорректные данные категории", "error")
            return redirect(url_for("admin.catalog.edit", cat_id=cat_id))

        updated = CatalogService.update_category(
            db_session,
            cat_id,
            {
                "title": title,
                "slug": slug,
                "description": description,
                "parent_id": parent_id,
            },
        )
        if updated:
            flash("Категория обновлена", "success")
        else:
            flash("Категорию не удалось обновить: проверьте URL и иерархию", "error")
        return redirect(url_for("admin.catalog.edit", cat_id=cat_id))
