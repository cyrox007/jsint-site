from __future__ import annotations

import unittest
from pathlib import Path

from views.public.vanga.potential import _group_factors, _team_payload


ROOT = Path(__file__).resolve().parents[1]


class VangaP10TeamContractTests(unittest.TestCase):
    def test_team_payload_preserves_director_order_and_full_cast(self) -> None:
        actors = [f"Actor {index}" for index in range(40)]
        payload, error = _team_payload(
            {
                "director": "Primary Director",
                "directors": [
                    "Primary Director",
                    "Second Director",
                    "Third Director",
                    "Second Director",
                ],
                "actors": actors,
            }
        )
        self.assertIsNone(error)
        self.assertEqual(
            payload["directors"],
            ["Primary Director", "Second Director", "Third Director"],
        )
        self.assertEqual(payload["director"], "Primary Director")
        self.assertEqual(len(payload["actors"]), 32)
        self.assertEqual(payload["actors"][0], "Actor 0")
        self.assertEqual(payload["actors"][-1], "Actor 31")

    def test_grouped_shap_keeps_original_factors_and_aggregates(self) -> None:
        output = {
            "factors": [
                {"key": "director_avg_rating", "value": 0.4},
                {"key": "director_recent_trend", "value": -0.1},
                {"key": "writer_avg_rating", "value": 0.2},
                {"key": "cast_known_ratio", "value": -0.3},
            ]
        }
        _group_factors(output)
        groups = {item["key"]: item for item in output["factor_groups"]}

        self.assertEqual(len(output["factors"]), 4)
        self.assertAlmostEqual(groups["director"]["value"], 0.3)
        self.assertAlmostEqual(groups["screenplay"]["value"], 0.2)
        self.assertAlmostEqual(groups["cast"]["value"], -0.3)
        self.assertEqual(output["factors"][0]["group_label"], "Режиссура")

    def test_frontend_progressive_enhancement_contract(self) -> None:
        potential = (ROOT / "static/public/vanga-potential.js").read_text(encoding="utf-8")
        team = (ROOT / "static/public/vanga-team.js").read_text(encoding="utf-8")
        analysis = (ROOT / "templates/public/vanga/_analysis.html").read_text(encoding="utf-8")

        self.assertIn("body.directors = directors", potential)
        self.assertIn(".slice(0, 32)", potential)
        self.assertIn("hidden.dataset.vangaTeamValues = role", team)
        self.assertIn("Режиссёрская команда", team)
        self.assertIn("Grouped SHAP", analysis)
        self.assertIn("prediction_output.factor_groups", analysis)


if __name__ == "__main__":
    unittest.main()
