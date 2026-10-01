from __future__ import annotations

import io
import pathlib
import tempfile
import unittest
import zipfile
from uuid import uuid4

from werkzeug.datastructures import FileStorage

from settings import config
from services.admin_notifications import DiagnosticService


ROOT = pathlib.Path(__file__).resolve().parents[1]


def zip_bytes(entries: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return output.getvalue()


class AdminInboxDiagnosticsContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_inbox_and_diagnostics_routes_are_wired(self):
        app = self.read("app.py")
        notes_api = self.read("views/notes_api.py")
        sidebar = self.read("templates/dashboard/^shared/sidebar/index.html")

        self.assertIn("d_inbox_router.install(app)", app)
        self.assertIn('f"{prefix}/diagnostics"', notes_api)
        self.assertIn("NotesControlPlane.authorize", notes_api)
        self.assertIn("DiagnosticService.create_report", notes_api)
        self.assertIn("request.max_content_length = max_bytes", notes_api)
        self.assertIn("request.max_form_parts = 8", notes_api)
        self.assertIn("admin.inbox.index", sidebar)
        self.assertIn("admin_unread_count", sidebar)

    def test_contact_creates_notification_after_message_is_flushed(self):
        contact = self.read("views/public/contact/views.py")
        self.assertIn("db_session.flush()", contact)
        self.assertIn("AdminNotificationService.for_contact", contact)
        self.assertIn("AdminNotificationService.enqueue_push", contact)

    def test_push_does_not_include_diagnostic_archive(self):
        service = self.read("services/admin_notifications.py")
        self.assertIn('"X-Click"', service)
        self.assertIn("push_text.encode", service)
        self.assertNotIn("package_path.encode", service)

    def test_safe_zip_is_stored_and_traversal_is_rejected(self):
        original_root = config.NOTES_DIAGNOSTIC_STORAGE_PATH
        original_limit = config.NOTES_DIAGNOSTIC_UPLOAD_MAX_BYTES
        with tempfile.TemporaryDirectory() as tmp:
            config.NOTES_DIAGNOSTIC_STORAGE_PATH = tmp
            config.NOTES_DIAGNOSTIC_UPLOAD_MAX_BYTES = 1024 * 1024
            try:
                safe = FileStorage(
                    stream=io.BytesIO(
                        zip_bytes(
                            {
                                "logs/app.log": b"ok",
                                "health.json": b'{"status":"degraded","database":true}',
                                "privacy.json": b'{"user_content_included":false}',
                            }
                        )
                    ),
                    filename="diagnostic.zip",
                )
                name, path, size, sha256 = DiagnosticService._store_package(
                    uuid4(),
                    safe,
                )
                self.assertEqual(name, "diagnostic.zip")
                self.assertTrue(pathlib.Path(path).is_file())
                self.assertGreater(size, 0)
                self.assertEqual(len(sha256), 64)
                preview = DiagnosticService._read_diagnostic_preview(pathlib.Path(path))
                self.assertEqual(preview["health"]["status"], "degraded")
                self.assertFalse(preview["privacy"]["user_content_included"])

                unsafe = FileStorage(
                    stream=io.BytesIO(zip_bytes({"../secret.txt": b"no"})),
                    filename="bad.zip",
                )
                with self.assertRaisesRegex(ValueError, "небезопасный путь"):
                    DiagnosticService._store_package(uuid4(), unsafe)
            finally:
                config.NOTES_DIAGNOSTIC_STORAGE_PATH = original_root
                config.NOTES_DIAGNOSTIC_UPLOAD_MAX_BYTES = original_limit

    def test_deployment_allows_diagnostic_uploads(self):
        update_script = self.read("update.sh")
        checkout_setup = self.read("deploy/checkout/setup.sh")
        checkout_unit = self.read("deploy/checkout/jsint-site.service")
        release_unit = self.read("deploy/jsint-site.service")
        checkout_nginx = self.read("deploy/checkout/nginx.conf.example")
        installer = self.read("deploy/install.sh")
        release_lib = self.read("deploy/release-lib.sh")

        self.assertIn("NOTES_DIAGNOSTIC_STORAGE_PATH", update_script)
        self.assertIn("/var/lib/jsint-site/diagnostics", checkout_setup)
        self.assertIn("/var/lib/jsint-site/diagnostics", checkout_unit)
        self.assertIn("/var/lib/jsint-site/diagnostics", release_unit)
        self.assertIn("client_max_body_size 12m", checkout_nginx)
        self.assertIn("NOTES_DIAGNOSTIC_STORAGE_PATH", installer)
        self.assertIn("location = /api/notes/v1/diagnostics", installer)
        self.assertIn("/var/lib/jsint-site/diagnostics", release_lib)


if __name__ == "__main__":
    unittest.main()
