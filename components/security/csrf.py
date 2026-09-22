from __future__ import annotations

import hmac
import secrets

from flask import abort, current_app, request, session

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
_SESSION_KEY = "_csrf_token"


def csrf_token() -> str:
    token = session.get(_SESSION_KEY)
    if not isinstance(token, str) or len(token) < 32:
        token = secrets.token_urlsafe(32)
        session[_SESSION_KEY] = token
    return token


def _submitted_token() -> str:
    header = request.headers.get("X-CSRF-Token", "").strip()
    if header:
        return header
    return request.form.get("_csrf_token", "").strip()


def validate_csrf() -> None:
    if request.method in _SAFE_METHODS:
        return

    expected = session.get(_SESSION_KEY)
    supplied = _submitted_token()
    if (
        not isinstance(expected, str)
        or not expected
        or not supplied
        or not hmac.compare_digest(expected, supplied)
    ):
        abort(400, description="Некорректный CSRF-токен. Обновите страницу и повторите действие.")


def rotate_csrf_token() -> None:
    session[_SESSION_KEY] = secrets.token_urlsafe(32)


def init_app(app) -> None:
    app.before_request(validate_csrf)
    app.jinja_env.globals["csrf_token"] = csrf_token
