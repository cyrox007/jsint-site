#!/usr/bin/env python3
"""Отправить все текущие публичные URL сайта в Яндекс через IndexNow."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import Database
from services.publication_channel import PublicationChannelService
from services.site import SiteService
from services.yandex_indexing import YandexIndexingService
from settings import config


def collect_urls(db_session) -> list[str]:
    site = SiteService.get_default(db_session)
    public = SiteService.public_config(site)
    base_url = (public.get("base_url") or config.SITE_BASE_URL).rstrip("/")

    urls: set[str] = {f"{base_url}/"}
    offset = 0
    while len(urls) < 50_000:
        batch = PublicationChannelService.list_public(
            db_session,
            site_id=site.id,
            limit=100,
            offset=offset,
        )
        if not batch:
            break

        for publication in batch:
            if publication.category is None:
                continue
            urls.add(
                f"{base_url}/category/{publication.category.slug}"
                f"/article/{publication.slug}"
            )

        if len(batch) < 100:
            break
        offset += len(batch)

    return sorted(urls)


def main() -> int:
    config.validate()
    if not config.YANDEX_INDEXNOW_ENABLED:
        print("IndexNow отключён: задайте YANDEX_INDEXNOW_ENABLED=true.")
        return 2

    db_session = Database.connect_database()
    try:
        urls = collect_urls(db_session)
    finally:
        db_session.close()

    statuses = YandexIndexingService.notify(urls)
    print(f"Передано URL в IndexNow: {len(urls)}")
    for host, status in statuses.items():
        print(f"{host}: HTTP {status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
