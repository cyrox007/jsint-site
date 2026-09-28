import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class MultisiteContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_site_registry_and_content_scope_exist(self):
        site_model = self.read("models/site.py")
        category_model = self.read("models/categories.py")
        publication_model = self.read("models/publication.py")
        self.assertIn('__tablename__ = "sites"', site_model)
        self.assertIn('UniqueConstraint("site_id", "slug"', category_model)
        self.assertIn('UniqueConstraint("site_id", "slug"', publication_model)
        self.assertIn("site_id", category_model)
        self.assertIn("site_id", publication_model)

    def test_migration_backfills_existing_content(self):
        migration = self.read("alembic/versions/4c91f7a2d8e3_multisite_content.py")
        self.assertIn('key": "jsinteractive"', migration)
        self.assertIn("UPDATE categories SET site_id", migration)
        self.assertIn("UPDATE publications SET site_id", migration)
        self.assertIn("uq_categories_site_slug", migration)
        self.assertIn("uq_publications_site_slug", migration)

    def test_admin_is_site_switchboard(self):
        sidebar = self.read("templates/dashboard/^shared/sidebar/index.html")
        routes = self.read("views/dashboard/sites/router.py")
        content = self.read("templates/dashboard/publication/index.html")
        self.assertIn("<span>Сайты</span>", sidebar)
        self.assertIn("admin.sites.index", routes)
        self.assertIn('name="site_id"', content)
        self.assertIn("Настройки сайта", content)

    def test_public_api_is_versioned_and_site_scoped(self):
        api = self.read("views/public/api.py")
        self.assertIn("/api/public/v1/sites/<string:site_key>", api)
        self.assertIn("/categories", api)
        self.assertIn("/publications", api)
        self.assertIn("Publication.site_id == site.id", api)
        self.assertIn("allowed_origins", api)

    def test_builtin_frontend_uses_site_settings(self):
        header = self.read("templates/public/^shared/header/index.html")
        hero = self.read("templates/public/home/section/hero.html")
        footer = self.read("templates/public/^shared/footer/index.html")
        self.assertIn("site.settings", header)
        self.assertIn("site.settings.hero", hero)
        self.assertIn("site.settings", footer)
        self.assertNotIn("cyrox007@gmail.com", header)
        self.assertNotIn("cyrox007@gmail.com", footer)
        self.assertNotIn("<style>", hero)

    def test_public_layout_has_no_large_inline_section_styles(self):
        for relative in [
            "templates/public/home/section/hero.html",
            "templates/public/home/section/philosophy.html",
            "templates/public/home/section/systems.html",
            "templates/public/home/section/about.html",
            "templates/public/articles/detail.html",
        ]:
            with self.subTest(relative=relative):
                self.assertNotIn("<style>", self.read(relative))
                self.assertNotIn('style="', self.read(relative))


if __name__ == "__main__":
    unittest.main()
