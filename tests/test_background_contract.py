import unittest

from celery_app import CELERY_QUEUE_NAME, CELERY_REDIS_KEY_PREFIX, celery_app
from components.background.status import BACKGROUND_HEARTBEAT_KEY
from settings import config


class BackgroundRuntimeContractTests(unittest.TestCase):
    def test_celery_uses_dedicated_redis_databases(self):
        self.assertNotEqual(config.CELERY_BROKER_URL, config.REDIS_URL)
        self.assertNotEqual(config.CELERY_RESULT_BACKEND, config.REDIS_URL)

    def test_celery_queue_is_isolated_for_all_workers(self):
        from pathlib import Path
        from unittest.mock import patch

        from services.admin_notifications import AdminNotificationService

        self.assertEqual(CELERY_QUEUE_NAME, "jsint-site.celery")
        self.assertEqual(celery_app.conf.task_default_queue, CELERY_QUEUE_NAME)
        self.assertEqual(
            celery_app.conf.broker_transport_options["global_keyprefix"],
            CELERY_REDIS_KEY_PREFIX,
        )
        self.assertEqual(
            celery_app.conf.result_backend_transport_options["global_keyprefix"],
            CELERY_REDIS_KEY_PREFIX,
        )
        for path in (
            "deploy/jsint-site-celery-worker.service",
            "deploy/checkout/jsint-site-celery-worker.service",
        ):
            unit = (Path(__file__).resolve().parents[1] / path).read_text(encoding="utf-8")
            self.assertIn("--queues=jsint-site.celery", unit)

        with patch.object(celery_app, "send_task") as send:
            AdminNotificationService.enqueue_push("123")
        send.assert_called_once_with(
            "tasks.system.deliver_admin_push",
            args=["123"],
            queue=CELERY_QUEUE_NAME,
            routing_key=CELERY_QUEUE_NAME,
        )

    def test_failed_enqueue_falls_back_to_direct_delivery(self):
        from unittest.mock import patch

        from services.admin_notifications import AdminNotificationService
        from services.web_push import WebPushService

        with patch.object(celery_app, "send_task", side_effect=RuntimeError("broker")):
            with patch.object(WebPushService, "deliver_notification_by_id") as deliver:
                AdminNotificationService.enqueue_push("123")
        deliver.assert_called_once_with("123")

    def test_heartbeat_task_is_registered_and_scheduled(self):
        task_name = "tasks.system.background_heartbeat"
        self.assertIn(task_name, celery_app.tasks)

        schedule = celery_app.conf.beat_schedule
        entry = schedule["background-heartbeat-every-30-seconds"]
        self.assertEqual(entry["task"], task_name)
        self.assertEqual(float(entry["schedule"]), 30.0)

    def test_heartbeat_key_is_namespaced(self):
        self.assertEqual(BACKGROUND_HEARTBEAT_KEY, "jsint:background:heartbeat")


if __name__ == "__main__":
    unittest.main()
