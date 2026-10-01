from __future__ import annotations

import pathlib
import unittest

from services.admin_notifications import AdminNotificationService


ROOT = pathlib.Path(__file__).resolve().parents[1]


class NotificationUiAndWorkspaceOrganizerContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_admin_header_has_visible_notification_center(self):
        header = self.read("templates/dashboard/^shared/header/index.html")
        sidebar = self.read("templates/dashboard/^shared/sidebar/index.html")
        settings = self.read("templates/dashboard/inbox/settings.html")
        router = self.read("views/dashboard/inbox/router.py")

        self.assertIn("header-notifications", header)
        self.assertIn("admin_unread_count", header)
        self.assertIn("admin_recent_notifications", header)
        self.assertIn("Все уведомления", header)
        self.assertIn("Настроить push", header)
        self.assertIn("<span>Уведомления</span>", sidebar)
        self.assertIn("admin.inbox.settings", router)
        self.assertIn("ntfy topic URL", settings)
        self.assertIn("Отправить тест", settings)
        self.assertIn("Диагностика Notes", settings)

    def test_push_token_encryption_round_trip_and_url_validation(self):
        token = "secret-token-for-test"
        encrypted = AdminNotificationService._encrypt_token(token)

        self.assertNotEqual(encrypted, token)
        self.assertNotIn(token, encrypted)
        self.assertEqual(
            AdminNotificationService._decrypt_token(encrypted),
            token,
        )
        self.assertEqual(
            AdminNotificationService._validate_push_url(
                "https://ntfy.example.test/private-topic"
            ),
            "https://ntfy.example.test/private-topic",
        )
        self.assertEqual(
            AdminNotificationService._validate_push_url(
                "http://127.0.0.1:8080/private-topic"
            ),
            "http://127.0.0.1:8080/private-topic",
        )
        with self.assertRaises(ValueError):
            AdminNotificationService._validate_push_url(
                "http://public.example.test/topic"
            )

    def test_workspace_organizer_is_public_and_search_visible(self):
        app = self.read("app.py")
        router = self.read("views/public/workspace_organizer/routers.py")
        view = self.read("views/public/workspace_organizer/views.py")
        template = self.read("templates/public/workspace_organizer/index.html")
        sitemap = self.read("views/public/seo.py")
        header = self.read("templates/public/^shared/header/index.html")
        footer = self.read("templates/public/^shared/footer/index.html")

        self.assertIn("workspace_organizer_router.install(app)", app)
        self.assertIn('"/workspace-organizer"', router)
        self.assertIn('"/notes"', router)
        self.assertIn("code=301", router)
        self.assertIn("ReleaseRecord.version_code.desc()", view)
        self.assertIn("SoftwareApplication", view)
        self.assertIn("Workspace Organizer", template)
        self.assertIn("workspace-organizer-logo.svg", template)
        self.assertIn("Порядок", template)
        self.assertIn("Self-hosted", template)
        self.assertIn("XChaCha20-Poly1305", template)
        self.assertIn('url_for(\'contact\', subject=\'Workspace Organizer\')', template)
        self.assertIn('"workspace-organizer"', sitemap)
        self.assertNotIn('(urljoin(f"{base_url}/", "notes"), None)', sitemap)
        self.assertIn("_SITEMAP_STATIC_URLS = 3", sitemap)
        self.assertIn("workspace_organizer", header)
        self.assertIn("workspace_organizer", footer)

    def test_product_cta_prefills_contact_subject(self):
        contact = self.read("views/public/contact/views.py")
        self.assertIn('request.args.get("subject", "")', contact)
        self.assertIn('values = {"subject": subject}', contact)


if __name__ == "__main__":
    unittest.main()
