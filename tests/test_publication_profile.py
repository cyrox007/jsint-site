import unittest

from services.publication_profile import (
    build_profile,
    profile_for_editor,
    public_profile,
    schema_for,
    set_profile,
    schemas_for_site,
)


class PublicationProfileTests(unittest.TestCase):
    def test_logos_article_schema_is_versioned(self):
        schema = schema_for("logos", "article")
        self.assertIsNotNone(schema)
        self.assertEqual(schema.key, "logos.article")
        self.assertEqual(schema.version, 1)
        self.assertIn("article", schemas_for_site("logos"))

    def test_profile_data_is_normalized(self):
        profile = build_profile(
            "logos",
            "article",
            {
                "abstract": "  Аннотация  ",
                "keywords": "философия, онтология, философия",
                "bibliography": "Источник 1\n\nИсточник 2",
            },
        )
        self.assertEqual(profile["schema"], "logos.article")
        self.assertEqual(profile["version"], 1)
        self.assertEqual(profile["data"]["abstract"], "Аннотация")
        self.assertEqual(profile["data"]["keywords"], ["философия", "онтология"])
        self.assertEqual(profile["data"]["bibliography"], ["Источник 1", "Источник 2"])

    def test_profile_helpers_do_not_expose_invalid_payload(self):
        self.assertEqual(
            profile_for_editor(
                {"profiles": {"logos": {"data": {"abstract": "A"}}}},
                "logos",
            ),
            {"abstract": "A"},
        )
        self.assertIsNone(
            public_profile(
                {"profiles": {"logos": {"schema": "logos.article"}}},
                "logos",
            )
        )
        self.assertIsNone(build_profile("jsint", "article", {}))

    def test_profiles_are_isolated_by_site(self):
        logos = build_profile(
            "logos",
            "article",
            {"abstract": "Для Logos", "keywords": "", "bibliography": ""},
        )
        extra = set_profile({"seo_title": "JSInt title"}, "logos", logos)
        self.assertEqual(
            public_profile(extra, "logos")["data"]["abstract"],
            "Для Logos",
        )
        self.assertIsNone(public_profile(extra, "jsint"))
        self.assertEqual(extra["seo_title"], "JSInt title")


if __name__ == "__main__":
    unittest.main()
