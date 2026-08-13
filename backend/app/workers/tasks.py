from app.core.logging import get_logger
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task
def send_email_async(to_email: str, subject: str, body: str):
    # Asynchronous email delivery logic (SMTP / SendGrid / AWS SES)
    logger.info("Sending email to %s with subject: %s", to_email, subject)
    return {"status": "sent", "to": to_email}


@celery_app.task
def calculate_lead_score_async(lead_id: str):
    # Background AI scoring job
    logger.info("Calculating AI lead score for lead: %s", lead_id)
    return {"lead_id": lead_id, "status": "processed"}
