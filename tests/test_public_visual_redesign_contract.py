from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PublicVisualRedesignContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_public_header_uses_portfolio_brand(self):
        template = self.read("templates/public/^shared/header/index.html")
        styles = self.read("templates/public/^shared/header/style.css")
        base = self.read("templates/public/^core/base.html")

        self.assertIn("public/jsinteractive-mark.svg", template)
        self.assertIn("#systems", template)
        self.assertIn("#publications", template)
        self.assertIn("#resume", template)
        self.assertIn("position:fixed", styles)
        self.assertIn("border-radius:0", styles)
        self.assertIn("backdrop-filter", styles)
        self.assertIn("public/jsinteractive-mark.svg", base)

    def test_home_matches_portfolio_information_architecture(self):
        page = self.read("templates/public/home/index.html")
        hero = self.read("templates/public/home/section/hero.html")
        systems = self.read("templates/public/home/section/systems.html")
        about = self.read("templates/public/home/section/about.html")
        resume = self.read("templates/public/home/section/resume.html")
        approach = self.read("templates/public/home/section/philosophy.html")
        styles = self.read("templates/public/home/style.css")

        self.assertIn('home_blocks_by_type.get("hero")', page)
        self.assertIn('home_blocks_by_type.get("systems")', page)
        self.assertIn('home_blocks_by_type.get("about")', page)
        self.assertIn('home_blocks_by_type.get("resume")', page)
        self.assertIn('home_blocks_by_type.get("philosophy")', page)
        self.assertIn("Технологии", hero)
        self.assertIn("portfolio-hero__backdrop", hero)
        self.assertIn("Наши проекты", systems)
        self.assertIn('id="publications"', systems)
        self.assertIn("Workspace Organizer", systems)
        self.assertIn("В чём я силён", about)
        self.assertIn("Опыт и резюме", resume)
        self.assertIn("resume_items", resume)
        self.assertIn("Мой подход", approach)
        self.assertIn("images.unsplash.com", styles)
        self.assertIn(".portfolio-feature-panel", styles)
        self.assertIn(".portfolio-proof", styles)

    def test_article_page_has_editorial_sidebar_and_generated_toc(self):
        template = self.read("templates/public/articles/detail.html")
        styles = self.read("templates/public/articles/style.css")
        controller = self.read("views/public/articles/views.py")
        script = self.read("static/public/article-toc.js")

        self.assertIn("portfolio-article-hero", template)
        self.assertIn("portfolio-article-layout", template)
        self.assertIn("portfolio-article-sidebar", template)
        self.assertIn('id="article-toc"', template)
        self.assertIn("related_articles", template)
        self.assertIn("reading_minutes", template)
        self.assertIn("math.ceil", controller)
        self.assertIn("PublicationChannelService.list_public", controller)
        self.assertIn('querySelectorAll("h2, h3")', script)
        self.assertIn(
            "grid-template-columns:minmax(0,1fr) 300px",
            styles,
        )

    def test_workspace_organizer_uses_same_visual_family(self):
        template = self.read("templates/public/workspace_organizer/index.html")
        styles = self.read("templates/public/workspace_organizer/style.css")

        self.assertIn("wo-portfolio-hero", template)
        self.assertIn("wo-app-window", template)
        self.assertIn("Что умеет Workspace Organizer", template)
        self.assertIn("Кому подойдёт", template)
        self.assertIn("Техническая база", template)
        self.assertIn("jsinteractive-mountain.svg", styles)
        self.assertIn("var(--border)", styles)

    def test_public_navigation_keeps_smooth_scroll(self):
        script = self.read("static/public/navigation.js")
        common = self.read("templates/public/^core/common.css")

        self.assertIn("scrollIntoView", script)
        self.assertIn("prefers-reduced-motion", script)
        self.assertIn("scroll-behavior: smooth", common)


if __name__ == "__main__":
    unittest.main()
