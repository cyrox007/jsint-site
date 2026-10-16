from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

from flask import abort, flash, redirect, render_template, request, url_for
from flask.views import MethodView
from sqlalchemy.orm import Session

from cache.manager import cache
from components.auth.decorator import login_required, with_db_session
from components.security.html import sanitize_rich_text
from models.categories import Category
from models.publication import Publication, PublicationSite
from services.media import MediaService
from services.publication import PublicationService
from services.publication_channel import PublicationChannelService
from services.publication_profile import (
    build_profile,
    profile_for_editor,
    public_profile,
    schemas_for_site,
    set_profile,
)
from services.site import SiteService
from services.yandex_indexing import YandexIndexingService
from utils.validation import validate_slug
from views.dashboard.blog.views import _publication_public_urls


_ALLOWED_SOURCE_TYPES = {"article", "lecture", "task", "case", "changelog"}


def _site_from_raw(db_session: Session, raw: str | None):
    """Возвращает сайт редактора без изменения глобального контекста админки."""
    try:
        site_id = UUID((raw or "").strip())
    except (TypeError, ValueError):
        return None
    return SiteService.get_by_id(db_session, site_id)


def _placement_for_site(
    db_session: Session,
    publication_id: UUID,
    site_id: UUID,
) -> PublicationSite | None:
    return (
        db_session.query(PublicationSite)
        .filter(
            PublicationSite.publication_id == publication_id,
            PublicationSite.site_id == site_id,
        )
        .first()
    )


def _editor_publication(publication: Publication, placement: PublicationSite):
    """Собирает представление публикации в контуре выбранного сайта."""
    return SimpleNamespace(
        id=publication.id,
        site_id=placement.site_id,
        title=publication.title,
        content=publication.content,
        source_type=publication.source_type,
        extra_data=publication.extra_data or {},
        category_id=placement.category_id,
        category=placement.category,
        slug=placement.slug,
        is_published=placement.is_published,
        published_at=placement.published_at,
        created_at=publication.created_at,
        updated_at=publication.updated_at,
    )


def _form_values(db_session: Session, publication: Publication, site):
    title = request.form.get("title", "").strip()
    content = sanitize_rich_text(request.form.get("content", "").strip())
    source_type = request.form.get("source-type", "article").strip()
    slug = validate_slug(request.form.get("slug", ""))
    is_published = request.form.get("is_published") == "on"

    if not title:
        raise ValueError("Укажите название публикации")
    if len(title) > 255:
        raise ValueError("Название публикации слишком длинное")
    if not content:
        raise ValueError("Добавьте текст публикации")
    if len(content) > 500_000:
        raise ValueError("Текст публикации слишком большой")
    if source_type not in _ALLOWED_SOURCE_TYPES:
        raise ValueError("Неизвестный тип публикации")

    category_raw = request.form.get("category_id", "").strip()
    try:
        category_id = UUID(category_raw) if category_raw else None
    except ValueError as exc:
        raise ValueError("Некорректная рубрика") from exc

    if category_id is not None and Category.get_by_id(
        db_session,
        category_id,
        site.id,
    ) is None:
        raise ValueError("Выбранная рубрика не принадлежит этому сайту")
    if is_published and category_id is None:
        raise ValueError("Для публикации материала выберите рубрику")

    duplicate = (
        db_session.query(PublicationSite)
        .filter(
            PublicationSite.site_id == site.id,
            PublicationSite.slug == slug,
            PublicationSite.publication_id != publication.id,
        )
        .first()
    )
    if duplicate is not None:
        raise ValueError("На этом сайте уже используется такой URL публикации")

    extra_data = dict(publication.extra_data or {})
    extra_data["seo_title"] = request.form.get("seo_title", "").strip()[:255]
    extra_data["seo_description"] = request.form.get("seo_description", "").strip()[:320]

    profile_schema = schemas_for_site(site.key).get(source_type)
    profile_values = {}
    if profile_schema is not None:
        profile_values = {
            field.name: request.form.get(f"profile_{field.name}", "")
            for field in profile_schema.fields
        }
    profile = build_profile(site.key, source_type, profile_values)
    extra_data = set_profile(extra_data, site.key, profile)

    return {
        "title": title,
        "content": content,
        "source_type": source_type,
        "slug": slug,
        "category_id": category_id,
        "is_published": is_published,
        "extra_data": extra_data,
    }


