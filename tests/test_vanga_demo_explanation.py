from __future__ import annotations

from pathlib import Path
import unittest

from views.public.vanga.views import _prediction_output


ROOT = Path(__file__).resolve().parents[1]


class VangaDemoExplanationTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_prediction_output_sorts_and_explains_all_contributions(self):
        result = _prediction_output(
            {
                "rating": 7.31,
                "base": 6.10,
                "contributions": {
                    "genres_combined": -0.43,
                    "director_avg_rating": 0.67,
                    "actor_1_id": 0.0,
                },
                "input_resolution": {
                    "title": {
                        "input": "Интерстеллар",
                        "canonical": "Interstellar",
                        "imdb_id": "tt0816692",
                    },
                    "director": {
                        "input": "Кристофер Нолан",
                        "canonical": "Christopher Nolan",
                        "imdb_id": "nm0634240",
                    },
                    "actors": [],
                },
            }
        )

        self.assertEqual(result["rating"], 7.31)
        self.assertEqual(result["base"], 6.10)
        self.assertEqual(result["factor_count"], 3)
        self.assertEqual(result["factors"][0]["key"], "director_avg_rating")
        self.assertEqual(result["factors"][0]["tone"], "positive")
        self.assertEqual(result["factors"][1]["tone"], "negative")
        self.assertEqual(result["factors"][2]["tone"], "neutral")
        self.assertEqual(result["factors"][0]["strength"], 100.0)
        self.assertEqual(len(result["recognized_inputs"]), 2)
        self.assertEqual(
            result["recognized_inputs"][0]["canonical"],
            "Interstellar",
        )

    def test_template_renders_full_shap_breakdown(self):
        template = "\n".join(
            [
                self.read("templates/public/vanga/index.html"),
                self.read("templates/public/vanga/_result.html"),
                self.read("templates/public/vanga/_analysis.html"),
            ]
        )

        self.assertIn("Полная расшифровка", template)
        self.assertIn("Все факторы этого прогноза", template)
        self.assertIn("SHAP-вклад", template)
        self.assertIn("prediction_output.positive_total", template)
        self.assertIn("prediction_output.negative_total", template)
        self.assertIn("for factor in prediction_output.factors", template)
        self.assertIn("factor.description", template)
        self.assertIn("factor.key", template)
        self.assertIn("Распознано по русскому вводу", template)
        self.assertIn("prediction_output.recognized_inputs", template)
        self.assertIn("public/vanga-demo.js", template)

    def test_animation_keeps_reduced_motion_fallback(self):
        script = self.read("static/public/vanga-demo.js")
        styles = self.read("templates/public/vanga/style.css")

        self.assertIn("prefers-reduced-motion: reduce", script)
        self.assertIn("IntersectionObserver", script)
        self.assertIn("data-vanga-submit-status", script)
        self.assertIn("data-rating-value", script)
        self.assertIn("scrollIntoView", script)
        self.assertIn("fetch(predictUrl", script)
        self.assertIn("localStorage", script)
        self.assertIn("data-vanga-movie-search", self.read("templates/public/vanga/index.html"))
        self.assertIn("@media(prefers-reduced-motion:reduce)", styles)
        self.assertIn(".vanga-result__score-ring", styles)
        self.assertIn(".vanga-factor-card", styles)


if __name__ == "__main__":
    unittest.main()
