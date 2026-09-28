from __future__ import annotations

import re

from uuid import UUID

from flask import abort, flash, jsonify, redirect, render_template, request, session, url_for
from flask.views import MethodView
from pydantic import ValidationError
from sqlalchemy.orm import Session

from components.admin.site_context import resolve_admin_site
from components.auth.decorator import login_required, with_db_session
from components.security.html import sanitize_rich_text
from models.categories import Category
from models.publication import Publication
from schemas.publication import PublicationCreate, PublicationUpdate
from services.catalog import CatalogService
from services.media import MediaService
from services.publication import PublicationService
from services.publication_profile import (
    build_profile,
    profile_for_editor,
    public_profile,
    schemas_for_site,
)
from services.publication_channel import PublicationChannelService
from services.site import SiteService
from utils.validation import validate_slug


def _site_from_raw(db_session: Session, raw: str | None, *, fallback: bool = True):
    return resolve_admin_site(db_session, raw, fallback=fallback)


def _publication_payload(schema_cls, site):
    content = sanitize_rich_text(request.form.get("content", "").strip())
    source_type = request.form.get("source-type", "article").strip()
    profile_schemas = schemas_for_site(site.key)
    selected_schema = profile_schemas.get(source_type)
    profile_values = {}
    if selected_schema is not None:
        profile_values = {
            field.name: request.form.get(f"profile_{field.name}", "")
            for field in selected_schema.fields
        }

    extra_data = {
        "seo_title": request.form.get("seo_title", "").strip()[:255],
        "seo_description": request.form.get("seo_description", "").strip()[:320],
    }
    profile = build_profile(site.key, source_type, profile_values)
    if profile is not None:
        extra_data["profile"] = profile

    return schema_cls(
        site_id=site.id,
        title=request.form.get("title", "").strip(),
        slug=request.form.get("slug", "").strip(),
        content=content,
        source_type=source_type,
        extra_data=extra_data,
        category_id=request.form.get("category_id", ""),
        author_id=session.get("user_id"),
        is_published=request.form.get("is_published") == "on",
        technology_ids=[],
    )


def _validate_publication_references(db_session: Session, data) -> str | None:
    if data.category_id is not None:
        category = Category.get_by_id(db_session, data.category_id, data.site_id)
        if category is None:
            return "Выбранная рубрика не существует на этом сайте"
    if data.is_published and data.category_id is None:
        return "Для публикации материала выберите рубрику"
    return None


def _validation_message(exc: ValidationError) -> str:
    first = exc.errors()[0] if exc.errors() else {}
    return str(first.get("msg") or "Проверьте заполненные поля")


def _optional_uuid(raw: str) -> UUID | None:
    raw = raw.strip()
    return UUID(raw) if raw else None


def _content_redirect(
    *,
    site_id: UUID | str,
    category_id: UUID | str | None = None,
    edit_category: UUID | str | None = None,
):
    values = {"site_id": str(site_id)}
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


def _sync_additional_placements(
    db_session: Session,
    publication: Publication,
) -> None:
    for site in SiteService.list_sites(db_session):
        if site.id == publication.site_id:
            continue

        prefix = f"placement_{site.id}"
        enabled = request.form.get(f"{prefix}_enabled") == "on"
        if not enabled:
            PublicationChannelService.remove_placement(
                db_session,
                publication_id=publication.id,
                site_id=site.id,
            )
            continue

        category_raw = request.form.get(f"{prefix}_category_id", "").strip()
        try:
            category_id = UUID(category_raw) if category_raw else None
        except ValueError as exc:
            raise ValueError(f"{site.name}: некорректная рубрика") from exc

        slug = request.form.get(f"{prefix}_slug", "").strip() or publication.slug
        PublicationChannelService.set_placement(
            db_session,
            publication_id=publication.id,
            site_id=site.id,
            slug=slug,
            category_id=category_id,
            is_published=request.form.get(f"{prefix}_published") == "on",
        )


