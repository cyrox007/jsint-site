import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class MediaLibraryContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_media_model_and_migration_exist(self):
        model = self.read("models/media.py")
        migration = self.read("alembic/versions/b3c8e12f4a71_media_library.py")
        self.assertIn('class MediaAsset', model)
        self.assertIn('"media_asset_sites"', model)
        self.assertIn('down_revision = "9a4f2d7c1b60"', migration)

    def test_upload_checks_real_image_signature(self):
        service = self.read("services/media.py")
        self.assertIn("_detect_image_type", service)
        self.assertIn("data.startswith", service)
        self.assertIn("MEDIA_UPLOAD_MAX_BYTES", service)
        self.assertNotIn("save(upload.filename", service)

    def test_media_is_available_in_admin_and_public_api(self):
        app = self.read("app.py")
        sidebar = self.read("templates/dashboard/^shared/sidebar/index.html")
        api = self.read("views/public/api.py")
        self.assertIn("d_media_router.install(app)", app)
        self.assertIn("public_media.install(app)", app)
        self.assertIn("Медиатека", sidebar)
        self.assertIn("/media", api)
        self.assertIn("MediaService.list_for_site", api)

    def test_public_media_has_immutable_cache_and_nosniff(self):
        view = self.read("views/public/media.py")
        self.assertIn("immutable", view)
        self.assertIn("X-Content-Type-Options", view)


if __name__ == "__main__":
    unittest.main()
