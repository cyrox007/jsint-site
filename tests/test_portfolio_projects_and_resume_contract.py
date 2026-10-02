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

    def test_vanga_promo_targets_movie_audience_not_product_sales(self):
        view = self.read("views/public/projects/views.py")
        template = self.read("templates/public/projects/detail.html")
        demo = self.read("templates/public/vanga/index.html")
        home = self.read("templates/public/home/section/systems.html")
        styles = self.read("templates/public/projects/style.css")

        self.assertIn("VANGA_DETAIL", view)
        self.assertIn("Бесплатное публичное демо · ML-эксперимент", view)
        self.assertIn("Прогноз рейтинга фильма до выхода", view)
        self.assertIn("EntertainmentApplication", view)
        self.assertIn("Зрители и любители кино", view)

        self.assertIn("Фильм ещё не вышел?", template)
        self.assertIn("Не только разработчикам — прежде всего любителям кино", template)
        self.assertIn("От параметров фильма до прогноза рейтинга", template)
        self.assertIn("Практика машинного обучения", template)
        self.assertIn("Какой рейтинг будет у следующей премьеры?", template)
        self.assertIn("Это не сервис для продажи", template)

        self.assertIn("Какой рейтинг может получить фильм?", demo)
        self.assertIn("не коммерческий продукт", demo)
        self.assertIn("Фильм ещё не вышел?", home)
        self.assertIn(".vanga-project-preview", styles)
        self.assertIn(".vanga-how-grid", styles)

    def test_churchcms_promo_explains_platform_and_roadmap(self):
        view = self.read("views/public/projects/views.py")
        template = self.read("templates/public/projects/detail.html")
        styles = self.read("templates/public/projects/style.css")

        self.assertIn("CHURCHCMS_DETAIL", view)
        self.assertIn("Активная разработка · Parish MVP", view)
        self.assertIn("Федерация ChurchCMS-узлов", view)
        self.assertIn("Telegram, VK и MAX", view)
        self.assertIn("Legacy migration", view)
        self.assertIn("Pilot deployments", view)

        self.assertIn("Независимые сайты, единая структура", template)
        self.assertIn("Что уже реализовано", template)
        self.assertIn("От legacy-аудита к новой платформе", template)
        self.assertIn("Не один сайт, а сеть самостоятельных ChurchCMS", template)
        self.assertIn("Что ещё предстоит", template)

        self.assertIn(".church-network", styles)
        self.assertIn(".church-timeline", styles)
        self.assertIn(".church-roadmap-grid", styles)

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

    def test_hero_is_contained_and_proof_cards_are_separate(self):
        styles = self.read("templates/public/home/style.css")

        self.assertIn("min-height:clamp(720px,88vh,820px)", styles)
        self.assertIn("overflow:hidden", styles)
        self.assertIn("min-height:520px", styles)
        self.assertIn("grid-template-columns:repeat(4,minmax(0,1fr))", styles)
        self.assertIn("gap:10px", styles)
        self.assertIn("border-radius:12px", styles)
        self.assertIn("photo-1776251693908-b7eb878a5e6b", styles)
        self.assertNotIn("min-height:clamp(700px,86vh,860px)", styles)


if __name__ == "__main__":
    unittest.main()
