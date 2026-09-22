from __future__ import annotations

from uuid import UUID

from flask import abort, flash, jsonify, redirect, render_template, request, session, url_for
from flask.views import MethodView
from pydantic import ValidationError
from sqlalchemy import func
from sqlalchemy.orm import Session

from components.auth.decorator import login_required, with_db_session
from components.security.html import sanitize_rich_text
from models.categories import Category
from models.publication import Publication
from schemas.publication import PublicationCreate, PublicationUpdate
from services.catalog import CatalogService
from services.publication import PublicationService
from utils.validation import validate_slug


def _publication_payload(schema_cls):
    content = sanitize_rich_text(request.form.get("content", "").strip())
    return schema_cls(
        title=request.form.get("title", "").strip(),
        slug=request.form.get("slug", "").strip(),
        content=content,
        source_type=request.form.get("source-type", "article").strip(),
        extra_data={
            "seo_title": request.form.get("seo_title", "").strip()[:255],
            "seo_description": request.form.get("seo_description", "").strip()[:320],
        },
        category_id=request.form.get("category_id", ""),
        author_id=session.get("user_id"),
        is_published=request.form.get("is_published") == "on",
        technology_ids=[],
    )


def _validate_publication_references(db_session: Session, data) -> str | None:
    if data.category_id is not None and Category.get_by_id(db_session, data.category_id) is None:
        return "Выбранная рубрика не существует"
    if data.is_published and data.category_id is None:
        return "Для публикации материала выберите рубрику"
    return None


def _validation_message(exc: ValidationError) -> str:
    first = exc.errors()[0] if exc.errors() else {}
    return str(first.get("msg") or "Проверьте заполненные поля")


def _optional_uuid(raw: str) -> UUID | None:
    raw = raw.strip()
    return UUID(raw) if raw else None


def _content_redirect(*, category_id: UUID | str | None = None, edit_category: UUID | str | None = None):
    values: dict[str, str] = {}
    if category_id:
        values["category_id"] = str(category_id)
    if edit_category:
        values["edit_category"] = str(edit_category)
    return redirect(url_for("admin.publication.index", **values))


def _tree_with_counts(items: list[dict], direct_counts: dict[str, int]) -> list[dict]:
    result: list[dict] = []
    for item in items:
        node = dict(item)
        children = _tree_with_counts(item.get("children") or [], direct_counts)
        own_count = direct_counts.get(str(item["id"]), 0)
        node["children"] = children
        node["publication_count"] = own_count + sum(
            child["publication_count"] for child in children
        )
        result.append(node)
    return result


class PublicationListPage(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session):
        filters: dict = {"is_published": None}
        selected_category_id = ""

        search = request.args.get("search", "").strip()
        if search:
            filters["search"] = search[:200]

        status = request.args.get("status", "").strip()
        if status == "published":
            filters["is_published"] = True
        elif status == "draft":
            filters["is_published"] = False

        category_raw = request.args.get("category_id", "").strip()
        if category_raw:
            try:
                category_id = UUID(category_raw)
                selected = Category.get_by_id(db_session, category_id)
                if selected is None:
                    flash("Выбранная рубрика не найдена", "error")
                else:
                    descendants = Category.get_all_descendants(db_session, category_id)
                    filters["category_ids"] = [category_id, *[item.id for item in descendants]]
                    selected_category_id = str(category_id)
            except ValueError:
                flash("Некорректный фильтр рубрики", "error")

        publications = PublicationService.get_publications(db_session, **filters)
        categories = db_session.query(Category).order_by(Category.title).all()

        total_publications = db_session.query(Publication).count()
        count_rows = (
            db_session.query(Publication.category_id, func.count(Publication.id))
            .filter(Publication.category_id.is_not(None))
            .group_by(Publication.category_id)
            .all()
        )
        direct_counts = {str(category_id): int(count) for category_id, count in count_rows}
        category_tree = _tree_with_counts(Category.get_tree(db_session), direct_counts)
        category_parent_ids = {
            str(category.id): str(category.parent_id or "") for category in categories
        }

        edit_category_id = request.args.get("edit_category", "").strip()
        if edit_category_id:
            try:
                edit_id = UUID(edit_category_id)
                if Category.get_by_id(db_session, edit_id) is None:
                    edit_category_id = ""
            except ValueError:
                edit_category_id = ""

        return render_template(
            "dashboard/publication/index.html",
            publications=publications,
            categories=categories,
            category_tree=category_tree,
            selected_category_id=selected_category_id,
            category_parent_ids=category_parent_ids,
            edit_category_id=edit_category_id,
            total_publications=total_publications,
        )

    @login_required
    @with_db_session
    def post(self, db_session: Session):
        action = request.form.get("action", "").strip()
        return_category_raw = request.form.get("return_category_id", "").strip()
        return_category_id: UUID | None = None
        if return_category_raw:
            try:
                return_category_id = UUID(return_category_raw)
            except ValueError:
                return_category_id = None

        if action == "create_category":
            try:
                slug = validate_slug(request.form.get("slug", ""))
                parent_id = _optional_uuid(request.form.get("parent_id", ""))
            except ValueError as exc:
                flash(str(exc) or "Проверьте данные рубрики", "error")
                return _content_redirect(category_id=return_category_id)

            category = CatalogService.create_category(
                db_session,
                {
                    "title": request.form.get("title", "").strip(),
                    "slug": slug,
                    "description": request.form.get("description", "").strip(),
                    "parent_id": parent_id,
                },
            )
            if category:
                flash("Рубрика создана", "success")
                return _content_redirect(category_id=category.id)

            flash("Не удалось создать рубрику: проверьте название, URL и родительскую рубрику", "error")
            return _content_redirect(category_id=return_category_id)

        if action == "update_category":
            try:
                category_id = UUID(request.form.get("category_id", "").strip())
                slug = validate_slug(request.form.get("slug", ""))
                parent_id = _optional_uuid(request.form.get("parent_id", ""))
            except ValueError as exc:
                flash(str(exc) or "Проверьте данные рубрики", "error")
                return _content_redirect(category_id=return_category_id)

            updated = CatalogService.update_category(
                db_session,
                category_id,
                {
                    "title": request.form.get("title", "").strip(),
                    "slug": slug,
                    "description": request.form.get("description", "").strip(),
                    "parent_id": parent_id,
                },
            )
            if updated:
                flash("Рубрика обновлена", "success")
                return _content_redirect(category_id=category_id)

            flash("Рубрику не удалось обновить: проверьте URL и иерархию", "error")
            return _content_redirect(category_id=return_category_id, edit_category=category_id)

        if action == "delete_category":
            try:
                category_id = UUID(request.form.get("category_id", "").strip())
            except ValueError:
                flash("Некорректная рубрика", "error")
                return _content_redirect(category_id=return_category_id)

            if CatalogService.delete_category(db_session, category_id):
                flash("Рубрика удалена", "success")
                if return_category_id == category_id:
                    return_category_id = None
            else:
                flash(
                    "Рубрику нельзя удалить: сначала удалите или перенесите публикации и дочерние рубрики",
                    "error",
                )
            return _content_redirect(category_id=return_category_id)

        abort(400)