class WorkspacePost(MethodView):
    """Редактор одной публикации в контуре конкретного сайта."""

    @login_required
    @with_db_session
    def get(self, db_session: Session, id: UUID):
        publication = Publication.get_by_id(db_session, id)
        if publication is None:
            abort(404)

        selected_site = _site_from_raw(db_session, request.args.get("site_id"))
        if selected_site is None:
            selected_site = SiteService.get_by_id(db_session, publication.site_id)
        if selected_site is None:
            abort(404)

        placement = _placement_for_site(db_session, id, selected_site.id)
        if placement is None:
            abort(404)

        categories = (
            db_session.query(Category)
            .filter(Category.site_id == selected_site.id)
            .order_by(Category.title)
            .all()
        )
        editor_publication = _editor_publication(publication, placement)

        return render_template(
            "dashboard/publication/edit.html",
            categories=categories,
            publication=editor_publication,
            selected_category_id="",
            selected_site=selected_site,
            workspace_site=selected_site,
            preview_url=url_for(
                "admin.publication.workspace_preview",
                id=publication.id,
                site_id=selected_site.id,
            ),
            media_assets=MediaService.list_for_site(db_session, selected_site.id),
            media_service=MediaService,
            profile_schemas=schemas_for_site(selected_site.key),
            profile_data=profile_for_editor(publication.extra_data, selected_site.key),
        )

    @login_required
    @with_db_session
    def post(self, db_session: Session, id: UUID):
        publication = Publication.get_by_id(db_session, id)
        if publication is None:
            abort(404)

        selected_site = _site_from_raw(db_session, request.form.get("site_id"))
        if selected_site is None:
            abort(400)

        placement = _placement_for_site(db_session, id, selected_site.id)
        if placement is None:
            abort(404)

        try:
            values = _form_values(db_session, publication, selected_site)
        except ValueError as exc:
            flash(str(exc) or "Проверьте заполненные поля", "error")
            return redirect(
                url_for(
                    "admin.publication.workspace_edit",
                    id=id,
                    site_id=selected_site.id,
                )
            )

        previous_index_urls = _publication_public_urls(db_session, id)

        publication.title = values["title"]
        publication.content = values["content"]
        publication.source_type = values["source_type"]
        publication.extra_data = values["extra_data"]
        db_session.add(publication)

        if selected_site.id == publication.site_id:
            publication.slug = values["slug"]
            publication.category_id = values["category_id"]
            publication.is_published = values["is_published"]
            if publication.is_published and not publication.published_at:
                publication.published_at = datetime.now(timezone.utc)
            elif not publication.is_published:
                publication.published_at = None
            PublicationChannelService.sync_owner(db_session, publication)
        else:
            PublicationChannelService.set_placement(
                db_session,
                publication_id=publication.id,
                site_id=selected_site.id,
                slug=values["slug"],
                category_id=values["category_id"],
                is_published=values["is_published"],
            )

        db_session.commit()
        cache.invalidate("publications")

        YandexIndexingService.enqueue(
            previous_index_urls + _publication_public_urls(db_session, id)
        )
        flash(f"Публикация сохранена для сайта «{selected_site.name}»", "success")
        return redirect(
            url_for(
                "admin.publication.workspace_edit",
                id=id,
                site_id=selected_site.id,
            )
        )


class WorkspacePreviewPost(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session, id: UUID):
        publication = Publication.get_by_id(db_session, id)
        selected_site = _site_from_raw(db_session, request.args.get("site_id"))
        if publication is None or selected_site is None:
            abort(404)

        placement = _placement_for_site(db_session, id, selected_site.id)
        if placement is None:
            abort(404)

        return render_template(
            "dashboard/publication/preview.html",
            publication=_editor_publication(publication, placement),
            selected_site=selected_site,
            profile=public_profile(publication.extra_data or {}, selected_site.key),
            preview_edit_url=url_for(
                "admin.publication.workspace_edit",
                id=id,
                site_id=selected_site.id,
            ),
        )


class WorkspaceDeletePost(MethodView):
    @login_required
    @with_db_session
    def post(self, db_session: Session, id: UUID):
        publication = Publication.get_by_id(db_session, id)
        selected_site = _site_from_raw(
            db_session,
            request.form.get("site_id") or request.args.get("site_id"),
        )
        if publication is None or selected_site is None:
            abort(404)

        placement = _placement_for_site(db_session, id, selected_site.id)
        if placement is None:
            abort(404)

        previous_index_urls = _publication_public_urls(db_session, id)
        if selected_site.id == publication.site_id:
            if not PublicationService.delete_publication(db_session, id):
                flash("Публикация не найдена", "error")
            else:
                YandexIndexingService.enqueue(previous_index_urls)
                flash("Публикация удалена", "success")
        else:
            PublicationChannelService.remove_placement(
                db_session,
                publication_id=id,
                site_id=selected_site.id,
            )
            publication.extra_data = set_profile(
                publication.extra_data,
                selected_site.key,
                None,
            )
            db_session.add(publication)
            db_session.commit()
            cache.invalidate("publications")
            YandexIndexingService.enqueue(previous_index_urls)
            flash(f"Размещение на сайте «{selected_site.name}» удалено", "success")

        return redirect(url_for("admin.publication.index", site_id=selected_site.id))
