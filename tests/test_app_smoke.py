import unittest
from uuid import uuid4

from app import create_app


class ApplicationSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config.update(TESTING=True)
        cls.client = cls.app.test_client()
        cls.base = "https://localhost"

    def test_home_page(self):
        response = self.client.get("/", base_url=self.base)
        self.assertEqual(response.status_code, 200)
        self.assertIn("+УЛЬТРА", response.get_data(as_text=True))

    def test_health_endpoint(self):
        response = self.client.get("/healthz", base_url=self.base)
        self.assertEqual(response.status_code, 200)
        self.assertIn(response.get_json()["status"], {"ok", "degraded"})

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
