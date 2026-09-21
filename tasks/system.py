from celery_app import celery_app
from components.background.status import record_background_heartbeat


@celery_app.task(
    name="tasks.system.background_heartbeat",
    ignore_result=True,
)
def background_heartbeat():
    """End-to-end heartbeat proving Beat -> broker -> Worker -> Redis."""
    return record_background_heartbeat()
