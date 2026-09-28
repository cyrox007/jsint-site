from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AdminSiteWorkspaceContractTests(unittest.TestCase):
    def test_header_has_global_site_switcher(self):
        template = (
            ROOT / "templates/dashboard/^shared/header/index.html"
        ).read_text(encoding="utf-8")
        self.assertIn("admin.site-workspace", template)
        self.assertIn('name="site_id"', template)
        self.assertIn("admin_selected_site", template)

    def test_content_and_media_use_shared_workspace(self):
        blog = (ROOT / "views/dashboard/blog/views.py").read_text(encoding="utf-8")
        media = (ROOT / "views/dashboard/media/views.py").read_text(encoding="utf-8")
        self.assertIn("resolve_admin_site", blog)
        self.assertIn("resolve_admin_site", media)

    def test_workspace_redirect_is_limited_to_admin_prefix(self):
        source = (ROOT / "views/dashboard/main/views.py").read_text(encoding="utf-8")
        self.assertIn("parsed.scheme", source)
        self.assertIn("parsed.netloc", source)
        self.assertIn("config.ADMIN_ROUTE_PREFIX", source)

    def test_sidebar_preserves_current_site(self):
        template = (
            ROOT / "templates/dashboard/^shared/sidebar/index.html"
        ).read_text(encoding="utf-8")
        self.assertIn("admin_selected_site.id", template)
        self.assertIn("admin.publication.index", template)
        self.assertIn("admin.media.index", template)


if __name__ == "__main__":
    unittest.main()
