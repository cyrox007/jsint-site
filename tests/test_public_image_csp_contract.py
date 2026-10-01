from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PublicImageCspContractTests(unittest.TestCase):
    def test_external_hero_image_host_is_narrowly_allowlisted(self):
        headers = (ROOT / "components/security/headers.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("https://images.unsplash.com", headers)
        self.assertIn("img-src 'self' data:", headers)
        self.assertNotIn("img-src *", headers)


if __name__ == "__main__":
    unittest.main()