class PublicationListPage(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session):
        selected_site = _site_from_raw(db_session, request.args.get("site_id"))
        selected_category_id = ""
        category_ids: list[UUID] | None = None
        search = request.args.get("search", "").strip()[:200] or None

        status = request.args.get("status", "").strip()
        publication_status: bool | None = None
        if status == "published":
            publication_status = True
        elif status == "draft":
            publication_status = False

        category_raw = request.args.get("category_id", "").strip()
        if category_raw:
            try:
                category_id = UUID(category_raw)
                selected = Category.get_by_id(db_session, category_id, selected_site.id)
                if selected is None:
                    flash("Выбранная рубрика не найдена на этом сайте", "error")
                else:
                    descendants = Category.get_all_descendants(db_session, category_id)
                    category_ids = [category_id, *[item.id for item in descendants]]
                    selected_category_id = str(category_id)
            except ValueError:
                flash("Некорректный фильтр рубрики", "error")

        publications = PublicationChannelService.list_for_admin(
            db_session,
            site_id=selected_site.id,
            is_published=publication_status,
            category_ids=category_ids,
            search=search,
        )
        categories = (
            db_session.query(Category)
            .filter(Category.site_id == selected_site.id)
            .order_by(Category.title)
            .all()
        )

        total_publications = PublicationChannelService.count_for_admin(
            db_session,
            site_id=selected_site.id,
        )
        count_rows = PublicationChannelService.category_counts(
            db_session,
            site_id=selected_site.id,
        )
        direct_counts = {str(category_id): int(count) for category_id, count in count_rows}
        category_tree = _tree_with_counts(
            Category.get_tree(db_session, selected_site.id),
            direct_counts,
        )
        category_parent_ids = {
            str(category.id): str(category.parent_id or "") for category in categories
        }

        edit_category_id = request.args.get("edit_category", "").strip()
        if edit_category_id:
            try:
                edit_id = UUID(edit_category_id)
                if Category.get_by_id(db_session, edit_id, selected_site.id) is None:
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
            sites=SiteService.list_sites(db_session),
            selected_site=selected_site,
        )

    @login_required
    @with_db_session
    def post(self, db_session: Session):
        selected_site = _site_from_raw(
            db_session,
            request.form.get("site_id"),
            fallback=False,
        )
        if selected_site is None:
            abort(400)

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
                return _content_redirect(
                    site_id=selected_site.id,
                    category_id=return_category_id,
                )

            category = CatalogService.create_category(
                db_session,
                {
                    "site_id": selected_site.id,
                    "title": request.form.get("title", "").strip(),
                    "slug": slug,
                    "description": request.form.get("description", "").strip(),
                    "parent_id": parent_id,
                },
            )
            if category:
                flash("Рубрика создана", "success")
                return _content_redirect(
                    site_id=selected_site.id,
                    category_id=category.id,
                )

            flash("Не удалось создать рубрику: проверьте название, URL и иерархию", "error")
            return _content_redirect(
                site_id=selected_site.id,
                category_id=return_category_id,
            )

        if action == "update_category":
            try:
                category_id = UUID(request.form.get("category_id", "").strip())
                slug = validate_slug(request.form.get("slug", ""))
                parent_id = _optional_uuid(request.form.get("parent_id", ""))
            except ValueError as exc:
                flash(str(exc) or "Проверьте данные рубрики", "error")
                return _content_redirect(
                    site_id=selected_site.id,
                    category_id=return_category_id,
                )

            category = Category.get_by_id(db_session, category_id, selected_site.id)
            if category is None:
                abort(404)

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
                return _content_redirect(
                    site_id=selected_site.id,
                    category_id=category_id,
                )

            flash("Рубрику не удалось обновить: проверьте URL и иерархию", "error")
            return _content_redirect(
                site_id=selected_site.id,
                category_id=return_category_id,
                edit_category=category_id,
            )

        if action == "delete_category":
            try:
                category_id = UUID(request.form.get("category_id", "").strip())
            except ValueError:
                flash("Некорректная рубрика", "error")
                return _content_redirect(
                    site_id=selected_site.id,
                    category_id=return_category_id,
                )

            if Category.get_by_id(db_session, category_id, selected_site.id) is None:
                abort(404)

            if CatalogService.delete_category(db_session, category_id):
                flash("Рубрика удалена", "success")
                if return_category_id == category_id:
                    return_category_id = None
            else:
                flash(
                    "Рубрику нельзя удалить: сначала удалите или перенесите публикации и дочерние рубрики",
                    "error",
                )
            return _content_redirect(
                site_id=selected_site.id,
                category_id=return_category_id,
            )

        abort(400)


