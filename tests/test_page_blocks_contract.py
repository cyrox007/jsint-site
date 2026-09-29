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
        self.assertIn('name="resume_company"', template)
        self.assertIn('data-add-row="resume-editor-list"', template)
        self.assertIn('data-add-row="about-cards-list"', template)
        self.assertIn('data-add-row="hero-metrics-list"', template)
        self.assertIn('data-add-row="navigation-list"', template)
        self.assertIn('name="hero_console_title"', template)
        self.assertIn('name="systems_article_label"', template)
        self.assertIn('name="philosophy_kicker"', template)

    def test_home_visual_copy_is_configurable(self):
        service = self.read("services/page.py")
        controller = self.read("views/dashboard/sites/views.py")
        hero = self.read("templates/public/home/section/hero.html")
        systems = self.read("templates/public/home/section/systems.html")
        self.assertIn('"console_title": "Рабочий контур"', service)
        self.assertIn('"article_label": "Открыть материал"', service)
        self.assertIn('request.form.get("hero_console_title"', controller)
        self.assertIn("hero.console_title", hero)
        self.assertIn("systems.article_label", systems)

    def test_default_home_has_real_content_without_fake_telemetry(self):
        service = self.read("services/page.py")
        self.assertIn('"title": "+УЛЬТРА"', service)
        self.assertIn('"accent": "архитектура сложных web-систем"', service)
        self.assertIn("Независимая инженерная мини-студия", service)
        self.assertIn("Интерактивная инженерия", service)
        self.assertNotIn('"value": "21ms"', service)
        self.assertNotIn('"value": "12"', service)

    def test_home_repair_migration_only_fills_empty_default_site_blocks(self):
        migration = self.read("alembic/versions/e6a1c4d8f930_restore_home_content.py")
        self.assertIn('down_revision = "d4e9a61b7c20"', migration)
        self.assertIn("site.is_default IS TRUE", migration)
        self.assertIn("COALESCE(block.settings ->> 'title', '') = ''", migration)
        self.assertIn("jsonb_array_length(block.settings -> 'cards') > 0", migration)
        self.assertIn("Уже заполненные пользователем поля не перезаписываются", migration)

    def test_empty_home_sections_do_not_render_visual_shells(self):
        hero = self.read("templates/public/home/section/hero.html")
        philosophy = self.read("templates/public/home/section/philosophy.html")
        about = self.read("templates/public/home/section/about.html")
        styles = self.read("templates/public/home/style.css")

        self.assertIn("hero_title = hero.title or site.settings.brand.name or site.name", hero)
        self.assertIn("hero_description = hero.description or site.settings.seo.description", hero)
        self.assertIn("hero_has_console", hero)
        self.assertIn("{% if philosophy.text %}", philosophy)
        self.assertIn("{% if about_cards %}", about)
        self.assertIn("hero-grid--solo", styles)
        self.assertNotIn("min-height: 100svh", styles)
        self.assertIn("padding: clamp(58px, 6vw, 86px) 0", styles)

    def test_public_base_uses_project_favicon(self):
        base = self.read("templates/public/^core/base.html")
        self.assertIn("favicon/favicon.ico", base)
        self.assertNotIn("icons8-pastel-glyph", base)

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
