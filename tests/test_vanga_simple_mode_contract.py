from __future__ import annotations

import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class VangaSimpleModeContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_simple_mode_script_is_always_loaded(self):
        analysis = self.read("templates/public/vanga/_analysis.html")
        self.assertIn("public/vanga-simple-mode.js", analysis)

    def test_advanced_controls_are_hidden_by_default(self):
        script = self.read("static/public/vanga-simple-mode.js")
        self.assertIn('root.dataset.vangaMode = "simple"', script)
        self.assertIn("Расширенный режим", script)
        self.assertIn("vanga-advanced-control", script)
        self.assertIn(".vanga-demo:not(.is-advanced) .vanga-advanced-control", script)
        self.assertIn("setAdvanced(false)", script)

    def test_future_catalog_is_lazy_loaded_only_for_advanced_mode(self):
        script = self.read("static/public/vanga-simple-mode.js")
        self.assertIn("ensureFutureAssets", script)
        self.assertIn("/static/public/vanga-future.js", script)
        self.assertIn("/static/public/vanga-future.css", script)
        self.assertIn("if (enabled) ensureFutureAssets()", script)
        self.assertIn(".vanga-demo:not(.is-advanced) .vanga-future", script)

    def test_simple_mode_blocks_manual_incomplete_submission_with_clear_hint(self):
        script = self.read("static/public/vanga-simple-mode.js")
        self.assertIn('const requiredAdvancedFields = ["director", "year", "runtime", "genres"]', script)
        self.assertIn("Выберите фильм из выпадающих подсказок", script)
        self.assertIn("Для ручного ввода откройте расширенный режим", script)

    def test_what_if_is_advanced_only(self):
        script = self.read("static/public/vanga-simple-mode.js")
        self.assertIn(".vanga-demo:not(.is-advanced) .vanga-compare", script)


if __name__ == "__main__":
    unittest.main()
