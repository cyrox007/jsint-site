from __future__ import annotations

import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class GlobalFaviconContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_public_and_admin_use_current_brand_favicon(self):
        public_base = self.read("templates/public/^core/base.html")
        admin_base = self.read("templates/dashboard/^core/base.html")

        for template in (public_base, admin_base):
            self.assertIn("url_for('favicon_svg')", template)
            self.assertIn("url_for('favicon_ico')", template)
            self.assertIn("url_for('apple_touch_icon')", template)
            self.assertNotIn("icons8-pastel-glyph", template)

    def test_legacy_favicon_urls_serve_current_brand_assets(self):
        app = self.read("app.py")

        self.assertIn('"/favicon.ico"', app)
        self.assertIn('"/apple-touch-icon.png"', app)
        self.assertIn('"/apple-touch-icon-precomposed.png"', app)
        self.assertIn('favicon/jsinteractive.ico', app)
        self.assertIn('favicon/jsinteractive-180.png', app)

    def test_admin_manifest_does_not_reference_old_icon_pack(self):
        manifest = self.read("static/admin-pwa/manifest.webmanifest")

        self.assertIn("jsinteractive-192.png", manifest)
        self.assertIn("jsinteractive-mark.svg", manifest)
        self.assertNotIn("icons8-pastel-glyph", manifest)


if __name__ == "__main__":
    unittest.main()
