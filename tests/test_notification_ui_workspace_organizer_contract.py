from __future__ import annotations

import pathlib
import unittest

from services.admin_notifications import AdminNotificationService


ROOT = pathlib.Path(__file__).resolve().parents[1]


class NotificationUiAndWorkspaceOrganizerContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_admin_header_has_actionable_notification_center(self):
        app = self.read("app.py")
        header = self.read("templates/dashboard/^shared/header/index.html")
        sidebar = self.read("templates/dashboard/^shared/sidebar/index.html")
        settings = self.read("templates/dashboard/inbox/settings.html")
        router = self.read("views/dashboard/inbox/router.py")

        self.assertIn("header-notifications", header)
        self.assertIn("admin_unread_count", header)
        self.assertIn("admin_recent_notifications", header)
        self.assertIn("Требуют внимания", header)
        self.assertIn("Центр уведомлений", header)
        self.assertIn("Настройки доставки", header)
        self.assertIn("AdminNotification.status == \"new\"", app)
        self.assertIn("<span>Уведомления</span>", sidebar)
        self.assertIn("admin.inbox.settings", router)
        self.assertIn("Включить уведомления", settings)
        self.assertIn("Отправить тест", settings)
        self.assertIn("Диагностика Notes", settings)
        self.assertNotIn("URL темы ntfy", settings)

    def test_inbox_and_contacts_default_to_attention_queue(self):
        inbox = self.read("views/dashboard/inbox/views.py")
        contacts = self.read("views/dashboard/contact/views.py")
        inbox_template = self.read("templates/dashboard/inbox/index.html")
        contact_template = self.read("templates/dashboard/contact/index.html")

        self.assertIn('request.args.get("status", "new")', inbox)
        self.assertIn('request.args.get("status", "new")', contacts)
        self.assertIn("Требуют внимания", inbox_template)
        self.assertIn("Прочитанные", inbox_template)
        self.assertIn("Архив", inbox_template)
        self.assertIn("Новые", contact_template)
        self.assertIn("Прочитанные", contact_template)
        self.assertIn("Архив", contact_template)

    def test_notification_filters_keep_checkbox_and_text_aligned_on_mobile(self):
        styles = self.read("templates/dashboard/inbox/style.css")

        self.assertIn(".notification-toggle{display:flex", styles)
        self.assertIn('input[type="checkbox"]{width:20px!important', styles)
        self.assertIn("flex:0 0 20px", styles)
        self.assertIn(".notification-settings-card__actions .btn{width:100%", styles)

    def test_native_push_test_reports_delivery_synchronously(self):
        api = self.read("views/dashboard/inbox/webpush.py")
        settings = self.read("templates/dashboard/inbox/settings.html")

        self.assertIn("WebPushService.deliver_notification", api)
        self.assertIn("result[\"delivered\"]", api)
        self.assertIn("Push не доставлен", api)
        self.assertIn("Отправить тест", settings)
        self.assertIn("Тест отправлен", settings)

    def test_admin_panel_is_installable_pwa_without_private_cache(self):
        app = self.read("app.py")
        base = self.read("templates/dashboard/^core/base.html")
        manifest = self.read("static/admin-pwa/manifest.webmanifest")
        worker = self.read("static/admin-pwa/service-worker.js")

        self.assertIn("admin_pwa_manifest", app)
        self.assertIn("admin_pwa_service_worker", app)
        self.assertIn('rel="manifest"', base)
        self.assertIn("serviceWorker.register", base)
        self.assertIn('"display": "standalone"', manifest)
        self.assertIn('"start_url": "."', manifest)
        self.assertNotIn("caches.open", worker)
        self.assertNotIn("addEventListener('fetch'", worker)
        self.assertIn("addEventListener('push'", worker)
        self.assertIn("notificationclick", worker)

    def test_legacy_push_token_crypto_remains_available_for_optional_fallback(self):
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

        self.assertIn("workspace_organizer_router.install(app)", app)
        self.assertIn('"/workspace-organizer"', router)
        self.assertIn('"/notes"', router)
        self.assertIn("code=301", router)
        self.assertIn("ReleaseRecord.version_code.desc()", view)
        self.assertIn("PublicationChannelService.list_public", view)
        self.assertIn("SoftwareApplication", view)
        self.assertIn("Workspace Organizer", template)
        self.assertIn("workspace-organizer-mark.svg", template)
        self.assertIn("Self-hosted", template)
        self.assertIn(
            "url_for('contact', subject='Workspace Organizer')",
            template,
        )
        self.assertIn('"workspace-organizer"', sitemap)
        self.assertNotIn(
            '(urljoin(f"{base_url}/", "notes"), None)',
            sitemap,
        )

    def test_workspace_organizer_uses_jsinteractive_visual_language(self):
        styles = self.read(
            "templates/public/workspace_organizer/style.css"
        )

        self.assertIn("jsinteractive-mountain.svg", styles)
        self.assertIn("var(--border)", styles)
        self.assertIn("#071018", styles)
        self.assertNotIn(
            "linear-gradient(180deg,#f9fcff 0%,#eef7ff",
            styles,
        )

    def test_product_cta_prefills_contact_subject(self):
        contact = self.read("views/public/contact/views.py")
        self.assertIn('request.args.get("subject", "")', contact)
        self.assertIn('values = {"subject": subject}', contact)


if __name__ == "__main__":
    unittest.main()
