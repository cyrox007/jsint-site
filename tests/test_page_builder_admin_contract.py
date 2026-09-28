from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PageBuilderAdminContractTests(unittest.TestCase):
    def test_generic_page_service_supports_crud(self):
        source = (ROOT / "services/page.py").read_text(encoding="utf-8")
        for name in (
            "list_pages",
            "create_page",
            "update_page",
            "add_block",
            "update_block",
            "delete_block",
            "delete_page",
        ):
            self.assertIn(f"def {name}", source)
        self.assertIn('if page.slug == "home"', source)

    def test_page_builder_is_registered(self):
        app_source = (ROOT / "app.py").read_text(encoding="utf-8")
        sidebar = (
            ROOT / "templates/dashboard/^shared/sidebar/index.html"
        ).read_text(encoding="utf-8")
        self.assertIn("d_pages_router.install(app)", app_source)
        self.assertIn("admin.pages.index", sidebar)

    def test_block_links_reject_unsafe_schemes(self):
        source = (
            ROOT / "views/dashboard/pages/views.py"
        ).read_text(encoding="utf-8")
        self.assertIn('parsed.scheme in {"http", "https"}', source)
        self.assertIn('parsed.scheme == "mailto"', source)
        self.assertNotIn('"javascript"', source)

    def test_builder_does_not_expose_raw_json_editor(self):
        template = (
            ROOT / "templates/dashboard/pages/edit.html"
        ).read_text(encoding="utf-8")
        self.assertNotIn('name="settings"', template)
        self.assertIn('name="block_type"', template)
        self.assertIn('name="block_title"', template)


if __name__ == "__main__":
    unittest.main()
