import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class PublicationChannelsContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_publication_site_model_and_migration_exist(self):
        model = self.read("models/publication.py")
        migration = self.read("alembic/versions/9a4f2d7c1b60_publication_sites.py")
        self.assertIn('class PublicationSite', model)
        self.assertIn('__tablename__ = "publication_sites"', model)
        self.assertIn('UniqueConstraint("site_id", "slug"', model)
        self.assertIn('down_revision = "7e1d5b2c9f40"', migration)
        self.assertIn("INSERT INTO publication_sites", migration)

    def test_owner_channel_is_synchronized_on_write(self):
        service = self.read("services/publication.py")
        self.assertGreaterEqual(
            service.count("PublicationChannelService.sync_owner"),
            2,
        )

    def test_public_delivery_uses_channels(self):
        home = self.read("views/public/home/views.py")
        article = self.read("views/public/articles/views.py")
        api = self.read("views/public/api.py")
        seo = self.read("views/public/seo.py")
        self.assertIn("PublicationChannelService.list_public", home)
        self.assertIn("PublicationChannelService.get_public_by_slug", article)
        self.assertIn("PublicationChannelService.list_public", api)
        self.assertIn("PublicationChannelService.list_public", seo)

    def test_category_delete_checks_publication_channels(self):
        catalog = self.read("services/catalog.py")
        self.assertIn("PublicationSite", catalog)
        self.assertIn("PublicationSite.category_id == cat_id", catalog)

    def test_admin_workspace_reads_and_edits_channels(self):
        views = self.read("views/dashboard/blog/views.py")
        template = self.read("templates/dashboard/publication/edit.html")
        self.assertIn("PublicationChannelService.list_for_admin", views)
        self.assertIn("_sync_additional_placements", views)
        self.assertIn("<strong>Размещение</strong>", template)
        self.assertIn("Публикация на других сайтах", template)
        self.assertIn("placement_{{ target_site.id }}_enabled", template)


if __name__ == "__main__":
    unittest.main()
