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
from services.publication import PublicationService
from utils.validation import validate_slug



def _category_tree_with_counts(db_session: Session) -> list[dict]:
    direct_counts = {
        category_id: int(count)
        for category_id, count in (
            db_session.query(Publication.category_id, func.count(Publication.id))
            .filter(Publication.category_id.is_not(None))
            .group_by(Publication.category_id)
            .all()
        )
    }
    tree = Category.get_tree(db_session)

    def attach_counts(nodes: list[dict]) -> int:
        total = 0
        for node in nodes:
            children_total = attach_counts(node["children"])
            own_count = direct_counts.get(node["id"], 0)
            node["publication_count"] = own_count + children_total
            total += node["publication_count"]
        return total

    attach_counts(tree)
    return tree

def _publication_payload(schema_cls):
    content = sanitize_rich_text(request.form.get("content", "").strip())
    return schema_cls(
        title=request.form.get("title", "").strip(),
        slug=request.form.get("slug", "").strip(),
        content=content,
        source_type=request.form.get("source-type", "article").strip(),
        extra_data={},
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
        filters: dict = {
            "is_published": None,
            "order_by": "updated_at",
            "order_direction": "desc",
        }

        search = request.args.get("search", "").strip()
        if search:
            filters["search"] = search[:200]

        status = request.args.get("status", "").strip()
        if status == "published":
            filters["is_published"] = True
        elif status == "draft":
            filters["is_published"] = False

        source_type = request.args.get("source_type", "").strip()
        if source_type in {"article", "task", "case", "changelog"}:
            filters["source_type"] = source_type

        current_category = None
        category_raw = request.args.get("category_id", "").strip()
        if category_raw:
            try:
                category_id = UUID(category_raw)
            except ValueError:
                flash("Некорректный фильтр категории", "error")
            else:
                current_category = Category.get_by_id(db_session, category_id)
                if current_category is None:
                    flash("Категория не найдена", "warning")
                else:
                    branch_ids = [current_category.id]
                    branch_ids.extend(
                        item.id for item in Category.get_all_descendants(db_session, current_category.id)
                    )
                    filters["category_ids"] = sorted(branch_ids, key=str)

        publications = PublicationService.get_publications(db_session, **filters)
        total_publications = db_session.query(Publication).count()
        return render_template(
            "dashboard/publication/index.html",
            publications=publications,
            category_tree=_category_tree_with_counts(db_session),
            current_category=current_category,
            current_category_id=current_category.id if current_category else None,
            total_publications=total_publications,
        )


class CreatePost(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session):
        categories = db_session.query(Category).order_by(Category.title).all()
        selected_category_id = None
        category_raw = request.args.get("category_id", "").strip()
        if category_raw:
            try:
                candidate = UUID(category_raw)
            except ValueError:
                pass
            else:
                if Category.get_by_id(db_session, candidate) is not None:
                    selected_category_id = candidate
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

        category_raw = request.form.get("category_id", "").strip()
        if category_raw:
            try:
                UUID(category_raw)
            except ValueError:
                category_raw = ""
        return redirect(
            url_for("admin.publication.index", category_id=category_raw or None)
        )
