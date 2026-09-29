import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class YandexIndexingContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_webmaster_verification_has_system_fallback(self):
        settings = self.read("settings.py")
        template = self.read("templates/public/^core/base.html")

        self.assertIn("YANDEX_WEBMASTER_VERIFICATION", settings)
        self.assertIn("725d05a47d08b13d", settings)
        self.assertIn("seo_defaults.yandex_verification or config.YANDEX_WEBMASTER_VERIFICATION", template)
        self.assertIn('name="yandex-verification"', template)

    def test_robots_and_sitemap_follow_yandex_contract(self):
        seo = self.read("views/public/seo.py")

        self.assertIn('f"Sitemap: {base_url}/sitemap.xml"', seo)
        self.assertIn("Clean-param:", seo)
        self.assertNotIn('"Disallow: /contact"', seo)
        self.assertIn("_SITEMAP_MAX_URLS = 50_000", seo)
        self.assertIn("<lastmod>", seo)
        self.assertIn("PageService.get_page", seo)

    def test_non_public_routes_have_noindex_header(self):
        headers = self.read("components/security/headers.py")

        self.assertIn('"X-Robots-Tag"] = "noindex, nofollow"', headers)
        self.assertIn('"/healthz", "/contact"', headers)
        self.assertIn('request.path.startswith("/api/")', headers)

    def test_articles_expose_search_metadata(self):
        article = self.read("views/public/articles/views.py")
        base = self.read("templates/public/^core/base.html")

        self.assertIn('"@type": "Article"', article)
        self.assertIn('"@type": "BreadcrumbList"', article)
        self.assertIn("response.last_modified", article)
        self.assertIn("structured_data_items", base)

    def test_indexnow_key_task_and_update_hooks_exist(self):
        settings = self.read("settings.py")
        app = self.read("app.py")
        service = self.read("services/yandex_indexing.py")
        tasks = self.read("tasks/system.py")
        blog = self.read("views/dashboard/blog/views.py")
        sites = self.read("views/dashboard/sites/views.py")

        self.assertIn("YANDEX_INDEXNOW_ENABLED", settings)
        self.assertIn("YANDEX_INDEXNOW_KEY", settings)
        self.assertIn("yandex_indexnow_key", app)
        self.assertIn("https://yandex.com/indexnow", service)
        self.assertIn('"keyLocation"', service)
        self.assertIn('"urlList"', service)
        self.assertIn("tasks.system.notify_yandex_indexnow", tasks)
        self.assertIn("YandexIndexingService.enqueue", blog)
        self.assertIn("YandexIndexingService.enqueue", sites)

    def test_full_reindex_command_exists(self):
        command = self.read("tools/reindex_yandex.py")
        docs = self.read("docs/SEO_YANDEX.md")

        self.assertIn("YandexIndexingService.notify(urls)", command)
        self.assertIn("Передано URL в IndexNow", command)
        self.assertIn(".venv/bin/python tools/reindex_yandex.py", docs)


if __name__ == "__main__":
    unittest.main()
