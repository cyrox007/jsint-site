import logging

from celery_app import celery_app
from components.background.status import record_background_heartbeat
from database import Database
from services.notes_control_plane import NotesControlPlane
from services.admin_notifications import AdminNotificationService
from services.yandex_indexing import YandexIndexingService


logger = logging.getLogger(__name__)


@celery_app.task(
    name="tasks.system.background_heartbeat",
    ignore_result=True,
)
def background_heartbeat():
    """Сквозная проверка Beat -> broker -> Worker -> Redis."""
    return record_background_heartbeat()


@celery_app.task(
    name="tasks.system.notify_yandex_indexnow",
    ignore_result=True,
    autoretry_for=(RuntimeError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def notify_yandex_indexnow(urls):
    """Сообщает Яндексу об изменённых публичных URL через IndexNow."""
    return YandexIndexingService.notify(list(urls or []))


@celery_app.task(
    name="tasks.system.purge_revoked_license_keys",
    ignore_result=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def purge_revoked_license_keys():
    """Удаляет лицензии, отключённые не меньше месяца назад."""
    session = Database.connect_database()
    try:
        deleted = NotesControlPlane.purge_revoked_licenses(session)
        if deleted:
            logger.info("Удалено отключённых лицензий: %s", deleted)
        return deleted
    finally:
        session.close()


@celery_app.task(
    name="tasks.system.deliver_admin_push",
    ignore_result=True,
    autoretry_for=(RuntimeError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def deliver_admin_push(notification_id: str):
    """Отправляет безопасный push о новом событии администратору."""
    return AdminNotificationService.deliver_push(notification_id)
