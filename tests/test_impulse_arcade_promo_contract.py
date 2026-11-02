from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ImpulseArcadePromoContractTests(unittest.TestCase):
    """Регрессии основной игровой карточки и отдельной страницы «Импульса»."""

    def read(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8")

    def test_home_features_impulse_and_preserves_archived_project(self):
        home = self.read("templates/public/home/section/systems.html")
        archive = self.read("templates/public/projects/the_game.html")
        router = self.read("views/public/projects/routers.py")

        self.assertIn("url_for('impulse_arcade_project')", home)
        self.assertIn("<h3>Импульс</h3>", home)
        self.assertNotIn("<h3>The-Game</h3>", home)
        self.assertIn('"/projects/impulse-arcade"', router)
        self.assertIn('"/projects/the-game"', router)
        self.assertIn("Учебный архив", archive)

    def test_promo_links_to_the_actual_game_and_sources(self):
        view = self.read("views/public/projects/impulse_arcade.py")
        template = self.read("templates/public/projects/impulse_arcade.html")

        self.assertIn("https://cyrox007.github.io/impulse-arcade/", view)
        self.assertIn("https://github.com/cyrox007/impulse-arcade", view)
        self.assertIn('IMPULSE_VERSION = "1.0.0-rc.1"', view)
        self.assertIn('href="{{ demo_url }}"', template)
        self.assertIn('href="{{ repository_url }}"', template)
        self.assertIn('rel="noopener noreferrer"', template)
        self.assertIn("Играть в «Импульс»", template)
        self.assertIn("url_for('the_game_project')", template)

    def test_promo_does_not_claim_unverified_stable_release_or_fps(self):
        template = self.read("templates/public/projects/impulse_arcade.html")
        view = self.read("views/public/projects/impulse_arcade.py")

        self.assertIn("релиз-кандидат", template)
        self.assertIn("ручная приёмка", template)
        self.assertIn("пяти секторов", template)
        self.assertIn("Два босса", template)
        self.assertNotIn("стабильные 60 FPS", template)
        self.assertIn('"@type": "VideoGame"', view)
        self.assertIn('"applicationCategory": "GameApplication"', view)
        self.assertIn('"softwareVersion": IMPULSE_VERSION', view)
        self.assertIn('"featureList": list(IMPULSE_FEATURES)', view)
        self.assertIn("breadcrumb_schema", view)

    def test_new_page_has_accessible_static_preview_and_responsive_styles(self):
        template = self.read("templates/public/projects/impulse_arcade.html")
        styles = self.read("templates/public/projects/impulse_arcade.css")
        seo = self.read("views/public/seo.py")

        self.assertIn("Схематическое превью", template)
        self.assertIn('aria-hidden="true"', template)
        self.assertIn("impulse-preview__arena", template)
        self.assertIn("impulse-preview__bricks", template)
        self.assertIn("impulse-technology__grid", styles)
        self.assertIn("@media (max-width: 760px)", styles)
        self.assertIn("@media (max-width: 520px)", styles)
        self.assertIn("projects/impulse-arcade", seo)
        self.assertIn("_SITEMAP_STATIC_URLS = 7", seo)


if __name__ == "__main__":
    unittest.main()
