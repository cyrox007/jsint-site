from __future__ import annotations

from uuid import UUID

from flask import flash, redirect, render_template, request, url_for
from flask.views import MethodView
from sqlalchemy.orm import Session

from components.auth.decorator import login_required, with_db_session
from models.sites import Site
from services.sites import SiteService


FIELDS = (
    "slug", "name", "brand_subtitle", "base_url", "contact_email", "github_url",
    "seo_title", "seo_description", "hero_badge", "hero_title", "hero_accent",
    "hero_description", "philosophy_title", "philosophy_subtitle", "philosophy_body",
    "about_title", "about_primary_title", "about_primary_body",
    "about_secondary_title", "about_secondary_body", "footer_note",
)


def payload() -> dict:
    data = {field: request.form.get(field, "") for field in FIELDS}
    data["is_active"] = request.form.get("is_active") == "on"
    data["is_default"] = request.form.get("is_default") == "on"
    return data


class SitesPage(MethodView):
    decorators = [login_required, with_db_session]

    def get(self, db_session: Session):
        selected = None
        raw_id = request.args.get("edit", "").strip()
        if raw_id:
            try:
                selected = db_session.get(Site, UUID(raw_id))
            except ValueError:
                selected = None
        return render_template("dashboard/sites/index.html", sites=SiteService.list_sites(db_session), selected_site=selected)

    def post(self, db_session: Session):
        action = request.form.get("action", "").strip()
        try:
            if action == "create":
                site = SiteService.create(db_session, payload())
                flash("Сайт создан", "success")
                return redirect(url_for("admin.sites.index", edit=site.id))
            if action == "update":
                site = db_session.get(Site, UUID(request.form.get("site_id", "")))
                if site is None:
                    raise ValueError("Сайт не найден")
                SiteService.update(db_session, site, payload())
                flash("Настройки сайта сохранены", "success")
                return redirect(url_for("admin.sites.index", edit=site.id))
            raise ValueError("Неизвестное действие")
        except (ValueError, TypeError) as exc:
            db_session.rollback()
            flash(str(exc) or "Не удалось сохранить сайт", "error")
            return redirect(url_for("admin.sites.index"))
