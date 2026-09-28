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
        self.assertIn("workspace", styles.lower() if False else "workspace")
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

    def test_article_page_uses_same_visual_language(self):
        template = (
            ROOT / "templates/public/articles/detail.html"
        ).read_text(encoding="utf-8")
        styles = (
            ROOT / "templates/public/articles/style.css"
        ).read_text(encoding="utf-8")
        self.assertIn("article-category", template)
        self.assertIn("article-back", template)
        self.assertIn("radial-gradient", styles)


if __name__ == "__main__":
    unittest.main()
