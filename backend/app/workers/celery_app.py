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
    imports=("app.workers.tasks",),
)

# Hourly sweep of scheduled report deliveries (see workers/tasks.py).
celery_app.conf.beat_schedule = {
    "deliver-due-scheduled-reports": {
        "task": "app.workers.tasks.deliver_due_scheduled_reports",
        "schedule": crontab(minute=0),
    },
    "deliver-pending-quotes": {
        "task": "app.workers.tasks.deliver_pending_quotes",
        "schedule": 60.0,
    },
    "deliver-pending-invoices": {
        "task": "app.workers.tasks.deliver_pending_invoices",
        "schedule": 60.0,
    },
    "deliver-pending-payment-receipts": {
        "task": "app.workers.tasks.deliver_pending_payment_receipts",
        "schedule": 60.0,
    },
    "send-due-invoice-reminders": {
        "task": "app.workers.tasks.send_due_invoice_reminders",
        "schedule": crontab(minute=15),
    },
}
