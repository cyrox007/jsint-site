from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class VangaWhatIfCompareTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_result_can_be_pinned_as_variant_a(self):
        result = self.read("templates/public/vanga/_result.html")

        self.assertIn("data-vanga-pin", result)
        self.assertIn("Зафиксировать вариант A", result)
        self.assertIn("data-generation", result)
        self.assertIn("data-rating", result)

    def test_compare_panel_explains_delta_and_changed_fields(self):
        template = self.read("templates/public/vanga/index.html")

        self.assertIn("data-vanga-compare", template)
        self.assertIn("What-if конструктор", template)
        self.assertIn("Сравнение двух сценариев", template)
        self.assertIn("data-vanga-compare-delta", template)
        self.assertIn("data-vanga-compare-changes", template)
        self.assertIn("Сбросить сравнение", template)

    def test_javascript_compares_only_same_model_generation(self):
        script = self.read("static/public/vanga-demo.js")

        self.assertIn("jsint:vanga:compare:v1", script)
        self.assertIn("renderComparison", script)
        self.assertIn("changedFields", script)
        self.assertIn('["writer", "Сценарист"]', script)
        self.assertIn("baselineGeneration !== currentGeneration", script)
        self.assertIn("Для честного what-if сравнения", script)
        self.assertIn("what-if сравнение сценариев", script)
        self.assertIn("delta.toFixed(2)", script)

    def test_compare_styles_are_responsive(self):
        styles = self.read("templates/public/vanga/style.css")

        self.assertIn(".vanga-compare-action", styles)
        self.assertIn(".vanga-compare__scores", styles)
        self.assertIn(".vanga-compare__changes", styles)
        self.assertIn("@media(max-width:760px)", styles)


if __name__ == "__main__":
    unittest.main()
