from __future__ import annotations

from urllib.parse import urlsplit

from flask import request

from settings import config


def _admin_connect_sources() -> str:
    sources = ["'self'", "https://mc.yandex.ru"]
    if request.path.startswith(config.ADMIN_ROUTE_PREFIX):
        parsed = urlsplit(config.NOTES_OPERATOR_SIGNER_URL)
        signer_origin = f"{parsed.scheme}://{parsed.netloc}"
        sources.append(signer_origin)
    return "connect-src " + " ".join(sources)


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
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://code.jquery.com https://mc.yandex.ru",
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
                "img-src 'self' data: https://mc.yandex.ru",
                _admin_connect_sources(),
                "font-src 'self' data:",
            ]
        ),
    )

    if config.IS_PRODUCTION and request.is_secure:
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000",
        )

    if request.path.startswith(config.ADMIN_ROUTE_PREFIX) or request.path == "/contact":
        response.headers["Cache-Control"] = "no-store, private"
        response.headers["Pragma"] = "no-cache"

    return response