class CreatePost(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session):
        categories = db_session.query(Category).order_by(Category.title).all()
        selected_category_id = ""
        category_raw = request.args.get("category_id", "").strip()
        if category_raw:
            try:
                category_id = UUID(category_raw)
                if Category.get_by_id(db_session, category_id) is not None:
                    selected_category_id = str(category_id)
            except ValueError:
                pass

        return render_template(
            "dashboard/publication/edit.html",
            categories=categories,
            selected_category_id=selected_category_id,
        )

    @login_required
    @with_db_session
    def post(self, db_session: Session):
        try:
            data = _publication_payload(PublicationCreate)
        except (ValidationError, ValueError) as exc:
            message = _validation_message(exc) if isinstance(exc, ValidationError) else str(exc)
            flash(message, "error")
            return redirect(url_for("admin.publication.create"))

        reference_error = _validate_publication_references(db_session, data)
        if reference_error:
            flash(reference_error, "error")
            return redirect(url_for("admin.publication.create"))

        if db_session.query(Publication).filter(Publication.slug == data.slug).first():
            flash("Публикация с таким URL уже существует", "error")
            return redirect(url_for("admin.publication.create"))

        publication = PublicationService.create_publication(db_session, data)
        if publication is None:
            flash("Не удалось создать публикацию", "error")
            return redirect(url_for("admin.publication.create"))

        flash("Публикация сохранена", "success")
        return redirect(url_for("admin.publication.edit", id=publication.id))


class CheckSlug(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session, slug: str):
        try:
            original = validate_slug(slug)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        candidate = original
        counter = 1
        while db_session.query(Publication).filter(Publication.slug == candidate).first():
            suffix = f"-{counter}"
            candidate = f"{original[:255 - len(suffix)].rstrip('-')}{suffix}"
            counter += 1

        return jsonify({"slug": candidate})


class UpdatePost(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session, id: UUID):
        publication = PublicationService.get_publication(db_session, id)
        if publication is None:
            abort(404)

        categories = db_session.query(Category).order_by(Category.title).all()
        return render_template(
            "dashboard/publication/edit.html",
            categories=categories,
            publication=publication,
            selected_category_id="",
        )

    @login_required
    @with_db_session
    def post(self, db_session: Session, id: UUID):
        if Publication.get_by_id(db_session, id) is None:
            abort(404)

        try:
            data = _publication_payload(PublicationUpdate)
        except (ValidationError, ValueError) as exc:
            message = _validation_message(exc) if isinstance(exc, ValidationError) else str(exc)
            flash(message, "error")
            return redirect(url_for("admin.publication.edit", id=id))

        reference_error = _validate_publication_references(db_session, data)
        if reference_error:
            flash(reference_error, "error")
            return redirect(url_for("admin.publication.edit", id=id))

        existing = db_session.query(Publication).filter(Publication.slug == data.slug).first()
        if existing is not None and existing.id != id:
            flash("Публикация с таким URL уже существует", "error")
            return redirect(url_for("admin.publication.edit", id=id))

        publication = PublicationService.update_publication(db_session, id, data)
        if publication is None:
            flash("Не удалось обновить публикацию", "error")
            return redirect(url_for("admin.publication.edit", id=id))

        flash("Публикация сохранена", "success")
        return redirect(url_for("admin.publication.edit", id=publication.id))


class DeletePost(MethodView):
    @login_required
    @with_db_session
    def post(self, db_session: Session, id: UUID):
        publication = Publication.get_by_id(db_session, id)
        return_category_id = publication.category_id if publication else None
        if not PublicationService.delete_publication(db_session, id):
            flash("Публикация не найдена", "error")
        else:
            flash("Публикация удалена", "success")
        return _content_redirect(category_id=return_category_id)
