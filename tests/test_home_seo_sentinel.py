import unittest

from views.public.home.views import _clean_seo_value


class HomeSeoSentinelTests(unittest.TestCase):
    def test_null_like_values_are_empty(self):
        for value in (None, "", "   ", "None", " none ", "NULL", "undefined"):
            with self.subTest(value=value):
                self.assertEqual(_clean_seo_value(value), "")

    def test_real_seo_value_is_preserved(self):
        self.assertEqual(
            _clean_seo_value("  JSInteractive — тестовый title  "),
            "JSInteractive — тестовый title",
        )


if __name__ == "__main__":
    unittest.main()
