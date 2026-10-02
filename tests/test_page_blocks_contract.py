import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class PageBlocksContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_page_models_and_migration_exist(self):
        model = self.read("models/page.py")
        migration = self.read(
            "alembic/versions/7e1d5b2c9f40_public_pages_blocks.py"
        )
        self.assertIn('__tablename__ = "pages"', model)
        self.assertIn('__tablename__ = "page_blocks"', model)
        self.assertIn('"block_type": "resume"', migration)

    def test_resume_template_contains_no_personal_resume_data(self):
        template = self.read("templates/public/home/section/resume.html")
        self.assertNotIn("Мебельный Рай", template)
        self.assertNotIn("Wondersoft", template)
        self.assertNotIn("BeBrainee", template)
        self.assertIn("resume_items", template)

    def test_home_uses_fixed_portfolio_composition_with_admin_visibility(self):
        template = self.read("templates/public/home/index.html")
        view = self.read("views/public/home/views.py")
        self.assertIn("home_blocks_by_type", view)
        self.assertIn('home_blocks_by_type.get("hero")', template)
        self.assertIn('home_blocks_by_type.get("systems")', template)
        self.assertIn('home_blocks_by_type.get("about")', template)
        self.assertIn('home_blocks_by_type.get("resume")', template)
        self.assertIn('home_blocks_by_type.get("philosophy")', template)
        self.assertIn("PageService.apply_public_navigation", view)
        self.assertIn("PageService.block_settings(page)", view)
        self.assertIn("public_blocks", self.read("services/page.py"))

    def test_portfolio_defaults_replace_old_studio_positioning(self):
        service = self.read("services/page.py")
        site_service = self.read("services/site.py")

        self.assertIn('"title": "Технологии для реальных задач"', service)
        self.assertIn('"title": "Избранные проекты"', service)
        self.assertIn('"title": "В чём я силён"', service)
        self.assertIn('"title": "Опыт и резюме"', service)
        self.assertIn('"name": "JSInteractive"', site_service)
        self.assertIn("личный технологический сайт", site_service)
        self.assertNotIn('"+УЛЬТРА"', site_service)

    def test_site_editor_still_controls_blocks_and_resume(self):
        controller = self.read("views/dashboard/sites/views.py")
        template = self.read("templates/dashboard/sites/edit.html")
        self.assertIn("PageService.update_home", controller)
        self.assertIn("block_{{ block.block_type }}_position", template)
        self.assertIn('name="resume_company"', template)
        self.assertIn('data-add-row="resume-editor-list"', template)
        self.assertIn('data-add-row="about-cards-list"', template)
        self.assertIn('data-add-row="navigation-list"', template)

    def test_home_portfolio_uses_real_publication_and_resume_data(self):
        systems = self.read("templates/public/home/section/systems.html")
        resume = self.read("templates/public/home/section/resume.html")
        view = self.read("views/public/home/views.py")

        self.assertIn("articles[:3]", systems)
        self.assertIn("article.title", systems)
        self.assertIn("article.content", systems)
        self.assertIn("resume_items", resume)
        self.assertIn("item.company", resume)
        self.assertIn("PublicationChannelService.list_public", view)

    def test_public_base_uses_project_favicon(self):
        base = self.read("templates/public/^core/base.html")
        self.assertIn("url_for('favicon_svg')", base)
        self.assertNotIn('rel="alternate icon"', base)
        self.assertNotIn("icons8-pastel-glyph", base)

    def test_public_seo_has_robots_opengraph_and_structured_data(self):
        base = self.read("templates/public/^core/base.html")
        robots = self.read("views/public/seo.py")
        self.assertIn('name="robots"', base)
        self.assertIn('property="og:locale"', base)
        self.assertIn('application/ld+json', base)
        self.assertIn('"Disallow: /api/"', robots)

    def test_resume_uses_dict_get_for_items_key(self):
        template = self.read("templates/public/home/section/resume.html")
        self.assertIn("resume.get('items', [])", template)


if __name__ == "__main__":
    unittest.main()
