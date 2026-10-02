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
from services.vanga_predictions import VangaPredictionService
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

    uncertainty = None
    raw_uncertainty = prediction.get("uncertainty")
    if isinstance(raw_uncertainty, dict):
        try:
            lower = float(raw_uncertainty["lower"])
            upper = float(raw_uncertainty["upper"])
            margin = float(raw_uncertainty["margin"])
            coverage = float(raw_uncertainty.get("coverage", 0.80))
            if 0 <= lower <= upper <= 10 and margin >= 0:
                uncertainty = {
                    "lower": round(lower, 2),
                    "upper": round(upper, 2),
                    "margin": round(margin, 2),
                    "coverage": round(coverage, 2),
                    "coverage_percent": int(round(coverage * 100)),
                    "test_year_from": raw_uncertainty.get("test_year_from"),
                    "test_year_to": raw_uncertainty.get("test_year_to"),
                    "test_rows": raw_uncertainty.get("test_rows"),
                }
        except (KeyError, TypeError, ValueError):
            uncertainty = None

    quality = None
    raw_quality = prediction.get("quality")
    if isinstance(raw_quality, dict):
        try:
            mae_raw = raw_quality.get("mae")
            rmse_raw = raw_quality.get("rmse")
            r2_raw = raw_quality.get("r2")
            quality = {
                "mae": round(float(mae_raw), 2) if mae_raw is not None else None,
                "rmse": round(float(rmse_raw), 2) if rmse_raw is not None else None,
                "r2": round(float(r2_raw), 3) if r2_raw is not None else None,
                "test_year_from": raw_quality.get("test_year_from"),
                "test_year_to": raw_quality.get("test_year_to"),
                "test_rows": raw_quality.get("test_rows"),
                "train_year_from": raw_quality.get("train_year_from"),
                "train_year_to": raw_quality.get("train_year_to"),
                "train_rows": raw_quality.get("train_rows"),
            }
            if not any(
                quality.get(name) is not None
                for name in ("mae", "rmse", "r2", "test_rows")
            ):
                quality = None
        except (TypeError, ValueError):
            quality = None

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
        "uncertainty": uncertainty,
        "quality": quality,
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


def _prepare_prediction_payload(values) -> tuple[dict[str, str], dict | None, str | None]:
    """Нормализует browser/API ввод в единый контракт Vanga."""
    imdb_id = str(values.get("imdb_id") or "").strip()
    title = str(values.get("title") or "").strip()
    director = str(values.get("director") or "").strip()
    year_raw = str(values.get("year") or "").strip()
    runtime_raw = str(values.get("runtime") or "").strip()

    genres_raw = values.get("genres") or ""
    if isinstance(genres_raw, list):
        genres = [str(item).strip() for item in genres_raw if str(item).strip()]
        genres_form = ", ".join(genres)
    else:
        genres_form = str(genres_raw).strip()
        genres = [item.strip() for item in genres_form.split(",") if item.strip()]

    actors_raw = values.get("actors") or []
    if isinstance(actors_raw, list):
        actors = [str(item).strip() for item in actors_raw if str(item).strip()][:5]
        actors_form = ", ".join(actors)
    else:
        actors_form = str(actors_raw).strip()
        actors = [item.strip() for item in actors_form.split(",") if item.strip()][:5]

    form = {
        "imdb_id": imdb_id,
        "title": title,
        "director": director,
        "year": year_raw,
        "runtime": runtime_raw,
        "genres": genres_form,
        "actors": actors_form,
    }

    if not title or len(title) > 240:
        return form, None, "Укажите название фильма."
    if not director or len(director) > 240:
        return form, None, "Укажите режиссёра."
    if not genres:
        return form, None, "Укажите хотя бы один жанр."

    try:
        year = int(year_raw)
        runtime = int(runtime_raw)
    except ValueError:
        return form, None, "Год и длительность должны быть целыми числами."

    if not 1888 <= year <= 2100:
        return form, None, "Год вне допустимого диапазона."
    if not 1 <= runtime <= 1000:
        return form, None, "Некорректная длительность фильма."
    if imdb_id and (len(imdb_id) > 16 or not imdb_id.startswith("tt")):
        return form, None, "Некорректный IMDb ID."

    payload = {
        "imdb_id": imdb_id or None,
        "title": title,
        "director": director,
        "year": year,
        "runtime": runtime,
        "genres": genres,
        "actors": actors,
    }
    return form, payload, None


def _run_prediction(payload: dict) -> tuple[dict | None, str | None]:
    try:
        prediction = _request_vanga("/predict", payload=payload)
        if not prediction.get("ok"):
            raise RuntimeError(
                str(prediction.get("error") or "Не удалось получить прогноз")
            )
        return prediction, None
    except RuntimeError as exc:
        return None, str(exc)


