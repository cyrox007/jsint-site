import unittest
from types import SimpleNamespace

from services.site import DEFAULT_SETTINGS, SiteService


class SiteSeoNormalizationTests(unittest.TestCase):
    def test_string_null_values_restore_required_seo_defaults(self):
        site = SimpleNamespace(
            settings={
                "seo": {
                    "site_name": " null ",
                    "title": "None",
                    "description": "UNDEFINED",
                    "locale": "   ",
                }
            }
        )

        seo = SiteService.settings(site)["seo"]

        self.assertEqual(seo["site_name"], DEFAULT_SETTINGS["seo"]["site_name"])
        self.assertEqual(seo["title"], DEFAULT_SETTINGS["seo"]["title"])
        self.assertEqual(seo["description"], DEFAULT_SETTINGS["seo"]["description"])
        self.assertEqual(seo["locale"], DEFAULT_SETTINGS["seo"]["locale"])

    def test_real_custom_seo_values_are_preserved(self):
        site = SimpleNamespace(
            settings={
                "seo": {
                    "title": "Мой SEO title",
                    "description": "Осмысленное описание публичной страницы длиной больше сорока символов.",
                }
            }
        )

        seo = SiteService.settings(site)["seo"]

        self.assertEqual(seo["title"], "Мой SEO title")
        self.assertEqual(
            seo["description"],
            "Осмысленное описание публичной страницы длиной больше сорока символов.",
        )


if __name__ == "__main__":
    unittest.main()
