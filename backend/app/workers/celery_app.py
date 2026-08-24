from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "crm_worker", broker=settings.CELERY_BROKER_URL, backend=settings.CELERY_RESULT_BACKEND
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# Hourly sweep of scheduled report deliveries (see workers/tasks.py).
celery_app.conf.beat_schedule = {
    "deliver-due-scheduled-reports": {
        "task": "app.workers.tasks.deliver_due_scheduled_reports",
        "schedule": crontab(minute=0),
    },
}
