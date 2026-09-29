from celery_app import celery_app
from components.background.status import record_background_heartbeat
from services.yandex_indexing import YandexIndexingService


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
