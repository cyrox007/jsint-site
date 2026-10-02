from __future__ import annotations

import json
import logging
import socket
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import jsonify, render_template, request
from flask.views import MethodView

from components.auth.decorator import with_db_session
from models.vanga import VangaPrediction
from services.site import SiteService
from settings import config


logger = logging.getLogger(__name__)


DEFAULT_FORM = {
    "imdb_id": "",
    "title": "",
    "director": "",
    "year": "",
    "runtime": "",
    "genres": "",
    "actors": "",
}


PREDICTION_FEATURES = {
    "director_avg_rating": (
        "История режиссёра",
        "Средний рейтинг прошлых фильмов режиссёра, вышедших до указанного года.",
    ),
    "director_id": (
        "Паттерн режиссёра",
        "Категориальный сигнал CatBoost: модель узнаёт режиссёра как отдельную сущность и учитывает исторические закономерности.",
    ),
    "actor_1_avg_rating": (
        "История актёра №1",
        "Средний рейтинг прошлых фильмов первого указанного актёра до года прогноза.",
    ),
    "actor_2_avg_rating": (
        "История актёра №2",
        "Средний рейтинг прошлых фильмов второго указанного актёра до года прогноза.",
    ),
    "actor_3_avg_rating": (
        "История актёра №3",
        "Средний рейтинг прошлых фильмов третьего указанного актёра до года прогноза.",
    ),
    "actor_1_id": (
        "Паттерн актёра №1",
        "Категориальный сигнал первого актёра. Нулевой вклад означает, что для этого прогноза сигнал почти не изменил оценку.",
    ),
    "actor_2_id": (
        "Паттерн актёра №2",
        "Категориальный сигнал второго актёра. Нулевой вклад означает, что для этого прогноза сигнал почти не изменил оценку.",
    ),
    "actor_3_id": (
        "Паттерн актёра №3",
        "Категориальный сигнал третьего актёра. Нулевой вклад означает, что для этого прогноза сигнал почти не изменил оценку.",
    ),
    "genres_combined": (
        "Сочетание жанров",
        "То, как выбранная комбинация жанров соотносится с историческими рейтингами похожих фильмов.",
    ),
    "runtimeMinutes": (
        "Хронометраж",
        "Влияние указанной длительности фильма относительно закономерностей обучающей выборки.",
    ),
    "startYear": (
        "Год выхода",
        "Влияние года релиза и временного контекста, который модель видела в исторических данных.",
    ),
    "title_len": (
        "Длина названия",
        "Слабый текстовый признак: количество символов в названии фильма.",
    ),
    "title_word_count": (
        "Слова в названии",
        "Количество слов в названии как дополнительный статистический признак.",
    ),
    "has_colon": (
        "Двоеточие в названии",
        "Бинарный признак структуры названия: есть ли в нём двоеточие.",
    ),
    "has_digit": (
        "Цифра в названии",
        "Бинарный признак: присутствует ли цифра в названии фильма.",
    ),
    "is_bond": (
        "Связь с Bond",
        "Эвристический признак, указывающий на узнаваемый паттерн франшизы James Bond.",
    ),
    "is_dc": (
        "Связь с DC",
        "Эвристический признак, указывающий на узнаваемый паттерн DC.",
    ),
    "is_harry_potter": (
        "Связь с Harry Potter",
        "Эвристический признак, указывающий на узнаваемый паттерн франшизы Harry Potter.",
    ),
    "is_marvel": (
        "Связь с Marvel",
        "Эвристический признак, указывающий на узнаваемый паттерн Marvel.",
    ),
    "is_star_wars": (
        "Связь со Star Wars",
        "Эвристический признак, указывающий на узнаваемый паттерн Star Wars.",
    ),
}


def _prediction_output(prediction: dict) -> dict:
    """Готовит технический ответ Vanga для понятного отображения человеку."""
    raw_contributions = prediction.get("contributions")
    contributions = raw_contributions if isinstance(raw_contributions, dict) else {}

    parsed: list[tuple[str, float]] = []
    for key, raw_value in contributions.items():
        try:
            parsed.append((str(key), float(raw_value)))
        except (TypeError, ValueError):
            continue

    parsed.sort(key=lambda item: abs(item[1]), reverse=True)
    max_abs = max((abs(value) for _, value in parsed), default=0.0)

    factors = []
    for key, value in parsed:
        label, description = PREDICTION_FEATURES.get(
            key,
            (
                key.replace("_", " ").strip().capitalize(),
                "Дополнительный признак модели. Его вклад показан в пунктах итогового рейтинга.",
            ),
        )
        if value > 0.01:
            direction = "Повышает прогноз"
            tone = "positive"
        elif value < -0.01:
            direction = "Снижает прогноз"
            tone = "negative"
        else:
            direction = "Почти не влияет"
            tone = "neutral"

        factors.append(
            {
                "key": key,
                "label": label,
                "description": description,
                "value": round(value, 4),
                "formatted_value": f"{value:+.2f}",
                "direction": direction,
                "tone": tone,
                "strength": round((abs(value) / max_abs * 100.0) if max_abs else 0.0, 1),
            }
        )

    positive_total = sum(value for _, value in parsed if value > 0)
    negative_total = sum(value for _, value in parsed if value < 0)

    try:
        base = float(prediction["base"]) if prediction.get("base") is not None else None
    except (TypeError, ValueError):
        base = None

    try:
        rating = float(prediction.get("rating"))
    except (TypeError, ValueError):
        rating = 0.0

    resolution = prediction.get("input_resolution")
    resolution = resolution if isinstance(resolution, dict) else {}
    recognized: list[dict[str, str]] = []

    def add_match(kind: str, match) -> None:
        if not isinstance(match, dict):
            return
        original = str(match.get("input") or "").strip()
        canonical = str(match.get("canonical") or "").strip()
        imdb_id = str(match.get("imdb_id") or "").strip()
        if not original or not canonical or original.casefold() == canonical.casefold():
            return
        recognized.append(
            {
                "kind": kind,
                "input": original,
                "canonical": canonical,
                "imdb_id": imdb_id,
            }
        )

    add_match("Название", resolution.get("title"))
    add_match("Режиссёр", resolution.get("director"))
    for match in resolution.get("actors") or []:
        add_match("Актёр", match)

    return {
        "rating": round(rating, 2),
        "base": round(base, 2) if base is not None else None,
        "positive_total": round(positive_total, 2),
        "negative_total": round(negative_total, 2),
        "factor_count": len(factors),
        "factors": factors,
        "top_factors": factors[:5],
        "recognized_inputs": recognized,
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
            prediction_output=None,
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
                prediction_output=None,
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
                prediction_output=None,
                demo_error=str(exc),
            ), 503

        return render_template(
            "public/vanga/index.html",
            **context,
            form=form,
            prediction=prediction,
            prediction_output=_prediction_output(prediction),
            demo_error=None,
        )