def _save_prediction_snapshot(db_session, site_id, payload: dict, prediction: dict):
    """Сохраняет воспроизводимый снимок прогноза без данных о посетителе."""
    try:
        rating = Decimal(str(prediction.get("rating"))).quantize(Decimal("0.01"))
        imdb_id = str(
            prediction.get("imdb_id")
            or payload.get("imdb_id")
            or ""
        ).strip() or None

        record = VangaPrediction(
            site_id=site_id,
            imdb_id=imdb_id,
            title=str(payload.get("title") or "")[:240],
            year=int(payload["year"]),
            model_generation=(
                str(prediction.get("generation") or "").strip()[:96] or None
            ),
            rating=rating,
            request_data={
                "imdb_id": imdb_id,
                "title": payload.get("title"),
                "director": payload.get("director"),
                "year": payload.get("year"),
                "runtime": payload.get("runtime"),
                "genres": payload.get("genres") or [],
                "actors": payload.get("actors") or [],
            },
            result_data={
                "base": prediction.get("base"),
                "contributions": prediction.get("contributions") or {},
                "explanation": prediction.get("explanation"),
                "input_resolution": prediction.get("input_resolution") or {},
                "uncertainty": prediction.get("uncertainty"),
                "quality": prediction.get("quality") or {},
            },
        )
        db_session.add(record)
        db_session.commit()
        return record
    except Exception:
        db_session.rollback()
        logger.exception("Не удалось сохранить снимок прогноза Vanga")
        return None


def _json_no_store(payload: dict, status: int = 200):
    response = jsonify(payload)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


def vanga_search():
    query = str(request.args.get("q") or "").strip()
    search_type = str(request.args.get("type") or "movie").strip().lower()
    if len(query) < 2:
        return _json_no_store({"ok": True, "items": []})
    if len(query) > 120:
        return _json_no_store(
            {"ok": False, "error": "Слишком длинный поисковый запрос."},
            400,
        )

    params = {"q": query, "limit": "8"}
    if search_type == "movie":
        year = str(request.args.get("year") or "").strip()
        if year:
            params["year"] = year
        path = "/search/movies?" + urlencode(params)
    elif search_type == "person":
        role = str(request.args.get("role") or "actor").strip().lower()
        if role not in {"director", "actor"}:
            role = "actor"
        params["role"] = role
        path = "/search/people?" + urlencode(params)
    else:
        return _json_no_store(
            {"ok": False, "error": "Неизвестный тип поиска."},
            400,
        )

    try:
        result = _request_vanga(path, timeout=5)
    except RuntimeError as exc:
        return _json_no_store({"ok": False, "error": str(exc)}, 503)

    return _json_no_store(
        {
            "ok": bool(result.get("ok")),
            "items": result.get("items") or [],
            "generation": result.get("generation"),
        }
    )


@with_db_session
def vanga_predict_api(db_session):
    if request.content_length is not None and request.content_length > 32 * 1024:
        return _json_no_store({"ok": False, "error": "Слишком большой запрос."}, 413)

    values = request.get_json(silent=True)
    if not isinstance(values, dict):
        return _json_no_store({"ok": False, "error": "Ожидается JSON."}, 400)

    form, payload, error = _prepare_prediction_payload(values)
    if error or payload is None:
        return _json_no_store({"ok": False, "error": error, "form": form}, 400)

    prediction, error = _run_prediction(payload)
    if error or prediction is None:
        return _json_no_store({"ok": False, "error": error}, 503)

    output = _prediction_output(prediction)
    site_model = SiteService.get_default(db_session)
    snapshot = _save_prediction_snapshot(
        db_session,
        site_model.id,
        payload,
        prediction,
    )

    return _json_no_store(
        {
            "ok": True,
            "prediction": prediction,
            "output": output,
            "snapshot": (
                {
                    "id": str(snapshot.id),
                    "generation": snapshot.model_generation,
                    "created_at": snapshot.created_at.isoformat(),
                }
                if snapshot is not None
                else None
            ),
            "result_html": render_template(
                "public/vanga/_result.html",
                prediction=prediction,
                prediction_output=output,
                demo_error=None,
            ),
            "analysis_html": render_template(
                "public/vanga/_analysis.html",
                prediction=prediction,
                prediction_output=output,
            ),
        }
    )


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
            service_status = (
                "Модель готова"
                if service_ready
                else "Модель временно недоступна"
            )
        except RuntimeError:
            pass

        canonical_url = (
            f"{site['base_url']}/projects/vanga"
            if site["base_url"]
            else "/projects/vanga"
        )
        verified_predictions = VangaPredictionService.recent_verified(
            db_session,
            site_id=site_model.id,
            limit=6,
        )
        verification_summary = VangaPredictionService.verification_summary(
            db_session,
            site_id=site_model.id,
        )
        return {
            "site_model": site_model,
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
            "verified_predictions": verified_predictions,
            "verification_summary": verification_summary,
        }

    def get(self, db_session):
        return render_template(
            "public/vanga/index.html",
            **self._base_context(db_session),
            form=dict(DEFAULT_FORM),
            prediction=None,
            prediction_output=None,
            demo_error=None,
        )

    def post(self, db_session):
        context = self._base_context(db_session)
        form, payload, error = _prepare_prediction_payload(request.form)
        if error or payload is None:
            return render_template(
                "public/vanga/index.html",
                **context,
                form=form,
                prediction=None,
                prediction_output=None,
                demo_error=error,
            ), 400

        prediction, error = _run_prediction(payload)
        if error or prediction is None:
            return render_template(
                "public/vanga/index.html",
                **context,
                form=form,
                prediction=None,
                prediction_output=None,
                demo_error=error,
            ), 503

        output = _prediction_output(prediction)
        _save_prediction_snapshot(
            db_session,
            context["site_model"].id,
            payload,
            prediction,
        )

        return render_template(
            "public/vanga/index.html",
            **context,
            form=form,
            prediction=prediction,
            prediction_output=output,
            demo_error=None,
        )
