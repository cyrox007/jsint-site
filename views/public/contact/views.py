from __future__ import annotations

import re

from flask import redirect, render_template, request, url_for
from flask.views import MethodView
from sqlalchemy.orm import Session

from components.auth.decorator import with_db_session
from components.security.contact_rate_limit import ContactRateLimiter
from models.contact import ContactMessage
from services.site import SiteService


def _compact(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\x00", "")).strip()


def _message_text(value: str) -> str:
    value = value.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in value.split("\n")]
    return "\n".join(lines).strip()


def _context(db_session: Session, *, errors=None, values=None, sent=False):
    site_model = SiteService.get_default(db_session)
    site = SiteService.public_config(site_model)
    canonical = f"{site['base_url']}/contact" if site["base_url"] else None
    return {
        "site_model": site_model,
        "site": site,
        "errors": errors or [],
        "values": values or {},
        "sent": sent,
        "seo_title": f"Связаться | {site['settings']['seo']['site_name']}",
        "seo_description": "Защищённая форма обратной связи.",
        "canonical_url": canonical,
        "seo_noindex": True,
    }


class ContactPage(MethodView):
    decorators = [with_db_session]

    def get(self, db_session: Session):
        return render_template(
            "public/contact/index.html",
            **_context(db_session, sent=request.args.get("sent") == "1"),
        )

    def post(self, db_session: Session):
        context = _context(db_session)
        site_model = context["site_model"]

        if ContactRateLimiter.blocked():
            context["errors"] = [
                "Слишком много отправок с вашего адреса. Повторите попытку позже."
            ]
            return render_template("public/contact/index.html", **context), 429

        # Honeypot: пользователь это поле не видит. Для бота имитируем успешную отправку.
        if request.form.get("website", "").strip():
            ContactRateLimiter.record_submission()
            return redirect(url_for("contact", sent="1"))

        values = {
            "name": _compact(request.form.get("name", "")),
            "reply_to": _compact(request.form.get("reply_to", "")),
            "subject": _compact(request.form.get("subject", "")),
            "message": _message_text(request.form.get("message", "")),
        }
        errors: list[str] = []

        if len(values["name"]) < 2 or len(values["name"]) > 120:
            errors.append("Укажите имя длиной от 2 до 120 символов.")
        if len(values["reply_to"]) < 3 or len(values["reply_to"]) > 320:
            errors.append("Укажите способ связи длиной от 3 до 320 символов.")
        if len(values["subject"]) > 200:
            errors.append("Тема не должна быть длиннее 200 символов.")
        if len(values["message"]) < 20 or len(values["message"]) > 5000:
            errors.append("Сообщение должно содержать от 20 до 5000 символов.")

        if errors:
            context["errors"] = errors
            context["values"] = values
            return render_template("public/contact/index.html", **context), 400

        db_session.add(
            ContactMessage(
                site_id=site_model.id,
                name=values["name"],
                reply_to=values["reply_to"],
                subject=values["subject"] or None,
                message=values["message"],
                status="new",
            )
        )
        db_session.commit()
        ContactRateLimiter.record_submission()
        return redirect(url_for("contact", sent="1"))
