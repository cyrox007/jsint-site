from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sqlalchemy import func, or_
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
        """Обновляет actual rating для pending/stale snapshots."""
        now = datetime.now(timezone.utc)
        stale_before = now - timedelta(hours=config.VANGA_ACTUAL_REFRESH_HOURS)
        limit = max(1, min(int(batch_limit or config.VANGA_ACTUAL_SYNC_BATCH), 1000))

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
            record.absolute_error = abs(predicted - rating).quantize(Decimal("0.01"))
            record.actual_rating_updated_at = now
            db.add(record)
            updated += 1

        db.commit()
        return {"checked": len(records), "updated": updated, "skipped": skipped}

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

    @staticmethod
    def verification_summary(
        db: Session,
        *,
        site_id,
    ) -> dict[str, float | int | None]:
        """Агрегат по уже сверенным снимкам без искусственного ранжирования."""
        count, avg_error = (
            db.query(
                func.count(VangaPrediction.id),
                func.avg(VangaPrediction.absolute_error),
            )
            .filter(VangaPrediction.site_id == site_id)
            .filter(VangaPrediction.absolute_error.isnot(None))
            .one()
        )
        return {
            "count": int(count or 0),
            "mae": round(float(avg_error), 2) if avg_error is not None else None,
        }

    @staticmethod
    def _coverage_value(record: VangaPrediction) -> float | None:
        result = record.result_data if isinstance(record.result_data, dict) else {}
        profile = result.get("pre_release_profile")
        profile = profile if isinstance(profile, dict) else {}
        candidates = [
            profile.get("data_coverage"),
            profile.get("coverage"),
            result.get("data_coverage"),
        ]
        for candidate in candidates:
            if isinstance(candidate, dict):
                for key in ("ratio", "score", "value", "known_ratio"):
                    raw = candidate.get(key)
                    try:
                        value = float(raw)
                    except (TypeError, ValueError):
                        continue
                    if 0 <= value <= 1:
                        return value
                    if 1 < value <= 100:
                        return value / 100.0
            else:
                try:
                    value = float(candidate)
                except (TypeError, ValueError):
                    continue
                if 0 <= value <= 1:
                    return value
                if 1 < value <= 100:
                    return value / 100.0
        return None

    @classmethod
    def _coverage_bin(cls, record: VangaPrediction) -> tuple[str, str]:
        value = cls._coverage_value(record)
        if value is None:
            return "unknown", "Не определено"
        if value < 0.4:
            return "low", "Низкое (<40%)"
        if value < 0.7:
            return "medium", "Среднее (40–69%)"
        return "high", "Высокое (≥70%)"

    @staticmethod
    def _aggregate_rows(groups: dict[str, dict]) -> list[dict]:
        rows: list[dict] = []
        for key, item in groups.items():
            errors = item["errors"]
            if not errors:
                continue
            rows.append(
                {
                    "key": key,
                    "label": item["label"],
                    "count": len(errors),
                    "mae": round(sum(errors) / len(errors), 2),
                    "mean_predicted": round(sum(item["predicted"]) / len(errors), 2),
                    "mean_actual": round(sum(item["actual"]) / len(errors), 2),
                }
            )
        return rows

    @classmethod
    def accuracy_report(cls, db: Session, *, site_id) -> dict:
        """Строит честный отчёт только по уже сверенным immutable snapshots."""
        records = (
            db.query(VangaPrediction)
            .filter(VangaPrediction.site_id == site_id)
            .filter(VangaPrediction.actual_rating.isnot(None))
            .filter(VangaPrediction.absolute_error.isnot(None))
            .order_by(VangaPrediction.created_at.asc())
            .all()
        )

        generations: dict[str, dict] = defaultdict(
            lambda: {"label": "", "errors": [], "predicted": [], "actual": []}
        )
        years: dict[str, dict] = defaultdict(
            lambda: {"label": "", "errors": [], "predicted": [], "actual": []}
        )
        coverage: dict[str, dict] = defaultdict(
            lambda: {"label": "", "errors": [], "predicted": [], "actual": []}
        )

        all_errors: list[float] = []
        latest_actual_at = None
        for record in records:
            error = float(record.absolute_error)
            predicted = float(record.rating)
            actual = float(record.actual_rating)
            all_errors.append(error)
            if record.actual_rating_updated_at and (
                latest_actual_at is None or record.actual_rating_updated_at > latest_actual_at
            ):
                latest_actual_at = record.actual_rating_updated_at

            generation = str(record.model_generation or "legacy")
            generation_item = generations[generation]
            generation_item["label"] = generation

            year_key = str(record.year)
            year_item = years[year_key]
            year_item["label"] = year_key

            coverage_key, coverage_label = cls._coverage_bin(record)
            coverage_item = coverage[coverage_key]
            coverage_item["label"] = coverage_label

            for item in (generation_item, year_item, coverage_item):
                item["errors"].append(error)
                item["predicted"].append(predicted)
                item["actual"].append(actual)

        generation_rows = cls._aggregate_rows(generations)
        generation_rows.sort(key=lambda item: item["label"], reverse=True)
        year_rows = cls._aggregate_rows(years)
        year_rows.sort(key=lambda item: item["label"], reverse=True)
        coverage_rows = cls._aggregate_rows(coverage)
        order = {"low": 0, "medium": 1, "high": 2, "unknown": 3}
        coverage_rows.sort(key=lambda item: order.get(item["key"], 99))

        return {
            "count": len(records),
            "mae": round(sum(all_errors) / len(all_errors), 2) if all_errors else None,
            "latest_actual_at": latest_actual_at,
            "by_generation": generation_rows,
            "by_year": year_rows,
            "by_coverage": coverage_rows,
            "disclaimer": (
                "IMDb rating продолжает меняться; отчёт показывает последнее сохранённое "
                "фактическое значение и никогда не пересчитывает исходный прогноз."
            ),
        }
