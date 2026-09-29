from __future__ import annotations

import json
import logging
from collections import defaultdict
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from settings import config


logger = logging.getLogger(__name__)
_INDEXNOW_ENDPOINT = "https://yandex.com/indexnow"
_MAX_URLS_PER_REQUEST = 10_000


class YandexIndexingService:
    @staticmethod
    def _normalized_urls(urls: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for raw in urls:
            value = str(raw or "").strip()
            if not value or value in seen:
                continue

            parsed = urlsplit(value)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.fragment
            ):
                continue

            seen.add(value)
            result.append(value)
        return result

    @classmethod
    def enqueue(cls, urls: list[str]) -> None:
        if not config.YANDEX_INDEXNOW_ENABLED:
            return

        normalized = cls._normalized_urls(urls)
        if not normalized:
            return

        # Импорт внутри метода не создаёт цикл при регистрации Celery-задач.
        from celery_app import celery_app

        try:
            celery_app.send_task(
                "tasks.system.notify_yandex_indexnow",
                args=[normalized],
            )
        except Exception as exc:
            logger.warning(
                "Не удалось поставить IndexNow в фоновую очередь: %s",
                type(exc).__name__,
            )

    @classmethod
    def notify(cls, urls: list[str]) -> dict[str, int]:
        if not config.YANDEX_INDEXNOW_ENABLED:
            return {}

        normalized = cls._normalized_urls(urls)
        grouped: dict[str, list[str]] = defaultdict(list)
        origins: dict[str, str] = {}

        for url in normalized:
            parsed = urlsplit(url)
            host = parsed.hostname or ""
            if parsed.port:
                host = f"{host}:{parsed.port}"
            grouped[host].append(url)
            origins[host] = f"{parsed.scheme}://{host}"

        statuses: dict[str, int] = {}
        for host, host_urls in grouped.items():
            for start in range(0, len(host_urls), _MAX_URLS_PER_REQUEST):
                batch = host_urls[start:start + _MAX_URLS_PER_REQUEST]
                payload = {
                    "host": host,
                    "key": config.YANDEX_INDEXNOW_KEY,
                    "keyLocation": (
                        f"{origins[host]}/{config.YANDEX_INDEXNOW_KEY}.txt"
                    ),
                    "urlList": batch,
                }
                request = Request(
                    _INDEXNOW_ENDPOINT,
                    data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json; charset=utf-8",
                        "User-Agent": "jsint-site-indexnow/1.0",
                    },
                    method="POST",
                )

                try:
                    with urlopen(request, timeout=5) as response:
                        status = int(response.status)
                except HTTPError as exc:
                    status = int(exc.code)
                    if status == 429 or status >= 500:
                        raise RuntimeError(
                            f"IndexNow временно недоступен: HTTP {status}"
                        ) from exc
                    logger.warning(
                        "IndexNow отклонил URL для %s: HTTP %s",
                        host,
                        status,
                    )
                except (OSError, URLError) as exc:
                    raise RuntimeError("Не удалось отправить IndexNow") from exc

                statuses[host] = status
                if status not in {200, 202} and status < 400:
                    logger.warning(
                        "Неожиданный ответ IndexNow для %s: HTTP %s",
                        host,
                        status,
                    )

        return statuses
