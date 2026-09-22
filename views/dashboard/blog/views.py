from __future__ import annotations

from uuid import UUID

from flask import abort, flash, jsonify, redirect, render_template, request, session, url_for
from flask.views import MethodView
from pydantic import ValidationError
from sqlalchemy.orm import Session

from components.auth.decorator import login_required, with_db_session
from components.security.html import sanitize_rich_text
from models.categories import Category
from models.publication import Publication
from schemas.publication import PublicationCreate, PublicationUpdate
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
        return "Выбранная категория не существует"
    if data.is_published and data.category_id is None:
        return "Для публикации материала выберите категорию"
    return None


def _validation_message(exc: ValidationError) -> str:
    first = exc.errors()[0] if exc.errors() else {}
    return str(first.get("msg") or "Проверьте заполненные поля")


class PublicationListPage(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session):
        filters: dict = {"is_published": None}

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
                filters["category_id"] = UUID(category_raw)
            except ValueError:
                flash("Некорректный фильтр категории", "error")

        publications = PublicationService.get_publications(db_session, **filters)
        categories = db_session.query(Category).order_by(Category.title).all()
        category_tree = Category.get_tree(db_session)
        selected_category_id = str(filters.get("category_id") or "")
        return render_template(
            "dashboard/publication/index.html",
            publications=publications,
            categories=categories,
            category_tree=category_tree,
            selected_category_id=selected_category_id,
        )


class CreatePost(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session):
        categories = db_session.query(Category).order_by(Category.title).all()
        return render_template("dashboard/publication/edit.html", categories=categories)

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
        if not PublicationService.delete_publication(db_session, id):
            flash("Публикация не найдена", "error")
        else:
            flash("Публикация удалена", "success")
        return redirect(url_for("admin.publication.index"))
