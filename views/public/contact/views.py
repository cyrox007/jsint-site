from __future__ import annotations

import re

from flask import abort, jsonify, redirect, render_template, request, url_for
from flask.views import MethodView
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from components.auth.decorator import with_db_session
from components.security.contact_rate_limit import ContactSpamGuard
from models.contact import ContactMessage
from services.page import PageService
from services.site import SiteService
from settings import config


def _compact(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\x00", "")).strip()


def _message_text(value: str) -> str:
    value = value.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in value.split("\n")]
    return "\n".join(lines).strip()


def _values() -> dict[str, str]:
    return {
        "name": _compact(request.form.get("name", "")),
        "reply_to": _compact(request.form.get("reply_to", "")),
        "subject": _compact(request.form.get("subject", "")),
        "message": _message_text(request.form.get("message", "")),
    }


def _validation_errors(values: dict[str, str]) -> list[str]:
    errors: list[str] = []
    if len(values["name"]) < 2 or len(values["name"]) > 120:
        errors.append("Укажите имя длиной от 2 до 120 символов.")
    if len(values["reply_to"]) < 3 or len(values["reply_to"]) > 320:
        errors.append("Укажите способ связи длиной от 3 до 320 символов.")
    if len(values["subject"]) > 200:
        errors.append("Тема не должна быть длиннее 200 символов.")
    if len(values["message"]) < 20 or len(values["message"]) > 5000:
        errors.append("Сообщение должно содержать от 20 до 5000 символов.")
    return errors


def _context(
    db_session: Session,
    *,
    errors: list[str] | None = None,
    values: dict[str, str] | None = None,
    sent: bool = False,
) -> dict:
    site_model = SiteService.get_default(db_session)
    site = SiteService.public_config(site_model)
    PageService.apply_public_navigation(
        db_session,
        site_model.id,
        site,
    )
    canonical = f"{site['base_url']}/contact" if site["base_url"] else None
    challenge = "" if sent else ContactSpamGuard.issue_challenge()

    return {
        "site_model": site_model,
        "site": site,
        "errors": errors or [],
        "values": values or {},
        "sent": sent,
        "contact_nonce": challenge,
        "turnstile_site_key": config.CONTACT_TURNSTILE_SITE_KEY,
        "seo_title": f"Связаться | {site['settings']['seo']['site_name']}",
        "seo_description": "Защищённая форма обратной связи.",
        "canonical_url": canonical,
        "seo_noindex": True,
    }


def _interactive_request() -> bool:
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def _silent_success():
    if _interactive_request():
        return jsonify(
            {
                "ok": True,
                "message": "Обращение принято.",
            }
        )
    return redirect(url_for("contact", sent="1"))


def _error_response(
    db_session: Session,
    errors: list[str],
    *,
    values: dict[str, str] | None = None,
    status: int = 400,
):
    if _interactive_request():
        return (
            jsonify(
                {
                    "ok": False,
                    "errors": errors,
                    "contact_nonce": ContactSpamGuard.issue_challenge(),
                }
            ),
            status,
        )

    context = _context(db_session, errors=errors, values=values)
    return render_template("public/contact/index.html", **context), status


class ContactPage(MethodView):
    decorators = [with_db_session]

    def get(self, db_session: Session):
        return render_template(
            "public/contact/index.html",
            **_context(db_session, sent=request.args.get("sent") == "1"),
        )

    def post(self, db_session: Session):
        if (
            request.content_length is not None
            and request.content_length > config.CONTACT_MAX_REQUEST_BYTES
        ):
            abort(413)

        site_model = SiteService.get_default(db_session)

        if ContactSpamGuard.volume_blocked():
            return _error_response(
                db_session,
                ["Слишком много отправок. Повторите попытку позже."],
                status=429,
            )

        ContactSpamGuard.record_attempt()

        challenge_ok = ContactSpamGuard.consume_challenge(
            request.form.get("_contact_nonce", "").strip()
        )
        if not challenge_ok or ContactSpamGuard.honeypot_triggered():
            return _silent_success()

        values = _values()
        errors = _validation_errors(values)
        errors.extend(ContactSpamGuard.content_errors(values))
        if errors:
            return _error_response(
                db_session,
                errors,
                values=values,
                status=400,
            )

        if ContactSpamGuard.reply_blocked(values["reply_to"]):
            return _silent_success()

        if not ContactSpamGuard.verify_turnstile(
            request.form.get("cf-turnstile-response", "")
        ):
            return _error_response(
                db_session,
                [
                    "Не удалось подтвердить отправку. Обновите страницу и повторите попытку."
                ],
                values=values,
                status=400,
            )

        fingerprint = ContactSpamGuard.fingerprint(values)
        if not ContactSpamGuard.reserve_fingerprint(fingerprint):
            return _silent_success()

        storage_fingerprint = ContactSpamGuard.storage_fingerprint(fingerprint)

        try:
            # Redis-защита фиксируется до INSERT. При обязательном Redis
            # недоступность защиты не должна приводить к записи в PostgreSQL.
            ContactSpamGuard.record_reply(values["reply_to"])
            db_session.add(
                ContactMessage(
                    site_id=site_model.id,
                    name=values["name"],
                    reply_to=values["reply_to"],
                    subject=values["subject"] or None,
                    message=values["message"],
                    fingerprint=storage_fingerprint,
                    status="new",
                )
            )
            db_session.commit()
        except IntegrityError:
            db_session.rollback()
            return _silent_success()
        except Exception:
            db_session.rollback()
            ContactSpamGuard.release_fingerprint(fingerprint)
            raise

        return _silent_success()
