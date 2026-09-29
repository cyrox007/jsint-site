from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_vanga_demo_route_contract():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    router_source = (ROOT / "views" / "public" / "vanga" / "routers.py").read_text(encoding="utf-8")
    view_source = (ROOT / "views" / "public" / "vanga" / "views.py").read_text(encoding="utf-8")
    template_source = (ROOT / "templates" / "public" / "vanga" / "index.html").read_text(encoding="utf-8")

    assert "from views.public.vanga import routers as vanga_router" in app_source
    assert "vanga_router.install(app)" in app_source
    assert '"/demo/vanga"' in router_source
    assert "VANGA_DEMO_URL" in view_source
    assert '"/predict"' in view_source
    assert 'name="_csrf_token"' in template_source


def test_vanga_demo_is_server_side_proxy():
    view_source = (ROOT / "views" / "public" / "vanga" / "views.py").read_text(encoding="utf-8")
    template_source = (ROOT / "templates" / "public" / "vanga" / "index.html").read_text(encoding="utf-8")

    assert "urlopen(" in view_source
    assert "127.0.0.1:9100" not in template_source
    assert "fetch(" not in template_source
