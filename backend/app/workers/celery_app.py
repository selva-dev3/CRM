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
    imports=("app.workers.tasks", "app.workers.whatsapp"),
)

# Hourly sweep of scheduled report deliveries (see workers/tasks.py).
celery_app.conf.beat_schedule = {
    "process-whatsapp-inbox-outbox": {
        "task": "app.workers.whatsapp.process_pending",
        "schedule": 10.0,
    },
    "cleanup-expired-auth-records": {
        "task": "app.workers.tasks.cleanup_expired_auth_records",
        "schedule": crontab(minute=10),
    },
    "cleanup-deleted-organization-files": {
        "task": "app.workers.tasks.cleanup_deleted_organization_files",
        "options": {"queue": "organization_cleanup"},
        "schedule": 30.0,
    },
    "deliver-pending-emails": {
        "task": "app.workers.tasks.deliver_pending_emails",
        "schedule": 30.0,
    },
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
    "deliver-pending-integration-events": {
        "task": "app.workers.tasks.deliver_pending_integration_events",
        "schedule": 30.0,
    },
    "send-due-invoice-reminders": {
        "task": "app.workers.tasks.send_due_invoice_reminders",
        "schedule": crontab(minute=15),
    },
    "reconcile-invoice-payment-aggregates": {
        "task": "app.workers.tasks.reconcile_invoice_payment_aggregates",
        "schedule": crontab(minute=30),
    },
    "reconcile-provider-subscriptions": {
        "task": "app.workers.tasks.reconcile_provider_subscriptions",
        "schedule": crontab(minute=45),
    },
}

# Dedicated cleanup deployments must not schedule unrelated delivery backlog.
if settings.ORGANIZATION_CLEANUP_ONLY:
    celery_app.conf.beat_schedule = {
        "cleanup-deleted-organization-files": celery_app.conf.beat_schedule["cleanup-deleted-organization-files"]
    }
