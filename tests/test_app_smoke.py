import unittest
from uuid import uuid4

from app import create_app
from settings import config


class ApplicationSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config.update(TESTING=True)
        cls.client = cls.app.test_client()
        host = config.ALLOWED_HOSTS[0] if config.ALLOWED_HOSTS else "localhost"
        cls.base = f"https://{host}"

    def test_home_page(self):
        response = self.client.get("/", base_url=self.base)
        self.assertEqual(response.status_code, 200)
        self.assertIn("+УЛЬТРА", response.get_data(as_text=True))

    def test_public_seo_headers_and_canonical(self):
        response = self.client.get("/", base_url=self.base)
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('<link rel="canonical" href=', html)
        self.assertIn('property="og:title"', html)
        self.assertIn('name="twitter:card"', html)

    def test_robots_txt(self):
        response = self.client.get("/robots.txt", base_url=self.base)
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("User-agent: *", body)
        self.assertIn(f"Disallow: {config.ADMIN_ROUTE_PREFIX}/", body)
        self.assertIn(f"Sitemap: {config.SITE_BASE_URL}/sitemap.xml", body)

    def test_sitemap_xml(self):
        response = self.client.get("/sitemap.xml", base_url=self.base)
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("<urlset", body)
        self.assertIn(f"<loc>{config.SITE_BASE_URL}/</loc>", body)
        self.assertNotIn(config.ADMIN_ROUTE_PREFIX, body)
        self.assertNotIn(config.NOTES_UPDATE_API_PREFIX, body)

    def test_health_endpoint(self):
        response = self.client.get("/healthz", base_url=self.base)
        self.assertEqual(response.status_code, 200)
        self.assertIn(response.get_json()["status"], {"ok", "degraded"})

    def test_loopback_signer_is_allowed_only_in_admin_csp(self):
        public_response = self.client.get("/", base_url=self.base)
        admin_response = self.client.get(
            f"{config.ADMIN_ROUTE_PREFIX}/login",
            base_url=self.base,
        )
        signer_origin = config.NOTES_OPERATOR_SIGNER_URL.rsplit("/v1", 1)[0]

        public_csp = public_response.headers.get("Content-Security-Policy", "")
        admin_csp = admin_response.headers.get("Content-Security-Policy", "")

        self.assertNotIn(signer_origin, public_csp)
        self.assertIn(signer_origin, admin_csp)

    def test_admin_login_page(self):
        response = self.client.get("/x321/dashboard/login", base_url=self.base)
        self.assertEqual(response.status_code, 200)
        self.assertIn("_csrf_token", response.get_data(as_text=True))

    def test_admin_login_rejects_missing_csrf(self):
        response = self.client.post(
            "/x321/dashboard/login",
            base_url=self.base,
            data={"email": "admin@example.com", "password": "not-a-password"},
        )
        self.assertEqual(response.status_code, 400)

    def test_dashboard_templates_compile(self):
        templates = [
            "dashboard/^core/base.html",
            "dashboard/^shared/header/index.html",
            "dashboard/^shared/sidebar/index.html",
            "dashboard/main/index.html",
            "dashboard/publication/index.html",
            "dashboard/publication/edit.html",
            "dashboard/catalog/index.html",
            "dashboard/catalog/edit.html",
            "dashboard/sites/index.html",
            "dashboard/sites/edit.html",
            "dashboard/control_plane/licenses.html",
            "dashboard/control_plane/releases.html",
            "dashboard/auth/index.html",
        ]
        for template_name in templates:
            with self.subTest(template=template_name):
                self.app.jinja_env.get_template(template_name)

    def test_public_registration_is_absent(self):
        response = self.client.get("/register", base_url=self.base)
        self.assertEqual(response.status_code, 404)

    def test_destructive_routes_are_not_get(self):
        uid = uuid4()
        publication = self.client.get(
            f"/x321/dashboard/publications/delete/{uid}",
            base_url=self.base,
        )
        category = self.client.get(
            f"/x321/dashboard/catalog/delete/{uid}",
            base_url=self.base,
        )
        self.assertEqual(publication.status_code, 405)
        self.assertEqual(category.status_code, 405)


if __name__ == "__main__":
    unittest.main()
