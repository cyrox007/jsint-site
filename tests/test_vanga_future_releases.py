from __future__ import annotations

from unittest.mock import patch

from flask import Flask

from views.public.vanga import future


def _app() -> Flask:
    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.add_url_rule(
        "/future-catalog",
        view_func=future.vanga_future_catalog_api,
        methods=["GET"],
    )
    app.add_url_rule(
        "/future-payload",
        view_func=future.vanga_future_prediction_payload_api,
        methods=["POST"],
    )
    return app


def test_future_catalog_requires_supported_explicit_market():
    client = _app().test_client()
    with patch("views.public.vanga.future.vanga_views._request_vanga") as upstream:
        missing = client.get("/future-catalog")
        worldwide = client.get("/future-catalog?territory=worldwide")

    assert missing.status_code == 400
    assert worldwide.status_code == 400
    assert upstream.call_count == 0
    assert "рынок" in worldwide.get_json()["error"].lower()


def test_future_catalog_proxies_iso_market_without_worldwide_fallback():
    client = _app().test_client()
    upstream_payload = {
        "ok": True,
        "territory": "iso3166:de",
        "territory_policy": "explicit_iso3166_no_worldwide_fallback",
        "items": [],
    }
    with patch(
        "views.public.vanga.future.vanga_views._request_vanga",
        return_value=upstream_payload,
    ) as upstream:
        response = client.get(
            "/future-catalog?territory=DE&cutoff=2026-10-04T12:00:00Z"
        )

    assert response.status_code == 200
    assert response.get_json()["territory"] == "iso3166:de"
    path = upstream.call_args.args[0]
    assert path.startswith("/future/catalog?")
    assert "territory=DE" in path
    assert "worldwide" not in path


def test_future_prediction_payload_preserves_blocked_state_as_200():
    client = _app().test_client()
    upstream_payload = {
        "ok": True,
        "prediction_ready": False,
        "blockers": ["regional_release_date_conflict"],
        "request": None,
        "target_territory": "iso3166:de",
    }
    with patch(
        "views.public.vanga.future.vanga_views._request_vanga",
        return_value=upstream_payload,
    ) as upstream:
        response = client.post(
            "/future-payload",
            json={
                "project_id": "wikidata:Q123",
                "territory": "DE",
                "cutoff": "2026-10-04T12:00:00Z",
            },
        )

    assert response.status_code == 200
    assert response.get_json()["prediction_ready"] is False
    assert response.get_json()["request"] is None
    path = upstream.call_args.args[0]
    payload = upstream.call_args.kwargs["payload"]
    assert path == "/future/prediction-payload"
    assert payload["territory"] == "DE"
    assert payload["allow_current_imdb_snapshot"] is False


def test_future_prediction_payload_rejects_bad_project_before_upstream():
    client = _app().test_client()
    with patch("views.public.vanga.future.vanga_views._request_vanga") as upstream:
        response = client.post(
            "/future-payload",
            json={"project_id": "", "territory": "DE"},
        )

    assert response.status_code == 400
    assert upstream.call_count == 0


def test_future_frontend_only_submits_when_payload_is_ready():
    source = open("static/public/vanga-future.js", encoding="utf-8").read()
    assert "if (!data.prediction_ready || !data.request)" in source
    assert "form.requestSubmit()" in source
    assert "worldwide" not in source
    assert "regional_release_date_conflict" in source


def test_future_frontend_is_loaded_as_progressive_enhancement():
    source = open("static/public/vanga-potential.js", encoding="utf-8").read()
    assert "/static/public/vanga-future.js" in source
    assert "/static/public/vanga-future.css" in source
    assert "базовая форма Vanga остаётся полностью рабочей" in source
