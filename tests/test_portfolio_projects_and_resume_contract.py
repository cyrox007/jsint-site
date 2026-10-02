from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PortfolioProjectsAndResumeContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_project_cards_use_internal_promos_and_market_is_gone(self):
        template = self.read("templates/public/home/section/systems.html")

        self.assertIn("project_promo", template)
        self.assertIn("project_slug='vanga'", template)
        self.assertIn("project_slug='the-game'", template)
        self.assertIn("project_slug='churchcms'", template)
        self.assertNotIn("github.com", template.lower())
        self.assertNotIn("<h3>Market</h3>", template)
        self.assertIn("<h3>The-Game</h3>", template)

    def test_project_promo_registry_and_routes_exist(self):
        app = self.read("app.py")
        router = self.read("views/public/projects/routers.py")
        view = self.read("views/public/projects/views.py")
        template = self.read("templates/public/projects/detail.html")
        sitemap = self.read("views/public/seo.py")

        self.assertIn("projects_router.install(app)", app)
        self.assertIn('"/projects/<project_slug>"', router)
        self.assertIn('"vanga": ProjectPromo(', view)
        self.assertIn('"the-game": ProjectPromo(', view)
        self.assertIn('"churchcms": ProjectPromo(', view)
        self.assertIn("project.capabilities", template)
        self.assertIn('"projects/vanga"', sitemap)
        self.assertIn('"projects/the-game"', sitemap)
        self.assertIn('"projects/churchcms"', sitemap)

    def test_about_uses_profile_supported_fullstack_context(self):
        template = self.read("templates/public/home/section/about.html")

        self.assertIn("Full-stack", template)
        self.assertIn("HTML5", template)
        self.assertIn("Vue.js", template)
        self.assertIn("Laravel", template)
        self.assertIn("FastAPI", template)
        self.assertIn("Go", template)
        self.assertIn("PostgreSQL", template)
        self.assertIn("Redis", template)
        self.assertIn("JavaScript и Canvas", template)

    def test_resume_modal_is_full_and_animated(self):
        template = self.read("templates/public/home/section/resume.html")
        styles = self.read("templates/public/home/style.css")
        script = self.read("static/public/home-portfolio.js")
        home = self.read("templates/public/home/index.html")

        self.assertIn("data-resume-open", template)
        self.assertIn("data-resume-modal", template)
        self.assertIn("for item in resume_items", template)
        self.assertNotIn("for item in resume_items[:3]", template.split("resume-modal", 1)[1])
        self.assertIn(".resume-modal.is-open", styles)
        self.assertIn("transition:transform .24s ease", styles)
        self.assertIn('event.key === "Escape"', script)
        self.assertIn("home-portfolio.js", home)

    def test_hero_allows_content_to_extend_without_clipping(self):
        styles = self.read("templates/public/home/style.css")

        self.assertIn("min-height:clamp(700px,86vh,860px)", styles)
        self.assertIn("overflow:visible", styles)
        self.assertIn("min-height:500px", styles)


if __name__ == "__main__":
    unittest.main()
