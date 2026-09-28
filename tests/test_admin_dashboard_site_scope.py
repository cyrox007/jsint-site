from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AdminDashboardSiteScopeTests(unittest.TestCase):
    def test_dashboard_counts_content_for_selected_site(self):
        source = (ROOT / "views/dashboard/main/views.py").read_text(encoding="utf-8")
        self.assertIn("selected_site = resolve_admin_site(db_session)", source)
        self.assertIn("PublicationSite.site_id == selected_site.id", source)
        self.assertIn("Category.site_id == selected_site.id", source)

    def test_dashboard_actions_preserve_workspace(self):
        template = (ROOT / "templates/dashboard/main/index.html").read_text(encoding="utf-8")
        self.assertIn("selected_site.name", template)
        self.assertIn("admin.publication.index", template)
        self.assertIn("site_id=selected_site.id", template)
        self.assertIn("admin.catalog.index", template)
        self.assertIn("admin.pages.index", template)
        self.assertIn("admin.media.index", template)


if __name__ == "__main__":
    unittest.main()
