from __future__ import annotations

from html import escape

from flask import Response, abort, render_template, url_for

from components.auth.decorator import with_db_session
from models.vanga import VangaPrediction
from services.page import PageService
from services.site import SiteService
from services.vanga_predictions import VangaPredictionService


@with_db_session
def vanga_accuracy(db_session):
    """Показывает накопленную точность только по фактически сверенным snapshot."""
    site_model = SiteService.get_default(db_session)
    site = SiteService.public_config(site_model)
    PageService.apply_public_navigation(db_session, site_model.id, site)
    report = VangaPredictionService.accuracy_report(db_session, site_id=site_model.id)

    base_url = (site.get("base_url") or "").rstrip("/")
    canonical_url = f"{base_url}/projects/vanga/accuracy" if base_url else "/projects/vanga/accuracy"
    return render_template(
        "public/vanga/accuracy.html",
        site=site,
        report=report,
        seo_title="Точность прогнозов Vanga — сверка с IMDb",
        seo_description=(
            "Накопленная точность сохранённых прогнозов Vanga: MAE по поколениям "
            "модели, годам фильмов и уровню покрытия данных."
        ),
        canonical_url=canonical_url,
        seo_noindex=False,
    )


@with_db_session
def vanga_snapshot_share_svg(db_session, snapshot_id):
    """Возвращает immutable share-card из сохранённого snapshot без inference."""
    site_model = SiteService.get_default(db_session)
    record = (
        db_session.query(VangaPrediction)
        .filter(VangaPrediction.id == snapshot_id)
        .filter(VangaPrediction.site_id == site_model.id)
        .first()
    )
    if record is None:
        abort(404)

    title = escape(str(record.title or "Фильм"))
    if len(title) > 62:
        title = title[:59] + "…"
    rating = f"{float(record.rating):.2f}"
    generation = escape(str(record.model_generation or "snapshot"))
    snapshot_url = url_for("vanga_snapshot", snapshot_id=record.id, _external=True)
    safe_url = escape(snapshot_url)

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900">
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#071018"/><stop offset="1" stop-color="#132637"/></linearGradient>
  <radialGradient id="glow"><stop stop-color="#68d5ff" stop-opacity=".28"/><stop offset="1" stop-color="#68d5ff" stop-opacity="0"/></radialGradient>
</defs>
<rect width="1600" height="900" fill="url(#bg)"/>
<circle cx="1280" cy="140" r="520" fill="url(#glow)"/>
<text x="120" y="150" fill="#8bdfff" font-family="Arial,sans-serif" font-size="34" font-weight="700">VANGA · СОХРАНЁННЫЙ ПРОГНОЗ</text>
<text x="120" y="290" fill="#ffffff" font-family="Arial,sans-serif" font-size="72" font-weight="700">{title}</text>
<text x="120" y="420" fill="#a8bac7" font-family="Arial,sans-serif" font-size="32">Прогноз до сверки с реальностью</text>
<text x="120" y="660" fill="#ffffff" font-family="Arial,sans-serif" font-size="190" font-weight="800">{rating}</text>
<text x="530" y="655" fill="#a8bac7" font-family="Arial,sans-serif" font-size="54">/ 10</text>
<text x="120" y="775" fill="#6f8798" font-family="Arial,sans-serif" font-size="27">Модель {generation}</text>
<text x="120" y="825" fill="#6f8798" font-family="Arial,sans-serif" font-size="23">{safe_url}</text>
</svg>'''
    response = Response(svg, mimetype="image/svg+xml")
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
