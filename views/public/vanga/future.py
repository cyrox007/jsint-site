from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlencode

from flask import request

from views.public.vanga import views as vanga_views


_ALLOWED_TERRITORIES = {"DE", "US", "NL", "GB", "FR", "ES", "IT", "CA", "AU", "JP", "KR"}


def _territory(value) -> str | None:
    territory = str(value or "").strip().upper()
    return territory if territory in _ALLOWED_TERRITORIES else None


def _cutoff(value) -> str:
    text = str(value or "").strip()
    if text:
        return text
    return datetime.now(timezone.utc).isoformat()


def vanga_future_catalog_api():
    """Проксирует региональный future catalog, не раскрывая внутренний Vanga URL."""
    territory = _territory(request.args.get("territory"))
    if territory is None:
        return vanga_views._json_no_store(
            {"ok": False, "error": "Выберите поддерживаемый рынок релиза."},
            400,
        )

    cutoff = _cutoff(request.args.get("cutoff"))
    params = {
        "territory": territory,
        "cutoff": cutoff,
        "include_conflicts": "true",
    }
    from_at = str(request.args.get("from_at") or "").strip()
    to_at = str(request.args.get("to_at") or "").strip()
    if from_at:
        params["from_at"] = from_at
    if to_at:
        params["to_at"] = to_at

    try:
        result = vanga_views._request_vanga(
            "/future/catalog?" + urlencode(params),
            timeout=5,
        )
    except RuntimeError as exc:
        return vanga_views._json_no_store(
            {"ok": False, "error": str(exc)},
            503,
        )

    return vanga_views._json_no_store(result, 200 if result.get("ok") else 503)


def vanga_future_prediction_payload_api():
    """Проксирует P9 payload builder и сохраняет blocked-state как штатный ответ."""
    if request.content_length is not None and request.content_length > 32 * 1024:
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

    project_id = str(values.get("project_id") or "").strip()
    territory = _territory(values.get("territory"))
    if not project_id or len(project_id) > 180:
        return vanga_views._json_no_store(
            {"ok": False, "error": "Некорректный project_id."},
            400,
        )
    if territory is None:
        return vanga_views._json_no_store(
            {"ok": False, "error": "Выберите поддерживаемый рынок релиза."},
            400,
        )

    payload = {
        "project_id": project_id,
        "territory": territory,
        "cutoff": _cutoff(values.get("cutoff")),
        "allow_current_imdb_snapshot": False,
    }

    try:
        result = vanga_views._request_vanga(
            "/future/prediction-payload",
            payload=payload,
            timeout=5,
        )
    except RuntimeError as exc:
        return vanga_views._json_no_store(
            {"ok": False, "error": str(exc)},
            503,
        )

    # prediction_ready=false — валидное состояние данных, а не ошибка HTTP.
    return vanga_views._json_no_store(result, 200 if result.get("ok") else 503)
