from __future__ import annotations

from flask import render_template, request

from components.auth.decorator import with_db_session
from models.vanga import VangaPrediction
from services.site import SiteService
from views.public.vanga import views as vanga_views


def _source_payload(values: dict) -> tuple[dict, str | None]:
    raw = values.get("source") or {}
    if not isinstance(raw, dict):
        return {}, "Данные первоисточника должны быть объектом."

    result: dict = {}
    for key in ("type", "title", "author", "format"):
        value = str(raw.get(key) or "").strip()
        if len(value) > 240:
            return {}, f"Поле первоисточника {key} слишком длинное."
        if value:
            result[key] = value

    if raw.get("series_size") not in (None, ""):
        try:
            series_size = int(raw.get("series_size"))
        except (TypeError, ValueError):
            return {}, "Размер цикла должен быть целым числом."
        if not 1 <= series_size <= 10000:
            return {}, "Размер цикла вне допустимого диапазона."
        result["series_size"] = series_size

    return result, None


def _persist_profile(db_session, snapshot, payload: dict, prediction: dict) -> None:
    if snapshot is None:
        return

    request_data = dict(snapshot.request_data or {})
    request_data["synopsis"] = payload.get("synopsis")
    request_data["source"] = payload.get("source") or {}

    result_data = dict(snapshot.result_data or {})
    result_data["pre_release_profile"] = prediction.get("pre_release_profile") or {}

    snapshot.request_data = request_data
    snapshot.result_data = result_data
    db_session.add(snapshot)
    db_session.commit()


@with_db_session
def vanga_predict_profile_api(db_session):
    """AJAX-прогноз с диагностикой потенциала по pre-release данным."""
    if request.content_length is not None and request.content_length > 48 * 1024:
        return vanga_views._json_no_store(
            {"ok": False, "error": "Слишком большой запрос."},
            413,
        )

    values = request.get_json(silent=True)
    if not isinstance(values, dict):
        return vanga_views._json_no_store(
            {"ok": False, "error": "Ожидается JSON."},
            400,
        )

    form, payload, error = vanga_views._prepare_prediction_payload(values)
    if error or payload is None:
        return vanga_views._json_no_store(
            {"ok": False, "error": error, "form": form},
            400,
        )

    synopsis = str(values.get("synopsis") or "").strip()
    if len(synopsis) > 5000:
        return vanga_views._json_no_store(
            {"ok": False, "error": "Синопсис не должен превышать 5000 символов."},
            400,
        )

    source, source_error = _source_payload(values)
    if source_error:
        return vanga_views._json_no_store(
            {"ok": False, "error": source_error},
            400,
        )

    payload["synopsis"] = synopsis or None
    payload["source"] = source

    prediction, error = vanga_views._run_prediction(payload)
    if error or prediction is None:
        return vanga_views._json_no_store(
            {"ok": False, "error": error},
            503,
        )

    output = vanga_views._prediction_output(prediction)
    site_model = SiteService.get_default(db_session)
    snapshot = vanga_views._save_prediction_snapshot(
        db_session,
        site_model.id,
        payload,
        prediction,
    )
    if snapshot is not None:
        try:
            _persist_profile(db_session, snapshot, payload, prediction)
        except Exception:
            db_session.rollback()

    snapshot_url = vanga_views._snapshot_url(snapshot)
    profile = prediction.get("pre_release_profile") or {}

    return vanga_views._json_no_store(
        {
            "ok": True,
            "prediction": prediction,
            "output": output,
            "snapshot": (
                {
                    "id": str(snapshot.id),
                    "generation": snapshot.model_generation,
                    "created_at": snapshot.created_at.isoformat(),
                    "url": snapshot_url,
                }
                if snapshot is not None
                else None
            ),
            "result_html": render_template(
                "public/vanga/_result.html",
                prediction=prediction,
                prediction_output=output,
                demo_error=None,
                snapshot_url=snapshot_url,
            ),
            "analysis_html": render_template(
                "public/vanga/_analysis.html",
                prediction=prediction,
                prediction_output=output,
            ),
            "profile_html": render_template(
                "public/vanga/_potential.html",
                profile=profile,
            ),
        }
    )


@with_db_session
def vanga_snapshot_potential(db_session, snapshot_id):
    """Возвращает сохранённый pre-release профиль без нового inference."""
    site_model = SiteService.get_default(db_session)
    record = (
        db_session.query(VangaPrediction)
        .filter(VangaPrediction.id == snapshot_id)
        .filter(VangaPrediction.site_id == site_model.id)
        .first()
    )
    if record is None:
        return vanga_views._json_no_store(
            {"ok": False, "error": "Снимок прогноза не найден."},
            404,
        )

    result_data = record.result_data if isinstance(record.result_data, dict) else {}
    profile = result_data.get("pre_release_profile")
    if not isinstance(profile, dict) or not profile:
        return vanga_views._json_no_store(
            {"ok": True, "profile_html": ""},
        )

    return vanga_views._json_no_store(
        {
            "ok": True,
            "profile_html": render_template(
                "public/vanga/_potential.html",
                profile=profile,
            ),
        }
    )
