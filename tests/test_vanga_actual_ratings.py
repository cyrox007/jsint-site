from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from models.vanga import VangaPrediction
from services.vanga_predictions import VangaPredictionService
from settings import config


ROOT = Path(__file__).resolve().parents[1]


class VangaActualRatingsTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_sync_updates_actual_rating_and_absolute_error(self):
        record = VangaPrediction(
            site_id=uuid4(),
            imdb_id="tt0816692",
            title="Interstellar",
            year=2014,
            model_generation="generation-test",
            rating=Decimal("7.30"),
            request_data={},
            result_data={},
        )

        query = MagicMock()
        query.filter.return_value = query
        query.order_by.return_value = query
        query.limit.return_value = query
        query.all.return_value = [record]

        db = MagicMock()
        db.query.return_value = query

        actual = [
            {
                "imdb_id": "tt0816692",
                "title": "Interstellar",
                "year": 2014,
                "rating": 8.70,
                "num_votes": 2200000,
            }
        ]

        with (
            patch.object(
                VangaPredictionService,
                "_fetch_actual_ratings",
                return_value=actual,
            ),
            patch.object(config, "VANGA_ACTUAL_MIN_VOTES", 1000),
            patch.object(config, "VANGA_ACTUAL_REFRESH_HOURS", 24),
        ):
            result = VangaPredictionService.sync_actual_ratings(
                db,
                batch_limit=10,
            )

        self.assertEqual(result["updated"], 1)
        self.assertEqual(record.actual_rating, Decimal("8.70"))
        self.assertEqual(record.actual_num_votes, 2200000)
        self.assertEqual(record.absolute_error, Decimal("1.40"))
        self.assertIsNotNone(record.actual_rating_updated_at)
        db.commit.assert_called_once()

    def test_low_vote_rating_is_not_published_as_verified(self):
        record = VangaPrediction(
            site_id=uuid4(),
            imdb_id="tt0000001",
            title="Future movie",
            year=2027,
            rating=Decimal("7.00"),
            request_data={},
            result_data={},
        )

        query = MagicMock()
        query.filter.return_value = query
        query.order_by.return_value = query
        query.limit.return_value = query
        query.all.return_value = [record]

        db = MagicMock()
        db.query.return_value = query

        with (
            patch.object(
                VangaPredictionService,
                "_fetch_actual_ratings",
                return_value=[
                    {
                        "imdb_id": "tt0000001",
                        "rating": 9.0,
                        "num_votes": 12,
                    }
                ],
            ),
            patch.object(config, "VANGA_ACTUAL_MIN_VOTES", 1000),
            patch.object(config, "VANGA_ACTUAL_REFRESH_HOURS", 24),
        ):
            result = VangaPredictionService.sync_actual_ratings(
                db,
                batch_limit=10,
            )

        self.assertEqual(result["updated"], 0)
        self.assertEqual(result["skipped"], 1)
        self.assertIsNone(record.actual_rating)
        self.assertIsNone(record.absolute_error)

    def test_migration_scheduler_and_public_comparison_contract(self):
        migration = self.read(
            "alembic/versions/f6b1d4c7e820_vanga_actual_ratings.py"
        )
        celery = self.read("celery_app.py")
        tasks = self.read("tasks/system.py")
        template = self.read("templates/public/vanga/index.html")

        self.assertIn('revision = "f6b1d4c7e820"', migration)
        self.assertIn('down_revision = "e8c4a91d2f70"', migration)
        self.assertIn('"actual_rating"', migration)
        self.assertIn('"absolute_error"', migration)

        self.assertIn("sync-vanga-actual-ratings", celery)
        self.assertIn("tasks.system.sync_vanga_actual_ratings", celery)
        self.assertIn("def sync_vanga_actual_ratings", tasks)

        self.assertIn("Vanga против реальности", template)
        self.assertIn("Последние сверенные прогнозы", template)
        self.assertIn("item.actual_rating", template)
        self.assertIn("item.absolute_error", template)


if __name__ == "__main__":
    unittest.main()
