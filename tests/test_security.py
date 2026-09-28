import unittest

from flask import Flask

from components.security.csrf import csrf_exempt, csrf_token, init_app
from components.security.html import sanitize_rich_text
from utils.validation import validate_slug


class RichTextSecurityTests(unittest.TestCase):
    def test_blocks_script_and_javascript_url(self):
        value = '<p>Hello</p><script>alert(1)</script><a href="javascript:alert(1)">bad</a>'
        clean = sanitize_rich_text(value)
        self.assertIn("<p>Hello</p>", clean)
        self.assertNotIn("script", clean.lower())
        self.assertNotIn("javascript:", clean.lower())

    def test_allows_safe_link(self):
        clean = sanitize_rich_text('<a href="https://example.com/path">Example</a>')
        self.assertIn('href="https://example.com/path"', clean)
        self.assertIn("noopener noreferrer nofollow", clean)

    def test_allows_safe_image_and_blocks_data_url(self):
        clean = sanitize_rich_text(
            '<img src="/media/123/image.png" alt="Схема">'
            '<img src="data:image/png;base64,AAAA" alt="bad">'
        )
        self.assertIn('src="/media/123/image.png"', clean)
        self.assertIn('alt="Схема"', clean)
        self.assertIn('loading="lazy"', clean)
        self.assertNotIn("data:image", clean)


class SlugValidationTests(unittest.TestCase):
    def test_accepts_normal_slug(self):
        self.assertEqual(validate_slug("hello-world-2"), "hello-world-2")

    def test_rejects_unsafe_slug(self):
        for value in ["../admin", "Hello World", "hello--world", "hello/world", ""]:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_slug(value)


class CsrfTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config.update(SECRET_KEY="test-secret-that-is-long-enough-for-unit-tests")
        init_app(app)

        @app.get("/token")
        def token():
            return csrf_token()

        @app.post("/write")
        def write():
            return "ok"

        @app.post("/machine")
        @csrf_exempt
        def machine():
            return "ok"

        self.client = app.test_client()

    def test_missing_token_is_rejected(self):
        response = self.client.post("/write")
        self.assertEqual(response.status_code, 400)

    def test_session_token_is_accepted(self):
        token = self.client.get("/token").get_data(as_text=True)
        response = self.client.post("/write", data={"_csrf_token": token})
        self.assertEqual(response.status_code, 200)

    def test_explicit_machine_endpoint_is_csrf_exempt(self):
        response = self.client.post("/machine")
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
