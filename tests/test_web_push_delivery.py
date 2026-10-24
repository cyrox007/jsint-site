from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from celery.exceptions import TimeoutError as CeleryTimeoutError
from flask import Flask, session
from pywebpush import WebPushException

from celery_app import celery_app
from services.admin_notifications import AdminNotificationService
from services.web_push import WebPushService
from tasks.system import deliver_admin_push
from views.dashboard.inbox.webpush import WebPushTestApi


class WebPushDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.notification = SimpleNamespace(
            id=uuid4(), details={"name": "Sender"}, title="Contact", summary="Message",
            severity="info", kind="contact", push_status="skipped",
        )

    def deliver(self, subscriptions, send_error=None, allowed=True):
        for device in subscriptions:
            device.id = uuid4()
        self.db.query.return_value.filter.return_value.all.return_value = subscriptions
        with patch.object(WebPushService, "_allowed_by_preferences", return_value=allowed):
            with patch.object(WebPushService, "_send", side_effect=send_error):
                return WebPushService.deliver_notification(self.db, self.notification)

    def test_native_success_survives_legacy_skipped_status(self):
        result = self.deliver([SimpleNamespace()])
        self.assertEqual(result["delivered"], 1)
        self.assertEqual(self.notification.details["web_push"]["status"], "sent")
        self.assertEqual(self.notification.push_status, "skipped")
        self.assertEqual(self.notification.details["name"], "Sender")
        self.db.commit.assert_called_once()

    def test_disabled_filter_is_recorded_without_sending(self):
        result = self.deliver([], allowed=False)
        self.assertTrue(result["skipped"])
        self.assertIn("фильтром", self.notification.details["web_push"]["message"])
        self.db.query.assert_not_called()
        self.db.commit.assert_called_once()

    def test_missing_subscriptions_are_distinct_from_filter(self):
        self.deliver([])
        self.assertEqual(self.notification.details["web_push"]["message"], "Нет активных подписок устройств")

    def test_expired_subscription_is_removed_and_recorded(self):
        device = SimpleNamespace()
        error = WebPushException("expired", response=SimpleNamespace(status_code=410))
        result = self.deliver([device], send_error=error)
        self.assertEqual(result["expired"], 1)
        self.db.delete.assert_called_once_with(device)
        self.assertIn("истекли", self.notification.details["web_push"]["message"])

    def test_network_failure_is_recorded(self):
        with self.assertLogs("services.web_push", level="ERROR"):
            result = self.deliver([SimpleNamespace()], send_error=OSError("offline"))
        self.assertEqual(result["failed"], 1)
        self.assertEqual(self.notification.details["web_push"]["status"], "failed")

    def test_partial_delivery_does_not_claim_all_devices_received(self):
        with self.assertLogs("services.web_push", level="ERROR"):
            self.deliver([SimpleNamespace(), SimpleNamespace()], send_error=[None, OSError("offline")])
        self.assertEqual(self.notification.details["web_push"]["status"], "partial")

    def test_normal_event_obeys_filter_but_explicit_test_bypasses_it(self):
        preferences = SimpleNamespace(notify_contact=False, notify_urgent=False)
        self.db.query.return_value.filter.return_value.first.return_value = preferences
        self.assertFalse(WebPushService._allowed_by_preferences(self.db, self.notification))
        self.notification.details = {"force_push": True}
        self.assertTrue(WebPushService._allowed_by_preferences(self.db, self.notification))

    def test_test_dispatch_waits_for_same_celery_task_and_scopes_user(self):
        user_id = uuid4()
        with patch.object(celery_app, "send_task") as send:
            result = AdminNotificationService.enqueue_push(self.notification.id, user_id=user_id, wait=True)
        self.assertEqual(send.call_args.args, ("tasks.system.deliver_admin_push",))
        self.assertEqual(send.call_args.kwargs["kwargs"], {"user_id": str(user_id)})
        send.return_value.get.assert_called_once_with(timeout=10, propagate=True)
        self.assertIs(result, send.return_value.get.return_value)

    def test_worker_timeout_is_not_retried_directly(self):
        with patch.object(celery_app, "send_task") as send:
            send.return_value.get.side_effect = CeleryTimeoutError()
            with patch.object(WebPushService, "deliver_notification_by_id") as direct:
                with self.assertRaises(CeleryTimeoutError):
                    AdminNotificationService.enqueue_push(self.notification.id, wait=True)
        direct.assert_not_called()

    def test_test_broker_failure_reports_fallback_transport(self):
        with patch.object(celery_app, "send_task", side_effect=RuntimeError("broker")):
            with patch.object(WebPushService, "deliver_notification_by_id", return_value={"delivered": 1}):
                with self.assertLogs("services.admin_notifications", level="ERROR"):
                    result = AdminNotificationService.enqueue_push(self.notification.id, user_id=uuid4(), wait=True)
        self.assertEqual(result["transport"], "direct_fallback")

    def test_worker_propagates_native_failure_instead_of_claiming_success(self):
        with patch.object(WebPushService, "deliver_notification_by_id", side_effect=OSError("offline")):
            with self.assertRaises(OSError):
                deliver_admin_push.run(str(self.notification.id))

    def test_legacy_delivery_cannot_replace_native_result(self):
        with patch.object(WebPushService, "deliver_notification_by_id", return_value={"delivered": 1}):
            with patch.object(AdminNotificationService, "deliver_push", return_value=False):
                result = deliver_admin_push.run(str(self.notification.id))
        self.assertEqual(result["web_push"]["delivered"], 1)
        self.assertFalse(result["legacy"])

    def test_test_api_exposes_worker_timeout_and_marks_test_read(self):
        app = Flask(__name__)
        app.secret_key = "test"
        with app.test_request_context("/", method="POST"):
            session["user_id"] = str(uuid4())
            with patch.object(AdminNotificationService, "create_test_push", return_value=self.notification):
                with patch.object(AdminNotificationService, "enqueue_push", side_effect=CeleryTimeoutError()):
                    response, status = WebPushTestApi.post.__wrapped__.__wrapped__(WebPushTestApi(), self.db)
        self.assertEqual(status, 504)
        self.assertIn("Celery worker", response.get_json()["error"])
        self.assertEqual(self.notification.status, "read")
        self.db.refresh.assert_called_once_with(self.notification)

    def test_test_api_returns_result_from_worker_and_refreshes_its_status(self):
        app = Flask(__name__)
        app.secret_key = "test"
        counts = {"delivered": 1, "failed": 0, "expired": 0, "total": 1, "skipped": False}
        with app.test_request_context("/", method="POST"):
            session["user_id"] = str(uuid4())
            with patch.object(AdminNotificationService, "create_test_push", return_value=self.notification):
                with patch.object(AdminNotificationService, "enqueue_push", return_value={"web_push": counts}):
                    response = WebPushTestApi.post.__wrapped__.__wrapped__(WebPushTestApi(), self.db)
        self.assertTrue(response.get_json()["ok"])
        self.assertEqual(response.get_json()["transport"], "celery")
        self.assertEqual(response.get_json()["delivered"], 1)
        self.db.refresh.assert_called_once_with(self.notification)


if __name__ == "__main__":
    unittest.main()
