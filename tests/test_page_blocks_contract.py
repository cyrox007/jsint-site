import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class PageBlocksContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_page_models_and_migration_exist(self):
        model = self.read("models/page.py")
        migration = self.read("alembic/versions/7e1d5b2c9f40_public_pages_blocks.py")
        self.assertIn('__tablename__ = "pages"', model)
        self.assertIn('__tablename__ = "page_blocks"', model)
        self.assertIn('down_revision = "4c91f7a2d8e3"', migration)
        self.assertIn('"block_type": "resume"', migration)

    def test_resume_template_contains_no_personal_resume_data(self):
        template = self.read("templates/public/home/section/resume.html")
        self.assertNotIn("Мебельный Рай", template)
        self.assertNotIn("Wondersoft", template)
        self.assertNotIn("BeBrainee", template)
        self.assertIn("resume_items", template)

    def test_home_is_rendered_from_ordered_blocks(self):
        template = self.read("templates/public/home/index.html")
        view = self.read("views/public/home/views.py")
        self.assertIn("for block in home_blocks", template)
        self.assertIn("PageService.public_blocks", view)

    def test_page_content_lives_in_block_settings(self):
        service = self.read("services/page.py")
        site_service = self.read("services/site.py")
        migration = self.read("alembic/versions/c8d2f51a6e90_page_block_content.py")
        sections = [
            self.read("templates/public/home/section/hero.html"),
            self.read("templates/public/home/section/philosophy.html"),
            self.read("templates/public/home/section/systems.html"),
            self.read("templates/public/home/section/about.html"),
        ]
        self.assertIn("HOME_BLOCK_DEFAULTS", service)
        self.assertNotIn('"hero": {', site_service)
        self.assertIn("settings - 'hero' - 'home'", migration)
        for section in sections:
            self.assertIn("block.settings", section)
            self.assertNotIn("site.settings.home", section)
            self.assertNotIn("site.settings.hero", section)

    def test_site_editor_controls_blocks_and_resume(self):
        controller = self.read("views/dashboard/sites/views.py")
        template = self.read("templates/dashboard/sites/edit.html")
        self.assertIn("PageService.update_home", controller)
        self.assertIn("block_{{ block.block_type }}_position", template)
        self.assertIn("resume_{{ index }}_company", template)

    def test_public_seo_has_robots_opengraph_and_structured_data(self):
        base = self.read("templates/public/^core/base.html")
        robots = self.read("views/public/seo.py")
        self.assertIn('name="robots"', base)
        self.assertIn('property="og:locale"', base)
        self.assertIn('application/ld+json', base)
        self.assertIn('"Disallow: /api/"', robots)

    def test_public_api_has_cache_validator_and_noindex(self):
        api = self.read("views/public/api.py")
        self.assertIn("response.add_etag()", api)
        self.assertIn('"X-Robots-Tag"', api)
        self.assertIn('"total": total', api)

    def test_public_api_exposes_published_pages(self):
        api = self.read("views/public/api.py")
        self.assertIn("/pages/<string:page_slug>", api)
        self.assertIn("PageService.public_blocks(page)", api)

    def test_resume_uses_dict_get_for_items_key(self):
        template = self.read("templates/public/home/section/resume.html")
        self.assertIn("resume.get('items', [])", template)


if __name__ == "__main__":
    unittest.main()
