from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sqlalchemy import or_
from sqlalchemy.orm import Session

from models.vanga import VangaPrediction
from settings import config


logger = logging.getLogger(__name__)


class VangaPredictionService:
    """Сверяет сохранённые прогнозы с текущим локальным IMDb rating."""

    @staticmethod
    def _fetch_actual_ratings(imdb_ids: list[str]) -> list[dict]:
        if not imdb_ids:
            return []

        request = Request(
            f"{config.VANGA_DEMO_URL}/catalog/ratings",
            data=json.dumps(
                {"imdb_ids": imdb_ids[:100]},
                ensure_ascii=False,
            ).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(
                request,
                timeout=config.VANGA_DEMO_TIMEOUT_SECONDS,
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(
                f"Vanga catalog ratings вернул HTTP {exc.code}"
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(
                "Vanga catalog ratings временно недоступен"
            ) from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                "Vanga catalog ratings вернул некорректный ответ"
            ) from exc

        if not isinstance(payload, dict) or not payload.get("ok"):
            raise RuntimeError("Vanga не подтвердил чтение IMDb ratings")
        items = payload.get("items")
        return items if isinstance(items, list) else []

    @staticmethod
    def _decimal_rating(value) -> Decimal | None:
        try:
            parsed = Decimal(str(value)).quantize(Decimal("0.01"))
        except (InvalidOperation, TypeError, ValueError):
            return None
        if parsed < 0 or parsed > 10:
            return None
        return parsed

    @classmethod
    def sync_actual_ratings(
        cls,
        db: Session,
        *,
        batch_limit: int | None = None,
    ) -> dict[str, int]:
        """Обновляет actual rating для pending/stale snapshots.

        Один и тот же фильм может иметь несколько исторических прогнозов.
        Текущий IMDb rating применяется к каждому такому snapshot отдельно,
        поэтому абсолютная ошибка остаётся привязана к конкретной версии
        модели и времени прогноза.
        """
        now = datetime.now(timezone.utc)
        stale_before = now - timedelta(
            hours=config.VANGA_ACTUAL_REFRESH_HOURS
        )
        limit = max(
            1,
            min(
                int(batch_limit or config.VANGA_ACTUAL_SYNC_BATCH),
                1000,
            ),
        )

        records = (
            db.query(VangaPrediction)
            .filter(VangaPrediction.imdb_id.isnot(None))
            .filter(
                or_(
                    VangaPrediction.actual_rating_updated_at.is_(None),
                    VangaPrediction.actual_rating_updated_at < stale_before,
                )
            )
            .order_by(VangaPrediction.created_at.asc())
            .limit(limit)
            .all()
        )
        if not records:
            return {"checked": 0, "updated": 0, "skipped": 0}

        imdb_ids: list[str] = []
        seen: set[str] = set()
        for record in records:
            imdb_id = str(record.imdb_id or "")
            if imdb_id and imdb_id not in seen:
                seen.add(imdb_id)
                imdb_ids.append(imdb_id)

        actual_by_id: dict[str, dict] = {}
        for start in range(0, len(imdb_ids), 100):
            items = cls._fetch_actual_ratings(imdb_ids[start:start + 100])
            for item in items:
                if not isinstance(item, dict):
                    continue
                imdb_id = str(item.get("imdb_id") or "")
                if imdb_id:
                    actual_by_id[imdb_id] = item

        updated = 0
        skipped = 0
        for record in records:
            actual = actual_by_id.get(str(record.imdb_id or ""))
            if actual is None:
                skipped += 1
                continue

            rating = cls._decimal_rating(actual.get("rating"))
            try:
                votes = int(actual.get("num_votes") or 0)
            except (TypeError, ValueError):
                votes = 0

            if rating is None or votes < config.VANGA_ACTUAL_MIN_VOTES:
                skipped += 1
                continue

            predicted = cls._decimal_rating(record.rating)
            if predicted is None:
                skipped += 1
                continue

            record.actual_rating = rating
            record.actual_num_votes = votes
            record.absolute_error = abs(predicted - rating).quantize(
                Decimal("0.01")
            )
            record.actual_rating_updated_at = now
            db.add(record)
            updated += 1

        db.commit()
        return {
            "checked": len(records),
            "updated": updated,
            "skipped": skipped,
        }

    @staticmethod
    def recent_verified(
        db: Session,
        *,
        site_id,
        limit: int = 6,
    ) -> list[VangaPrediction]:
        """Возвращает последние сверенные прогнозы без дублей фильма."""
        candidates = (
            db.query(VangaPrediction)
            .filter(VangaPrediction.site_id == site_id)
            .filter(VangaPrediction.actual_rating.isnot(None))
            .filter(VangaPrediction.absolute_error.isnot(None))
            .order_by(VangaPrediction.actual_rating_updated_at.desc())
            .limit(max(20, limit * 5))
            .all()
        )

        result: list[VangaPrediction] = []
        seen: set[str] = set()
        for record in candidates:
            key = record.imdb_id or f"{record.title.casefold()}:{record.year}"
            if key in seen:
                continue
            seen.add(key)
            result.append(record)
            if len(result) >= limit:
                break
        return result
