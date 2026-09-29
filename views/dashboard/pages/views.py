from __future__ import annotations

from urllib.parse import urlparse
from uuid import UUID

from flask import abort, flash, redirect, render_template, request, url_for
from flask.views import MethodView
from sqlalchemy.orm import Session

from components.admin.site_context import resolve_admin_site
from components.auth.decorator import login_required, with_db_session
from components.security.html import sanitize_rich_text
from services.page import GENERIC_BLOCK_LABELS, GENERIC_BLOCK_TYPES, PageService
from services.site import SiteService
from services.yandex_indexing import YandexIndexingService


def _safe_href(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if value.startswith(("#", "/")):
        return value
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return value
    if parsed.scheme == "mailto" and parsed.path:
        return value
    raise ValueError(f"Недопустимая ссылка: {value}")


def _block_settings(block_type: str) -> dict:
    if block_type == "rich_text":
        return {
            "title": request.form.get("block_title", "").strip()[:200],
            "body": sanitize_rich_text(request.form.get("block_body", "").strip()),
        }

    if block_type == "publication_feed":
        try:
            limit = int(request.form.get("block_limit", "6"))
        except ValueError as exc:
            raise ValueError("Количество публикаций должно быть числом") from exc
        return {
            "title": request.form.get("block_title", "").strip()[:200],
            "source_type": request.form.get("block_source_type", "").strip()[:80],
            "category": request.form.get("block_category", "").strip()[:255],
            "limit": max(1, min(limit, 50)),
        }

    if block_type == "callout":
        return {
            "title": request.form.get("block_title", "").strip()[:200],
            "text": request.form.get("block_text", "").strip()[:2000],
            "label": request.form.get("block_label", "").strip()[:120],
            "href": _safe_href(request.form.get("block_href", "")),
        }

    if block_type == "links":
        items: list[dict[str, str]] = []
        for line in request.form.get("block_links", "").splitlines():
            line = line.strip()
            if not line:
                continue
            label, separator, href = line.partition("|")
            if not separator or not label.strip() or not href.strip():
                raise ValueError("Ссылки: используйте формат «Название|ссылка», одна строка на ссылку")
            items.append({
                "label": label.strip()[:120],
                "href": _safe_href(href),
            })
        return {
            "title": request.form.get("block_title", "").strip()[:200],
            "items": items[:40],
        }

    raise ValueError("Неизвестный тип блока")


class PageList(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session):
        site = resolve_admin_site(db_session, request.args.get("site_id"))
        return render_template(
            "dashboard/pages/index.html",
            selected_site=site,
            sites=SiteService.list_sites(db_session),
            pages=PageService.list_pages(db_session, site.id),
        )

    @login_required
    @with_db_session
    def post(self, db_session: Session):
        site = resolve_admin_site(db_session, request.form.get("site_id"))
        try:
            page = PageService.create_page(
                db_session,
                site.id,
                slug=request.form.get("slug", ""),
                title=request.form.get("title", ""),
                seo_title=request.form.get("seo_title", ""),
                seo_description=request.form.get("seo_description", ""),
                is_published=request.form.get("is_published") == "on",
            )
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("admin.pages.index", site_id=site.id))

        flash("Страница создана", "success")
        return redirect(url_for("admin.pages.edit", page_id=page.id))


class PageEdit(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session, page_id: UUID):
        page = PageService.get_by_id(db_session, page_id)
        if page is None:
            abort(404)
        site = SiteService.get_by_id(db_session, page.site_id)
        if site is None:
            abort(404)
        resolve_admin_site(db_session, site.id)

        return render_template(
            "dashboard/pages/edit.html",
            page=page,
            selected_site=site,
            blocks=PageService.list_blocks(page),
            generic_block_types=GENERIC_BLOCK_TYPES,
            generic_block_labels=GENERIC_BLOCK_LABELS,
        )

    @login_required
    @with_db_session
    def post(self, db_session: Session, page_id: UUID):
        page = PageService.get_by_id(db_session, page_id)
        if page is None:
            abort(404)
        resolve_admin_site(db_session, page.site_id)

        action = request.form.get("action", "update_page").strip()
        try:
            if action == "update_page":
                PageService.update_page(
                    db_session,
                    page,
                    slug=request.form.get("slug", ""),
                    title=request.form.get("title", ""),
                    seo_title=request.form.get("seo_title", ""),
                    seo_description=request.form.get("seo_description", ""),
                    is_published=request.form.get("is_published") == "on",
                )
                flash("Настройки страницы сохранены", "success")

            elif action == "add_block":
                block_type = request.form.get("block_type", "").strip()
                PageService.add_block(
                    db_session,
                    page,
                    block_type=block_type,
                    settings=_block_settings(block_type),
                    is_enabled=True,
                )
                flash("Блок добавлен", "success")

            elif action in {"update_block", "delete_block"}:
                block_id = UUID(request.form.get("block_id", "").strip())
                block = PageService.get_block(db_session, page.id, block_id)
                if block is None:
                    abort(404)

                if action == "delete_block":
                    PageService.delete_block(db_session, block)
                    flash("Блок удалён", "success")
                else:
                    PageService.update_block(
                        db_session,
                        block,
                        position=int(request.form.get("position", "100")),
                        settings=_block_settings(block.block_type),
                        is_enabled=request.form.get("is_enabled") == "on",
                    )
                    flash("Блок сохранён", "success")

            elif action == "delete_page":
                site_id = page.site_id
                PageService.delete_page(db_session, page)
                flash("Страница удалена", "success")
                return redirect(url_for("admin.pages.index", site_id=site_id))

            else:
                abort(400)

        except (ValueError, TypeError) as exc:
            flash(str(exc) or "Проверьте данные", "error")

        if page.slug == "home" and page.is_published:
            site = SiteService.get_by_id(db_session, page.site_id)
            if site is not None and site.is_active:
                base_url = (
                    SiteService.public_config(site).get("base_url") or ""
                ).rstrip("/")
                if base_url:
                    YandexIndexingService.enqueue([f"{base_url}/"])

        return redirect(url_for("admin.pages.edit", page_id=page.id))
