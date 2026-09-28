from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PublicFrontendApiContractTests(unittest.TestCase):
    def test_bootstrap_route_is_versioned_and_site_scoped(self):
        source = (ROOT / "views/public/api.py").read_text(encoding="utf-8")
        self.assertIn('PUBLIC_API_CONTRACT = "jsint-public-v1"', source)
        self.assertIn(
            '"/api/public/v1/sites/<string:site_key>/bootstrap"',
            source,
        )
        self.assertIn('"categories": [_category_payload(item) for item in categories]', source)
        self.assertIn('"latest_publications": [', source)
        self.assertIn("def _site_payload(site)", source)
        self.assertNotIn("SiteService.public_config(site)", source)
        self.assertIn('"data": public_profile(extra)', source)
        self.assertNotIn('"extra_data": extra', source)

    def test_external_frontend_contract_has_explicit_cors(self):
        source = (ROOT / "views/public/api.py").read_text(encoding="utf-8")
        self.assertIn('allowed_origins', source)
        self.assertIn('Access-Control-Allow-Origin', source)
        self.assertIn('Access-Control-Expose-Headers', source)
        self.assertIn('X-JSInt-Public-API', source)

    def test_documentation_for_external_frontends_exists(self):
        doc = (ROOT / "docs/PUBLIC_FRONTEND_API.md").read_text(encoding="utf-8")
        self.assertIn("единым backend", doc)
        self.assertIn("VUE_APP_SITE_KEY=logos", doc)
        self.assertIn("не должен хранить API-ключи", doc)
        self.assertIn("SEO конкретного внешнего frontend принадлежат самому frontend", doc)


if __name__ == "__main__":
    unittest.main()
