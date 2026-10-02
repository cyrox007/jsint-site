from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PublicSeoContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_base_has_complete_social_metadata(self):
        base = self.read("templates/public/^core/base.html")

        self.assertIn('name="description"', base)
        self.assertIn('name="author" content="JSInteractive"', base)
        self.assertIn('rel="canonical"', base)
        self.assertIn('property="og:image"', base)
        self.assertIn('property="og:image:width" content="1600"', base)
        self.assertIn('property="og:image:height" content="900"', base)
        self.assertIn('property="og:image:alt"', base)
        self.assertIn('name="twitter:card" content="summary_large_image"', base)
        self.assertIn('article:published_time', base)
        self.assertIn('application/ld+json', base)
        self.assertIn('"inLanguage": "ru-RU"', base)

    def test_home_has_profile_and_project_list_schema(self):
        view = self.read("views/public/home/views.py")
        site = self.read("services/site.py")

        self.assertIn('"@type": "ProfilePage"', view)
        self.assertIn('"@type": "ItemList"', view)
        self.assertIn("author_entity(site)", view)
        self.assertIn("HERO_IMAGE_URL", view)
        self.assertIn("seo_preload_image_url=HERO_IMAGE_URL", view)
        self.assertIn(
            "JSInteractive — full-stack разработка и self-hosted проекты",
            view,
        )
        self.assertIn("backend, API, админ-панели", view)
        self.assertIn("full-stack разработчика", site)

    def test_articles_use_blogposting_and_rich_metadata(self):
        view = self.read("views/public/articles/views.py")

        self.assertIn('"@type": "BlogPosting"', view)
        self.assertIn('"wordCount": word_count', view)
        self.assertIn('"keywords": keywords', view)
        self.assertIn('"author": author_entity(site)', view)
        self.assertIn('"image": [article_image_url]', view)
        self.assertIn("first_content_image", view)
        self.assertIn("seo_published_at", view)
        self.assertIn("seo_modified_at", view)
        self.assertIn("breadcrumb_schema", view)

    def test_projects_and_workspace_have_software_schema(self):
        projects = self.read("views/public/projects/views.py")
        workspace = self.read("views/public/workspace_organizer/views.py")

        self.assertIn('"@type": "SoftwareApplication"', projects)
        self.assertIn('"featureList"', projects)
        self.assertIn("breadcrumb_schema", projects)
        self.assertIn("seo_title=project.seo_title", projects)

        self.assertIn('"@type": "SoftwareApplication"', workspace)
        self.assertIn('"featureList"', workspace)
        self.assertIn("breadcrumb_schema", workspace)
        self.assertIn("self-hosted заметки, задачи и файлы", workspace)

    def test_vanga_demo_does_not_compete_with_project_page(self):
        vanga = self.read("views/public/vanga/views.py")
        sitemap = self.read("views/public/seo.py")

        self.assertIn('"seo_noindex": True', vanga)
        self.assertIn('/projects/vanga', vanga)
        self.assertNotIn(
            '(urljoin(f"{base_url}/", "demo/vanga"),',
            sitemap,
        )
        self.assertIn('"projects/vanga"', sitemap)

    def test_robots_and_sitemap_keep_indexing_hygiene(self):
        seo = self.read("views/public/seo.py")

        self.assertIn('"Disallow: /api/"', seo)
        self.assertIn('"Disallow: /healthz"', seo)
        self.assertIn("Clean-param:", seo)
        self.assertIn("Sitemap:", seo)
        self.assertIn("static_modified", seo)
        self.assertIn("<lastmod>", seo)


if __name__ == "__main__":
    unittest.main()
