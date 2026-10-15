from __future__ import annotations

import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class NativeWebPushContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_admin_uses_native_web_push_without_ntfy_setup(self):
        settings = self.read("templates/dashboard/inbox/settings.html")
        router = self.read("views/dashboard/inbox/router.py")
        worker = self.read("static/admin-pwa/service-worker.js")

        self.assertIn("Включить уведомления", settings)
        self.assertIn("PushManager", settings)
        self.assertIn("Notification.requestPermission", settings)
        self.assertNotIn("ntfy topic URL", settings)
        self.assertNotIn("URL темы ntfy", settings)
        self.assertIn("admin.inbox.web_push_subscribe", router)
        self.assertIn("admin.inbox.web_push_test", router)
        self.assertIn("addEventListener('push'", worker)
        self.assertIn("showNotification", worker)

    def test_web_push_is_persisted_and_migrated(self):
        model = self.read("models/web_push.py")
        migration = self.read(
            "alembic/versions/a91c7e4b2d10_admin_web_push_subscriptions.py"
        )
        requirements = self.read("requirements.txt")

        self.assertIn("admin_web_push_subscriptions", model)
        self.assertIn("user_id", model)
        self.assertIn('down_revision = "f6b1d4c7e820"', migration)
        self.assertIn("pywebpush==", requirements)

    def test_vapid_key_is_generated_locally_and_not_sent_to_browser(self):
        service = self.read("services/web_push.py")

        self.assertIn("ec.generate_private_key", service)
        self.assertIn("webpush(", service)
        self.assertIn("public_key", service)
        self.assertIn("webpush-vapid.pem", service)
        self.assertNotIn("vapid_private_key\":", service)

    def test_background_delivery_includes_native_web_push(self):
        tasks = self.read("tasks/system.py")
        contact = self.read("views/public/contact/views.py")

        self.assertIn("WebPushService.deliver_notification_by_id", tasks)
        self.assertIn("AdminNotificationService.enqueue_push(notification.id)", contact)


if __name__ == "__main__":
    unittest.main()
