import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class MobilePublicationEditorContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_mobile_editor_styles_are_loaded(self):
        styles = self.read("templates/dashboard/styles.css")
        self.assertIn("/dashboard/publication/mobile-editor.css", styles)

    def test_mobile_editor_keeps_save_actions_reachable(self):
        styles = self.read("templates/dashboard/publication/mobile-editor.css")
        self.assertIn(".publication-editor-header__actions", styles)
        self.assertIn("position: fixed", styles)
        self.assertIn("safe-area-inset-bottom", styles)
        self.assertIn("min-height: 46px", styles)

    def test_mobile_editor_avoids_keyboard_and_ios_zoom_conflicts(self):
        styles = self.read("templates/dashboard/publication/mobile-editor.css")
        self.assertIn(":has(input:focus, textarea:focus, select:focus, .ql-editor:focus)", styles)
        self.assertIn("font-size: 16px", styles)
        self.assertIn("min-height: 44px", styles)

    def test_mobile_quill_toolbar_is_touch_friendly_and_sticky(self):
        styles = self.read("templates/dashboard/publication/mobile-editor.css")
        self.assertIn(".publication-body-field .ql-toolbar.ql-snow", styles)
        self.assertIn("position: sticky", styles)
        self.assertIn("top: 58px", styles)
        self.assertIn("overflow-x: auto", styles)
        self.assertIn("min-width: 36px", styles)

    def test_mobile_media_picker_uses_viewport_and_safe_area(self):
        styles = self.read("templates/dashboard/publication/mobile-editor.css")
        self.assertIn("max-height: calc(100dvh - 16px)", styles)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr))", styles)
        self.assertIn("@media (max-width: 430px)", styles)


if __name__ == "__main__":
    unittest.main()
