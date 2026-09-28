from __future__ import annotations

from uuid import UUID

from flask import flash, jsonify, redirect, request, url_for
from flask.views import MethodView
from sqlalchemy.orm import Session

from components.auth.decorator import login_required, with_db_session
from models.categories import Category
from services.catalog import CatalogService
from services.site import SiteService
from utils.validation import validate_slug


def _selected_site(db_session: Session):
    raw = request.values.get("site_id", "").strip()
    if raw:
        try:
            site = SiteService.get_by_id(db_session, UUID(raw))
        except ValueError:
            site = None
        if site is not None:
            return site
    return SiteService.get_default(db_session)


class CatalogIndexView(MethodView):
    """Совместимый маршрут: управление рубриками перенесено в раздел «Контент»."""

    @login_required
    def get(self):
        return redirect(url_for("admin.publication.index"))

    @login_required
    @with_db_session
    def post(self, db_session: Session):
        site = _selected_site(db_session)
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        try:
            slug = validate_slug(request.form.get("slug", ""))
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("admin.publication.index", site_id=site.id))

        category = CatalogService.create_category(
            db_session,
            {
                "site_id": site.id,
                "title": title,
                "slug": slug,
                "description": description,
                "parent_id": None,
            },
        )
        if category:
            flash("Рубрика создана", "success")
            return redirect(
                url_for(
                    "admin.publication.index",
                    site_id=site.id,
                    category_id=category.id,
                )
            )

        flash("Не удалось создать рубрику", "error")
        return redirect(url_for("admin.publication.index", site_id=site.id))


class CategoryTreeView(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session):
        site = _selected_site(db_session)
        parent_id = request.args.get("parent_id")
        try:
            parent_uuid = UUID(parent_id) if parent_id else None
        except ValueError:
            return jsonify({"error": "Некорректный parent_id"}), 400

        tree = CatalogService.get_category_tree(
            db_session,
            site.id,
            parent_id=parent_uuid,
        )
        return jsonify(tree)


class CategoryDeleteView(MethodView):
    @login_required
    @with_db_session
    def post(self, db_session: Session, cat_id: UUID):
        category = Category.get_by_id(db_session, cat_id)
        site_id = category.site_id if category else SiteService.get_default(db_session).id
        if CatalogService.delete_category(db_session, cat_id):
            flash("Рубрика удалена", "success")
        else:
            flash(
                "Рубрику нельзя удалить: проверьте дочерние рубрики и публикации",
                "error",
            )
        return redirect(url_for("admin.publication.index", site_id=site_id))


class CategoryEditView(MethodView):
    """Старый URL редактора открывает inline-редактор в едином workspace."""

    @login_required
    @with_db_session
    def get(self, db_session: Session, cat_id: UUID):
        category = Category.get_by_id(db_session, cat_id)
        if category is None:
            flash("Рубрика не найдена", "error")
            return redirect(url_for("admin.publication.index"))
        return redirect(
            url_for(
                "admin.publication.index",
                site_id=category.site_id,
                category_id=cat_id,
                edit_category=cat_id,
            )
        )

    @login_required
    @with_db_session
    def post(self, db_session: Session, cat_id: UUID):
        category = Category.get_by_id(db_session, cat_id)
        if category is None:
            flash("Рубрика не найдена", "error")
            return redirect(url_for("admin.publication.index"))

        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        parent_raw = request.form.get("parent_id", "").strip()

        try:
            slug = validate_slug(request.form.get("slug", ""))
            parent_id = UUID(parent_raw) if parent_raw else None
        except ValueError as exc:
            flash(str(exc) or "Некорректные данные рубрики", "error")
            return redirect(
                url_for(
                    "admin.publication.index",
                    site_id=category.site_id,
                    category_id=cat_id,
                    edit_category=cat_id,
                )
            )

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
            flash("Рубрика обновлена", "success")
            return redirect(
                url_for(
                    "admin.publication.index",
                    site_id=category.site_id,
                    category_id=cat_id,
                )
            )

        flash("Рубрику не удалось обновить: проверьте URL и иерархию", "error")
        return redirect(
            url_for(
                "admin.publication.index",
                site_id=category.site_id,
                category_id=cat_id,
                edit_category=cat_id,
            )
        )
