from __future__ import annotations

from urllib.parse import urlsplit

from flask import request

from settings import config

_TURNSTILE_ORIGIN = "https://challenges.cloudflare.com"


def _turnstile_active() -> bool:
    return request.path == "/contact" and bool(config.CONTACT_TURNSTILE_SITE_KEY)


def _script_sources() -> str:
    sources = [
        "'self'",
        "'unsafe-inline'",
        "https://cdn.jsdelivr.net",
        "https://code.jquery.com",
        "https://mc.yandex.ru",
    ]
    if _turnstile_active():
        sources.append(_TURNSTILE_ORIGIN)
    return "script-src " + " ".join(sources)


def _connect_sources() -> str:
    sources = ["'self'", "https://mc.yandex.ru"]
    if request.path.startswith(config.ADMIN_ROUTE_PREFIX):
        parsed = urlsplit(config.NOTES_OPERATOR_SIGNER_URL)
        sources.append(f"{parsed.scheme}://{parsed.netloc}")
    if _turnstile_active():
        sources.append(_TURNSTILE_ORIGIN)
    return "connect-src " + " ".join(sources)


def _frame_sources() -> str:
    sources = ["'self'"]
    if _turnstile_active():
        sources.append(_TURNSTILE_ORIGIN)
    return "frame-src " + " ".join(sources)


def apply_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    )

    response.headers.setdefault(
        "Content-Security-Policy",
        "; ".join(
            [
                "default-src 'self'",
                "base-uri 'self'",
                "form-action 'self'",
                "frame-ancestors 'none'",
                "object-src 'none'",
                _script_sources(),
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
                "img-src 'self' data: https://mc.yandex.ru https://images.unsplash.com",
                _connect_sources(),
                _frame_sources(),
                "font-src 'self' data:",
            ]
        ),
    )

    if config.IS_PRODUCTION and request.is_secure:
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000",
        )

    private_or_non_searchable = (
        request.path.startswith(config.ADMIN_ROUTE_PREFIX)
        or request.path.startswith("/api/")
        or request.path.startswith(f"{config.NOTES_UPDATE_API_PREFIX}/")
        or request.path in {"/healthz", "/contact"}
    )
    if private_or_non_searchable:
        response.headers["X-Robots-Tag"] = "noindex, nofollow"

    if request.path.startswith(config.ADMIN_ROUTE_PREFIX) or request.path == "/contact":
        response.headers["Cache-Control"] = "no-store, private"
        response.headers["Pragma"] = "no-cache"

    return response
