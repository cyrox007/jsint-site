from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import unittest
from uuid import uuid4

from models.vanga import VangaPrediction
from views.public.vanga.views import _prediction_from_snapshot


ROOT = Path(__file__).resolve().parents[1]


class VangaShareSnapshotTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_snapshot_reconstructs_prediction_without_new_inference(self):
        record = VangaPrediction(
            id=uuid4(),
            site_id=uuid4(),
            imdb_id="tt0816692",
            title="Interstellar",
            year=2014,
            model_generation="generation-test",
            rating=Decimal("7.31"),
            request_data={
                "title": "Interstellar",
                "director": "Christopher Nolan",
                "year": 2014,
                "runtime": 169,
                "genres": ["Adventure", "Drama", "Sci-Fi"],
                "actors": ["Matthew McConaughey", "Anne Hathaway"],
            },
            result_data={
                "base": 6.10,
                "contributions": {"director_avg_rating": 0.67},
                "input_resolution": {},
                "uncertainty": {
                    "lower": 6.1,
                    "upper": 8.5,
                    "margin": 1.2,
                    "coverage": 0.8,
                },
                "quality": {"mae": 1.02},
            },
        )

        prediction, form = _prediction_from_snapshot(record)

        self.assertEqual(prediction["rating"], 7.31)
        self.assertEqual(prediction["generation"], "generation-test")
        self.assertEqual(prediction["contributions"]["director_avg_rating"], 0.67)
        self.assertEqual(form["director"], "Christopher Nolan")
        self.assertEqual(form["genres"], "Adventure, Drama, Sci-Fi")

    def test_share_route_ui_and_javascript_contract(self):
        router = self.read("views/public/vanga/routers.py")
        view = self.read("views/public/vanga/views.py")
        result = self.read("templates/public/vanga/_result.html")
        script = self.read("static/public/vanga-demo.js")
        styles = self.read("templates/public/vanga/style.css")

        self.assertIn('"/demo/vanga/p/<uuid:snapshot_id>"', router)
        self.assertIn('endpoint="vanga_snapshot"', router)
        self.assertIn("def vanga_snapshot", view)
        self.assertIn("_prediction_from_snapshot", view)
        self.assertIn("seo_noindex", view)

        self.assertIn("data-vanga-share", result)
        self.assertIn("Постоянная ссылка", result)
        self.assertIn("snapshot_url", result)

        self.assertIn("navigator.share", script)
        self.assertIn("navigator.clipboard", script)
        self.assertIn("data-vanga-share-status", script)
        self.assertIn(".vanga-share", styles)


if __name__ == "__main__":
    unittest.main()
