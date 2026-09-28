import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class SiteFoundationContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_public_identity_is_database_backed(self):
        self.assertIn("class Site(Database.Base)", self.read("models/sites.py"))
        self.assertIn("SiteService.get_current", self.read("views/public/home/views.py"))

    def test_admin_has_sites_control_plane(self):
        self.assertIn("<span>Сайты</span>", self.read("templates/dashboard/^shared/sidebar/index.html"))
        self.assertIn('"admin.sites.index"', self.read("views/dashboard/sites/router.py"))

    def test_public_templates_are_not_brand_hardcoded(self):
        for path in (
            "templates/public/^shared/header/index.html",
            "templates/public/^shared/footer/index.html",
            "templates/public/home/section/hero.html",
            "templates/public/home/section/philosophy.html",
            "templates/public/home/section/about.html",
        ):
            content = self.read(path)
            self.assertNotIn("+УЛЬТРА", content)
            self.assertNotIn("cyrox007@gmail.com", content)

    def test_home_sections_do_not_embed_style_blocks(self):
        for path in (
            "templates/public/home/section/hero.html",
            "templates/public/home/section/philosophy.html",
            "templates/public/home/section/about.html",
            "templates/public/home/section/systems.html",
        ):
            self.assertNotIn("<style", self.read(path))


if __name__ == "__main__":
    unittest.main()
