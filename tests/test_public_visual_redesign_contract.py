from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PublicVisualRedesignContractTests(unittest.TestCase):
    def test_public_header_uses_floating_navigation(self):
        template = (
            ROOT / "templates/public/^shared/header/index.html"
        ).read_text(encoding="utf-8")
        styles = (
            ROOT / "templates/public/^shared/header/style.css"
        ).read_text(encoding="utf-8")
        self.assertIn("logo-mark", template)
        self.assertIn("border-radius: 22px", styles)
        self.assertIn("backdrop-filter", styles)

    def test_home_has_new_visual_sections(self):
        hero = (
            ROOT / "templates/public/home/section/hero.html"
        ).read_text(encoding="utf-8")
        systems = (
            ROOT / "templates/public/home/section/systems.html"
        ).read_text(encoding="utf-8")
        resume = (
            ROOT / "templates/public/home/section/resume.html"
        ).read_text(encoding="utf-8")
        self.assertIn("hero-console", hero)
        self.assertIn("project-index", systems)
        self.assertIn("resume-marker", resume)

    def test_dynamic_content_is_not_replaced_by_hardcoded_brand_copy(self):
        about = (
            ROOT / "templates/public/home/section/about.html"
        ).read_text(encoding="utf-8")
        footer = (
            ROOT / "templates/public/^shared/footer/index.html"
        ).read_text(encoding="utf-8")
        self.assertNotIn("Независимая работа с продуктами", about)
        self.assertIn("settings.brand.subtitle", footer)

    def test_article_page_uses_editorial_visual_language(self):
        template = (
            ROOT / "templates/public/articles/detail.html"
        ).read_text(encoding="utf-8")
        styles = (
            ROOT / "templates/public/articles/style.css"
        ).read_text(encoding="utf-8")
        controller = (
            ROOT / "views/public/articles/views.py"
        ).read_text(encoding="utf-8")

        self.assertIn("article-hero", template)
        self.assertIn("article-facts", template)
        self.assertIn("article-layout", template)
        self.assertIn("article-rail", template)
        self.assertIn("reading_minutes", template)
        self.assertIn("math.ceil", controller)
        self.assertIn("grid-template-columns: minmax(0, 1fr) 260px", styles)
        self.assertIn("grid-template-columns: 210px minmax(0, 760px)", styles)

    def test_public_navigation_has_smooth_scroll_and_no_dead_hashes(self):
        page_service = (ROOT / "services/page.py").read_text(encoding="utf-8")
        script = (ROOT / "static/public/navigation.js").read_text(encoding="utf-8")
        base = (ROOT / "templates/public/^core/base.html").read_text(encoding="utf-8")
        hero = (ROOT / "templates/public/home/section/hero.html").read_text(encoding="utf-8")
        common = (ROOT / "templates/public/^core/common.css").read_text(encoding="utf-8")

        self.assertIn("filter_navigation", page_service)
        self.assertIn('href == "#"', page_service)
        self.assertIn("href[1:] not in anchors", page_service)
        self.assertIn("scrollIntoView", script)
        self.assertIn("prefers-reduced-motion", script)
        self.assertIn("public/navigation.js", base)
        self.assertIn("'systems' in home_anchor_ids", hero)
        self.assertIn("scroll-behavior: smooth", common)


if __name__ == "__main__":
    unittest.main()