class CreatePost(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session):
        selected_site = _site_from_raw(db_session, request.args.get("site_id"))
        categories = (
            db_session.query(Category)
            .filter(Category.site_id == selected_site.id)
            .order_by(Category.title)
            .all()
        )
        selected_category_id = ""
        category_raw = request.args.get("category_id", "").strip()
        if category_raw:
            try:
                category_id = UUID(category_raw)
                if Category.get_by_id(db_session, category_id, selected_site.id) is not None:
                    selected_category_id = str(category_id)
            except ValueError:
                pass

        return render_template(
            "dashboard/publication/edit.html",
            categories=categories,
            selected_category_id=selected_category_id,
            selected_site=selected_site,
            media_assets=MediaService.list_for_site(db_session, selected_site.id),
            media_service=MediaService,
            profile_schemas=schemas_for_site(selected_site.key),
            profile_data={},
        )

    @login_required
    @with_db_session
    def post(self, db_session: Session):
        selected_site = _site_from_raw(
            db_session,
            request.form.get("site_id"),
            fallback=False,
        )
        if selected_site is None:
            abort(400)

        try:
            data = _publication_payload(PublicationCreate, selected_site)
        except (ValidationError, ValueError) as exc:
            message = _validation_message(exc) if isinstance(exc, ValidationError) else str(exc)
            flash(message, "error")
            return redirect(url_for("admin.publication.create", site_id=selected_site.id))

        reference_error = _validate_publication_references(db_session, data)
        if reference_error:
            flash(reference_error, "error")
            return redirect(url_for("admin.publication.create", site_id=selected_site.id))

        if Publication.get_by_slug(db_session, data.slug, selected_site.id):
            flash("На этом сайте уже есть публикация с таким URL", "error")
            return redirect(url_for("admin.publication.create", site_id=selected_site.id))

        publication = PublicationService.create_publication(db_session, data)
        if publication is None:
            flash("Не удалось создать публикацию", "error")
            return redirect(url_for("admin.publication.create", site_id=selected_site.id))

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

        selected_site = _site_from_raw(db_session, request.args.get("site_id"))
        candidate = original
        counter = 1
        while Publication.get_by_slug(db_session, candidate, selected_site.id):
            suffix = f"-{counter}"
            candidate = f"{original[:255 - len(suffix)].rstrip('-')}{suffix}"
            counter += 1
        return jsonify({"slug": candidate})


