from __future__ import annotations

from pathlib import Path
import unittest

from views.public.vanga.potential import _source_payload


ROOT = Path(__file__).resolve().parents[1]


class VangaPotentialProfileTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_source_payload_is_normalized_without_post_release_fields(self):
        source, error = _source_payload(
            {
                "source": {
                    "type": "роман",
                    "title": "Пример",
                    "author": "Автор",
                    "format": "фильм",
                    "series_size": "3",
                    "review_after_release": "не должно пройти",
                }
            }
        )

        self.assertIsNone(error)
        self.assertEqual(source["series_size"], 3)
        self.assertEqual(source["type"], "роман")
        self.assertNotIn("review_after_release", source)

    def test_source_payload_rejects_invalid_series_size(self):
        source, error = _source_payload(
            {"source": {"series_size": "не число"}}
        )

        self.assertEqual(source, {})
        self.assertIn("целым числом", error)

    def test_routes_and_form_expose_potential_analysis(self):
        router = self.read("views/public/vanga/routers.py")
        template = self.read("templates/public/vanga/index.html")
        script = self.read("static/public/vanga-potential.js")

        self.assertIn('"/demo/vanga/predict-profile"', router)
        self.assertIn('endpoint="vanga_predict_profile_api"', router)
        self.assertIn('"/demo/vanga/p/<uuid:snapshot_id>/potential"', router)

        self.assertIn("data-vanga-potential-host", template)
        self.assertIn('name="synopsis"', template)
        self.assertIn('name="source_type"', template)
        self.assertIn('name="source_title"', template)
        self.assertIn('name="source_author"', template)
        self.assertIn("vanga_predict_profile_api", template)
        self.assertIn("vanga-potential.js", template)
        self.assertIn("data-coverage-style.css", template)

        self.assertIn('body.synopsis = value("synopsis")', script)
        self.assertIn("body.source = sourcePayload()", script)
        self.assertIn("profile_html", script)
        self.assertIn("/potential", script)

    def test_profile_ui_does_not_present_diagnostic_layer_as_fact(self):
        partial = self.read("templates/public/vanga/_potential.html")

        self.assertIn("Потенциал и вероятные риски", partial)
        self.assertIn("Вероятные сильные стороны", partial)
        self.assertIn("Вероятные слабые места", partial)
        self.assertIn("риски, а не факты", partial)
        self.assertIn("эвристика синопсиса", partial)
        self.assertIn("Покрытие исходных данных", partial)

    def test_profile_ui_exposes_model_familiarity_and_abstention(self):
        partial = self.read("templates/public/vanga/_potential.html")
        css = self.read("templates/public/vanga/data-coverage-style.css")

        self.assertIn("Знакомство модели с командой", partial)
        self.assertIn("known_people_count", partial)
        self.assertIn("provided_people_count", partial)
        self.assertIn("missing_feature_count", partial)
        self.assertIn("abstention.get('recommended')", partial)
        self.assertIn("Низкая обеспеченность историческими данными", partial)
        self.assertIn("resolved_no_history", partial)
        self.assertIn("не удалось сопоставить с IMDb", partial)
        self.assertIn("vanga-potential__abstention", css)

    def test_profile_ui_keeps_legacy_profile_compatible(self):
        partial = self.read("templates/public/vanga/_potential.html")

        self.assertIn("person.get('prior_count', person.get('works_count', 0))", partial)
        self.assertIn("{% if familiarity %}", partial)
        self.assertIn("{% elif person.get('state') %}", partial)
        self.assertIn("недостаточно исторических данных", partial)

    def test_snapshot_persists_profile_and_pre_release_context(self):
        endpoint = self.read("views/public/vanga/potential.py")

        self.assertIn('request_data["synopsis"]', endpoint)
        self.assertIn('request_data["source"]', endpoint)
        self.assertIn('result_data["pre_release_profile"]', endpoint)
        self.assertIn("сохранённый pre-release профиль", endpoint.lower())


if __name__ == "__main__":
    unittest.main()
