from __future__ import annotations

from pathlib import Path
import unittest

from models.vanga import VangaPrediction
from views.public.vanga.views import _prepare_prediction_payload


ROOT = Path(__file__).resolve().parents[1]


class VangaDiscoveryHistoryTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_prepare_payload_accepts_ajax_lists_and_imdb_id(self):
        form, payload, error = _prepare_prediction_payload(
            {
                "imdb_id": "tt0816692",
                "title": "Interstellar",
                "director": "Christopher Nolan",
                "year": "2014",
                "runtime": "169",
                "genres": ["Adventure", "Drama", "Sci-Fi"],
                "actors": ["Matthew McConaughey", "Anne Hathaway"],
            }
        )

        self.assertIsNone(error)
        self.assertEqual(payload["imdb_id"], "tt0816692")
        self.assertEqual(payload["genres"], ["Adventure", "Drama", "Sci-Fi"])
        self.assertEqual(payload["actors"][1], "Anne Hathaway")
        self.assertEqual(form["genres"], "Adventure, Drama, Sci-Fi")

    def test_prediction_snapshot_model_contains_reproducibility_fields(self):
        columns = VangaPrediction.__table__.columns

        for name in (
            "imdb_id",
            "title",
            "year",
            "model_generation",
            "rating",
            "request_data",
            "result_data",
            "created_at",
        ):
            self.assertIn(name, columns)

    def test_migration_and_ui_contract_exist(self):
        migration = self.read(
            "alembic/versions/e8c4a91d2f70_vanga_predictions.py"
        )
        template = self.read("templates/public/vanga/index.html")
        script = self.read("static/public/vanga-demo.js")

        self.assertIn('revision = "e8c4a91d2f70"', migration)
        self.assertIn('down_revision = "d2f7a91c4e60"', migration)
        self.assertIn('"vanga_predictions"', migration)

        self.assertIn("data-vanga-movie-search", template)
        self.assertIn("data-vanga-person-search", template)
        self.assertIn("data-vanga-genre-chips", template)
        self.assertIn("data-vanga-history", template)
        self.assertIn("data-predict-url", template)
        self.assertIn("data-search-url", template)

        self.assertIn("fetchSearch", script)
        self.assertIn("fetch(predictUrl", script)
        self.assertIn("jsint:vanga:history:v1", script)
        self.assertIn("X-CSRF-Token", script)
        self.assertIn("result_html", script)
        self.assertIn("analysis_html", script)


if __name__ == "__main__":
    unittest.main()
