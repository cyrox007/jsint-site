from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from settings import config

config.validate()

CELERY_QUEUE_NAME = "jsint-site.celery"
CELERY_REDIS_KEY_PREFIX = "jsint-site:celery:"

celery_app = Celery(
    "jsint_site",
    broker=config.CELERY_BROKER_URL,
    backend=config.CELERY_RESULT_BACKEND,
    include=["tasks.system"],
)

celery_app.conf.update(
    task_default_queue=CELERY_QUEUE_NAME,
    task_default_exchange=CELERY_QUEUE_NAME,
    task_default_routing_key=CELERY_QUEUE_NAME,
    task_routes={"*": {"queue": CELERY_QUEUE_NAME, "routing_key": CELERY_QUEUE_NAME}},
    broker_transport_options={"global_keyprefix": CELERY_REDIS_KEY_PREFIX},
    result_backend_transport_options={"global_keyprefix": CELERY_REDIS_KEY_PREFIX},
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    beat_schedule={
        "background-heartbeat-every-30-seconds": {
            "task": "tasks.system.background_heartbeat",
            "schedule": 30.0,
        },
        "purge-revoked-license-keys-daily": {
            "task": "tasks.system.purge_revoked_license_keys",
            "schedule": crontab(hour=3, minute=17),
        },
        "sync-vanga-actual-ratings": {
            "task": "tasks.system.sync_vanga_actual_ratings",
            "schedule": crontab(hour="*/6", minute=23),
        },
    },
)


# Регистрируем системные задачи при импорте приложения, чтобы CLI, тесты,
# Worker и Beat видели один и тот же task registry до первого сообщения.
import tasks.system  # noqa: E402,F401
