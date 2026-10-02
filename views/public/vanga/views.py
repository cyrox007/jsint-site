from __future__ import annotations

import json
import socket
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import render_template, request
from flask.views import MethodView

from components.auth.decorator import with_db_session
from services.site import SiteService
from settings import config


DEFAULT_FORM = {
    "title": "",
    "director": "",
    "year": "",
    "runtime": "",
    "genres": "",
    "actors": "",
}


def _request_vanga(path: str, *, payload: dict | None = None, timeout: int | None = None) -> dict:
    url = f"{config.VANGA_DEMO_URL}{path}"
    data = None
    headers = {"Accept": "application/json"}
    method = "GET"

    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
        method = "POST"

    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout or config.VANGA_DEMO_TIMEOUT_SECONDS) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
            message = str(body.get("error") or body.get("message") or f"HTTP {exc.code}")
        except Exception:
            message = f"HTTP {exc.code}"
        raise RuntimeError(message) from exc
    except (URLError, socket.timeout, TimeoutError) as exc:
        raise RuntimeError("Демонстрационный сервис Vanga сейчас недоступен") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Vanga вернула некорректный ответ") from exc

    if not isinstance(result, dict):
        raise RuntimeError("Vanga вернула некорректный ответ")
    return result


class VangaDemoPage(MethodView):
    decorators = [with_db_session]

    def _base_context(self, db_session):
        site_model = SiteService.get_default(db_session)
        site = SiteService.public_config(site_model)

        service_ready = False
        service_status = "Сервис недоступен"
        try:
            health = _request_vanga("/health", timeout=2)
            service_ready = bool(health.get("ok"))
            service_status = "Модель готова" if service_ready else "Модель временно недоступна"
        except RuntimeError:
            pass

        canonical_url = (
            f"{site['base_url']}/projects/vanga"
            if site["base_url"]
            else "/projects/vanga"
        )
        return {
            "site": site,
            "seo_title": "Прогноз рейтинга фильма до выхода — Vanga",
            "seo_description": (
                "Попробуйте спрогнозировать рейтинг ещё не вышедшего фильма "
                "по режиссёру, актёрам, жанру, году и длительности."
            ),
            "canonical_url": canonical_url,
            "seo_noindex": True,
            "service_ready": service_ready,
            "service_status": service_status,
        }

    def get(self, db_session):
        return render_template(
            "public/vanga/index.html",
            **self._base_context(db_session),
            form=DEFAULT_FORM,
            prediction=None,
            demo_error=None,
        )

    def post(self, db_session):
        context = self._base_context(db_session)
        form = {
            key: request.form.get(key, "").strip()
            for key in DEFAULT_FORM
        }

        try:
            year = int(form["year"])
            runtime = int(form["runtime"])
        except ValueError:
            return render_template(
                "public/vanga/index.html",
                **context,
                form=form,
                prediction=None,
                demo_error="Год и длительность должны быть целыми числами.",
            ), 400

        actors = [item.strip() for item in form["actors"].split(",") if item.strip()]
        payload = {
            "title": form["title"],
            "director": form["director"],
            "year": year,
            "runtime": runtime,
            "genres": form["genres"],
            "actors": actors[:5],
        }

        try:
            prediction = _request_vanga("/predict", payload=payload)
            if not prediction.get("ok"):
                raise RuntimeError(str(prediction.get("error") or "Не удалось получить прогноз"))
        except RuntimeError as exc:
            return render_template(
                "public/vanga/index.html",
                **context,
                form=form,
                prediction=None,
                demo_error=str(exc),
            ), 503

        return render_template(
            "public/vanga/index.html",
            **context,
            form=form,
            prediction=prediction,
            demo_error=None,
        )
