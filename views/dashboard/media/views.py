from __future__ import annotations

from uuid import UUID

from flask import abort, flash, redirect, render_template, request, session, url_for
from flask.views import MethodView
from sqlalchemy.orm import Session

from components.admin.site_context import resolve_admin_site
from components.auth.decorator import login_required, with_db_session
from services.media import MediaService
from services.site import SiteService


def _selected_site(db_session: Session, raw: str | None):
    return resolve_admin_site(db_session, raw)


def _asset_for_site(db_session: Session, asset_id: UUID, site_id: UUID):
    asset = MediaService.get(db_session, asset_id)
    if asset is None or all(site.id != site_id for site in asset.sites):
        abort(404)
    return asset


def _current_user_id() -> UUID | None:
    raw = session.get("user_id")
    if not raw:
        return None
    try:
        return UUID(str(raw))
    except ValueError:
        return None


class MediaLibraryPage(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session):
        site = _selected_site(db_session, request.args.get("site_id"))
        return render_template(
            "dashboard/media/index.html",
            selected_site=site,
            sites=SiteService.list_sites(db_session),
            assets=MediaService.list_for_site(db_session, site.id),
            media_service=MediaService,
        )

    @login_required
    @with_db_session
    def post(self, db_session: Session):
        site = _selected_site(db_session, request.form.get("site_id"))
        action = request.form.get("action", "upload").strip()

        if action == "upload":
            upload = request.files.get("file")
            if upload is None:
                flash("Выберите изображение", "error")
                return redirect(url_for("admin.media.index", site_id=site.id))
            try:
                asset = MediaService.upload_image(
                    db_session,
                    site=site,
                    upload=upload,
                    created_by=_current_user_id(),
                    alt_text=request.form.get("alt_text", ""),
                )
            except (ValueError, OSError) as exc:
                flash(str(exc) or "Не удалось сохранить изображение", "error")
            else:
                flash(f"Изображение «{asset.original_name}» добавлено в медиатеку", "success")
            return redirect(url_for("admin.media.index", site_id=site.id))

        try:
            asset_id = UUID(request.form.get("asset_id", "").strip())
        except ValueError:
            abort(400)
        asset = _asset_for_site(db_session, asset_id, site.id)

        if action == "update":
            site_ids: list[UUID] = []
            for raw_site_id in request.form.getlist("site_ids"):
                try:
                    site_ids.append(UUID(raw_site_id))
                except ValueError:
                    abort(400)
            try:
                MediaService.update_asset(
                    db_session,
                    asset=asset,
                    site_ids=site_ids,
                    alt_text=request.form.get("alt_text", ""),
                )
            except ValueError as exc:
                flash(str(exc), "error")
            else:
                flash("Настройки медиафайла сохранены", "success")
            return redirect(url_for("admin.media.index", site_id=site.id))

        if action == "detach":
            if MediaService.detach_or_delete(
                db_session,
                asset=asset,
                site_id=site.id,
            ):
                flash("Медиафайл убран из выбранного сайта", "success")
            return redirect(url_for("admin.media.index", site_id=site.id))

        abort(400)
