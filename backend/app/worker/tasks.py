from app.worker.celery_app import celery_app

@celery_app.task
def send_email_async(to_email: str, subject: str, body: str):
    # Asynchronous email delivery logic (SMTP / SendGrid / AWS SES)
    print(f"Sending email to {to_email} with subject: {subject}")
    return {"status": "sent", "to": to_email}

@celery_app.task
def calculate_lead_score_async(lead_id: str):
    # Background AI scoring job
    print(f"Calculating AI lead score for lead: {lead_id}")
    return {"lead_id": lead_id, "status": "processed"}