class UpdatePost(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session, id: UUID):
        publication_model = Publication.get_by_id(db_session, id)
        if publication_model is None:
            abort(404)

        publication = PublicationService.get_publication(db_session, id)
        selected_site = SiteService.get_by_id(db_session, publication_model.site_id)
        if publication is None or selected_site is None:
            abort(404)

        categories = (
            db_session.query(Category)
            .filter(Category.site_id == selected_site.id)
            .order_by(Category.title)
            .all()
        )
        sites = SiteService.list_sites(db_session)
        placements = PublicationChannelService.list_placements(db_session, id)
        placements_by_site = {str(item.site_id): item for item in placements}
        categories_by_site = {
            str(site.id): (
                db_session.query(Category)
                .filter(Category.site_id == site.id)
                .order_by(Category.title)
                .all()
            )
            for site in sites
        }
        workspace_site = _site_from_raw(db_session, request.args.get("site_id"))

        preview_url = url_for("admin.publication.preview", id=publication_model.id)

        return render_template(
            "dashboard/publication/edit.html",
            categories=categories,
            publication=publication,
            selected_category_id="",
            selected_site=selected_site,
            workspace_site=workspace_site,
            sites=sites,
            placements_by_site=placements_by_site,
            categories_by_site=categories_by_site,
            preview_url=preview_url,
            media_assets=MediaService.list_for_site(db_session, selected_site.id),
            media_service=MediaService,
            profile_schemas=schemas_for_site(selected_site.key),
            profile_data=profile_for_editor(publication_model.extra_data),
        )

    @login_required
    @with_db_session
    def post(self, db_session: Session, id: UUID):
        publication_model = Publication.get_by_id(db_session, id)
        if publication_model is None:
            abort(404)
        selected_site = SiteService.get_by_id(db_session, publication_model.site_id)
        if selected_site is None:
            abort(404)

        try:
            data = _publication_payload(PublicationUpdate, selected_site)
        except (ValidationError, ValueError) as exc:
            message = _validation_message(exc) if isinstance(exc, ValidationError) else str(exc)
            flash(message, "error")
            return redirect(url_for("admin.publication.edit", id=id))

        reference_error = _validate_publication_references(db_session, data)
        if reference_error:
            flash(reference_error, "error")
            return redirect(url_for("admin.publication.edit", id=id))

        existing = Publication.get_by_slug(db_session, data.slug, selected_site.id)
        if existing is not None and existing.id != id:
            flash("На этом сайте уже есть публикация с таким URL", "error")
            return redirect(url_for("admin.publication.edit", id=id))

        publication = PublicationService.update_publication(
            db_session,
            id,
            data,
            commit=False,
        )
        if publication is None:
            flash("Не удалось обновить публикацию", "error")
            return redirect(url_for("admin.publication.edit", id=id))

        publication_model = Publication.get_by_id(db_session, id)
        try:
            _sync_additional_placements(db_session, publication_model)
            db_session.commit()
        except ValueError as exc:
            db_session.rollback()
            flash(str(exc), "error")
            return redirect(url_for("admin.publication.edit", id=id))

        flash("Публикация и размещения сохранены", "success")
        return redirect(url_for("admin.publication.edit", id=publication.id))


class PreviewPost(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session, id: UUID):
        publication = Publication.get_by_id(db_session, id)
        if publication is None:
            abort(404)

        site_model = SiteService.get_by_id(db_session, publication.site_id)
        if site_model is None:
            abort(404)

        extra = publication.extra_data or {}
        edit_url = url_for("admin.publication.edit", id=publication.id)

        if not site_model.is_default:
            return render_template(
                "dashboard/publication/preview.html",
                publication=publication,
                selected_site=site_model,
                profile=public_profile(extra),
                preview_edit_url=edit_url,
            )

        site = SiteService.public_config(site_model)
        plain_text = re.sub(r"<[^>]+>", " ", publication.content or "")
        plain_text = re.sub(r"\s+", " ", plain_text).strip()
        return render_template(
            "public/articles/detail.html",
            site=site,
            publication=publication,
            seo_title=(extra.get("seo_title") or publication.title).strip(),
            seo_description=(extra.get("seo_description") or plain_text[:180]).strip(),
            canonical_url=None,
            og_type="article",
            preview_mode=True,
            preview_edit_url=edit_url,
        )


class DeletePost(MethodView):
    @login_required
    @with_db_session
    def post(self, db_session: Session, id: UUID):
        publication = Publication.get_by_id(db_session, id)
        if publication is None:
            flash("Публикация не найдена", "error")
            return _content_redirect(site_id=SiteService.get_default(db_session).id)

        site_id = publication.site_id
        return_category_id = publication.category_id
        if not PublicationService.delete_publication(db_session, id):
            flash("Публикация не найдена", "error")
        else:
            flash("Публикация удалена", "success")
        return _content_redirect(site_id=site_id, category_id=return_category_id)
