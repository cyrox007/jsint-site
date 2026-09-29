from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_vanga_demo_api_registered():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    api_source = (ROOT / "views" / "demo_api.py").read_text(encoding="utf-8")

    assert "from views import demo_api" in app_source
    assert "demo_api.install(app)" in app_source
    assert 'prefix = "/api/demo/v1/vanga"' in api_source
    assert '"X-JSInt-Installation"' in api_source
    assert 'action="vanga-demo-heartbeat"' in api_source


def test_vanga_demo_does_not_expose_release_artifacts():
    api_source = (ROOT / "views" / "demo_api.py").read_text(encoding="utf-8")

    assert "/artifact" not in api_source
    assert "release_for_artifact" not in api_source
