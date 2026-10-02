from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse


# Общие публичные SEO-константы. Изображение используется как fallback для
# OpenGraph/Twitter и structured data, если у страницы нет собственного.
HERO_IMAGE_URL = (
    "https://images.unsplash.com/photo-1776251693908-b7eb878a5e6b"
    "?auto=format&fit=crop&fm=jpg&q=82&w=2400"
)
DEFAULT_SHARE_IMAGE_URL = (
    "https://images.unsplash.com/photo-1776251693908-b7eb878a5e6b"
    "?auto=format&fit=crop&fm=jpg&q=82&w=1600&h=900"
)

AUTHOR_NAME = "JSInteractive"
AUTHOR_DESCRIPTION = (
    "Full-stack разработка веб-приложений, backend-сервисов, "
    "self-hosted систем и собственных программных проектов."
)
AUTHOR_KNOWS_ABOUT = [
    "Full-stack development",
    "Backend development",
    "Python",
    "PHP",
    "JavaScript",
    "Flask",
    "FastAPI",
    "PostgreSQL",
    "Redis",
    "Docker",
    "Nginx",
    "Self-hosted systems",
    "Realtime systems",
]


def absolute_url(base_url: str, value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return raw
    if not base_url:
        return raw
    return urljoin(f"{base_url.rstrip('/')}/", raw.lstrip("/"))


def share_image_url(site: dict, value: str | None = None) -> str:
    explicit = absolute_url(site.get("base_url") or "", value)
    if explicit:
        return explicit

    configured = (
        site.get("settings", {})
        .get("seo", {})
        .get("image_url")
    )
    configured_url = absolute_url(site.get("base_url") or "", configured)
    return configured_url or DEFAULT_SHARE_IMAGE_URL


def first_content_image(html: str | None, base_url: str) -> str | None:
    if not html:
        return None
    match = re.search(
        r'<img\b[^>]*\bsrc=["\']([^"\']+)["\']',
        html,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    return absolute_url(base_url, match.group(1))


def author_entity(site: dict) -> dict:
    base_url = (site.get("base_url") or "").rstrip("/")
    return {
        "@type": "Person",
        "@id": f"{base_url}/#creator" if base_url else "#creator",
        "name": AUTHOR_NAME,
        "url": f"{base_url}/#about" if base_url else "/#about",
        "description": AUTHOR_DESCRIPTION,
        "knowsAbout": AUTHOR_KNOWS_ABOUT,
    }


def breadcrumb_schema(items: list[tuple[str, str | None]]) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": index,
                "name": name,
                **({"item": url} if url else {}),
            }
            for index, (name, url) in enumerate(items, start=1)
        ],
    }
