from __future__ import annotations

from urllib.parse import urlparse
from uuid import UUID

from flask import abort, flash, redirect, render_template, request, url_for
from flask.views import MethodView
from sqlalchemy.orm import Session

from components.auth.decorator import login_required, with_db_session
from models.categories import Category
from models.publication import Publication
from services.page import HOME_BLOCK_LABELS, HOME_BLOCK_TYPES, PageService
from services.site import SiteService


def _lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def _safe_href(value: str) -> str:
    value = value.strip()
    if value.startswith(("#", "/")):
        return value
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https", "mailto"}:
        return value
    raise ValueError(f"Недопустимая ссылка: {value}")


def _safe_http_url(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    parsed = urlparse(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError(f"Недопустимый URL: {value}")
    return value


def _parse_navigation(value: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for line in _lines(value):
        label, separator, href = line.partition("|")
        if not separator or not label.strip() or not href.strip():
            raise ValueError("Навигация: используйте формат «Название|ссылка», одна ссылка на строку")
        items.append({"label": label.strip()[:80], "href": _safe_href(href)})
    return items


def _parse_origins(value: str) -> list[str]:
    origins: list[str] = []
    for item in _lines(value):
        parsed = urlparse(item.rstrip("/"))
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise ValueError(f"Некорректный origin для API: {item}")
        origins.append(item.rstrip("/"))
    return origins


def _settings_from_form(current: dict) -> dict:
    settings = current.copy()
    settings["brand"] = {
        "name": request.form.get("brand_name", "").strip()[:120],
        "subtitle": request.form.get("brand_subtitle", "").strip()[:160],
    }
    settings["seo"] = {
        "site_name": request.form.get("seo_site_name", "").strip()[:160],
        "title": request.form.get("seo_title", "").strip()[:255],
        "description": request.form.get("seo_description", "").strip()[:320],
        "image_url": _safe_http_url(request.form.get("seo_image_url", ""))[:1000],
        "locale": request.form.get("seo_locale", "ru_RU").strip()[:20] or "ru_RU",
        "robots_index": request.form.get("seo_robots_index") == "on",
        "yandex_verification": request.form.get("seo_yandex_verification", "").strip()[:120],
    }
    settings["contact"] = {
        "email": request.form.get("contact_email", "").strip()[:255],
        "github_url": _safe_href(request.form.get("github_url", "").strip())
        if request.form.get("github_url", "").strip()
        else "",
    }
    settings["navigation"] = _parse_navigation(request.form.get("navigation", ""))
    settings.pop("hero", None)
    settings.pop("home", None)

    settings["footer"] = {
        "description": request.form.get("footer_description", "").strip()[:500],
        "location": request.form.get("footer_location", "").strip()[:160],
        "note": request.form.get("footer_note", "").strip()[:300],
    }
    settings["api"] = {
        "allowed_origins": _parse_origins(request.form.get("api_allowed_origins", "")),
    }
    return settings


def _block_states_from_form() -> dict[str, dict]:
    states: dict[str, dict] = {}
    for block_type in HOME_BLOCK_TYPES:
        raw_position = request.form.get(f"block_{block_type}_position", "100").strip()
        try:
            position = int(raw_position)
        except ValueError as exc:
            raise ValueError("Порядок блоков должен быть целым числом") from exc
        states[block_type] = {
            "position": position,
            "enabled": request.form.get(f"block_{block_type}_enabled") == "on",
        }
    return states


def _resume_settings_from_form() -> dict:
    items: list[dict] = []
    for index in range(8):
        company = request.form.get(f"resume_{index}_company", "").strip()
        if not company:
            continue
        items.append(
            {
                "company": company[:200],
                "period": request.form.get(f"resume_{index}_period", "").strip()[:200],
                "position": request.form.get(f"resume_{index}_position", "").strip()[:240],
                "description": request.form.get(f"resume_{index}_description", "").strip()[:4000],
                "achievements": _lines(
                    request.form.get(f"resume_{index}_achievements", "")
                )[:20],
                "technologies": [
                    item.strip()[:80]
                    for item in request.form.get(
                        f"resume_{index}_technologies",
                        "",
                    ).split(",")
                    if item.strip()
                ][:30],
            }
        )
    return {
        "title": request.form.get("resume_title", "").strip()[:160] or "Опыт работы",
        "subtitle": request.form.get("resume_subtitle", "").strip()[:500],
        "items": items,
    }


def _hero_metrics_from_form() -> list[dict[str, str]]:
    metrics: list[dict[str, str]] = []
    for line in _lines(request.form.get("hero_metrics", "")):
        label, separator, value = line.partition("|")
        if not separator or not label.strip() or not value.strip():
            raise ValueError("Метрики первого экрана: используйте формат «Название|Значение»")
        metrics.append(
            {
                "label": label.strip()[:80],
                "value": value.strip()[:120],
            }
        )
    return metrics[:12]


def _home_block_settings_from_form() -> dict[str, dict]:
    about_cards = [
        {
            "title": request.form.get("about_card_1_title", "").strip()[:160],
            "text": request.form.get("about_card_1_text", "").strip()[:1500],
        },
        {
            "title": request.form.get("about_card_2_title", "").strip()[:160],
            "text": request.form.get("about_card_2_text", "").strip()[:1500],
        },
    ]
    return {
        "hero": {
            "badge": request.form.get("hero_badge", "").strip()[:200],
            "title": request.form.get("hero_title", "").strip()[:200],
            "accent": request.form.get("hero_accent", "").strip()[:240],
            "description": request.form.get("hero_description", "").strip()[:3000],
            "note": request.form.get("hero_note", "").strip()[:300],
            "terminal_lines": _lines(request.form.get("hero_terminal_lines", ""))[:8],
            "metrics": _hero_metrics_from_form(),
            "tags": [
                item.strip()[:80]
                for item in request.form.get("hero_tags", "").split(",")
                if item.strip()
            ][:16],
        },
        "philosophy": {
            "title": request.form.get("philosophy_title", "").strip()[:160],
            "subtitle": request.form.get("philosophy_subtitle", "").strip()[:500],
            "text": request.form.get("philosophy_text", "").strip()[:5000],
        },
        "systems": {
            "title": request.form.get("systems_title", "").strip()[:160],
            "subtitle": request.form.get("systems_subtitle", "").strip()[:500],
        },
        "about": {
            "title": request.form.get("about_title", "").strip()[:160],
            "cards": about_cards,
        },
        "resume": _resume_settings_from_form(),
    }


class SiteListPage(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session):
        sites = SiteService.list_sites(db_session)
        counts = {
            str(site.id): {
                "categories": db_session.query(Category).filter(Category.site_id == site.id).count(),
                "publications": db_session.query(Publication).filter(Publication.site_id == site.id).count(),
            }
            for site in sites
        }
        return render_template("dashboard/sites/index.html", sites=sites, counts=counts)

    @login_required
    @with_db_session
    def post(self, db_session: Session):
        try:
            site = SiteService.create(
                db_session,
                key=request.form.get("key", ""),
                name=request.form.get("name", ""),
                base_url=request.form.get("base_url", ""),
                theme_key=request.form.get("theme_key", "ultra"),
            )
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("admin.sites.index"))

        flash("Сайт создан. Теперь настройте витрину и доступ к публичному API.", "success")
        return redirect(url_for("admin.sites.edit", site_id=site.id))


class SiteEditPage(MethodView):
    @login_required
    @with_db_session
    def get(self, db_session: Session, site_id: UUID):
        site = SiteService.get_by_id(db_session, site_id)
        if site is None:
            abort(404)

        home_page = PageService.get_page(db_session, site.id, "home")
        home_blocks = PageService.list_blocks(home_page) if home_page is not None else []
        home_block_settings = PageService.block_settings(home_page)
        resume_settings = home_block_settings["resume"]

        return render_template(
            "dashboard/sites/edit.html",
            site=site,
            site_settings=SiteService.settings(site),
            home_page=home_page,
            home_blocks=home_blocks,
            block_labels=HOME_BLOCK_LABELS,
            home_block_settings=home_block_settings,
            resume_settings=resume_settings,
            resume_items=resume_settings.get("items", []),
        )

    @login_required
    @with_db_session
    def post(self, db_session: Session, site_id: UUID):
        site = SiteService.get_by_id(db_session, site_id)
        if site is None:
            abort(404)

        try:
            settings = _settings_from_form(SiteService.settings(site))
            block_states = _block_states_from_form()
            block_settings = _home_block_settings_from_form()

            SiteService.update(
                db_session,
                site,
                name=request.form.get("name", ""),
                base_url=request.form.get("base_url", ""),
                theme_key=request.form.get("theme_key", "ultra"),
                settings=settings,
                is_active=request.form.get("is_active") == "on",
                is_default=request.form.get("is_default") == "on",
                commit=False,
            )
            PageService.update_home(
                db_session,
                site.id,
                seo_title=request.form.get("home_seo_title", ""),
                seo_description=request.form.get("home_seo_description", ""),
                block_states=block_states,
                block_settings=block_settings,
                commit=False,
            )
            db_session.commit()
        except ValueError as exc:
            db_session.rollback()
            flash(str(exc), "error")
            return redirect(url_for("admin.sites.edit", site_id=site_id))

        flash("Настройки сайта и структура главной сохранены", "success")
        return redirect(url_for("admin.sites.edit", site_id=site_id))
