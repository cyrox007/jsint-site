import unittest

from celery_app import celery_app
from components.background.status import BACKGROUND_HEARTBEAT_KEY
from settings import config


class BackgroundRuntimeContractTests(unittest.TestCase):
    def test_celery_uses_dedicated_redis_databases(self):
        self.assertNotEqual(config.CELERY_BROKER_URL, config.REDIS_URL)
        self.assertNotEqual(config.CELERY_RESULT_BACKEND, config.REDIS_URL)

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
