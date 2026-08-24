import io
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.logging import get_logger
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(ignore_result=True)
def send_email_async(to_email: str, subject: str, body: str):
    # Asynchronous email delivery logic (SMTP / SendGrid / AWS SES)
    logger.info("Sending email to %s with subject: %s", to_email, subject)
    return {"status": "sent", "to": to_email}


@celery_app.task
def calculate_lead_score_async(lead_id: str):
    # Background AI scoring job
    logger.info("Calculating AI lead score for lead: %s", lead_id)
    return {"lead_id": lead_id, "status": "processed"}


@celery_app.task
def deliver_due_scheduled_reports():
    """Generate and email every scheduled report whose next_run is due.

    Runs hourly via celery beat. For each due schedule it builds the report
    CSV from live data, uploads it to object storage, emails a presigned
    download link, and advances ``next_run`` — each schedule is committed
    independently so one failure does not block or duplicate the others.
    """
    return _run_deliver_due_scheduled_reports()


def _run_deliver_due_scheduled_reports() -> dict:
    import asyncio

    return asyncio.run(_deliver_due_reports())


async def _deliver_due_reports() -> dict:
    from app.db.session import AsyncSessionLocal
    from app.models.report import ScheduledReport
    from app.services.report_service import compute_next_run, report_service
    from app.services.s3_service import s3_service
    from app.workers.tasks import send_email_async

    now = datetime.now(UTC)
    delivered = 0
    failed = 0
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(ScheduledReport)
            .where(ScheduledReport.next_run.is_not(None), ScheduledReport.next_run <= now)
            .with_for_update(skip_locked=True)
        )
        due = list(res.scalars().all())

        for sched in due:
            # Capture plain values up front: after a rollback the ORM instance's
            # attributes are expired and touching them would trigger a lazy load.
            sched_id = sched.id
            sched_org = sched.organization_id
            sched_type = sched.report_type
            sched_email = sched.email
            try:
                csv_text = await report_service.build_report_csv_for_organization(
                    db, sched_org, sched_type
                )
                object_name = f"exports/scheduled/{sched_id}/{now.strftime('%Y%m%dT%H%M%SZ')}.csv"
                s3_key = s3_service.upload_file(
                    io.BytesIO(csv_text.encode("utf-8")),
                    object_name=object_name,
                    content_type="text/csv",
                )
                download_url = s3_service.generate_presigned_url(s3_key)

                send_email_async.delay(
                    to_email=sched_email,
                    subject=f"Scheduled report: {sched_type}",
                    body=(
                        f"Your scheduled '{sched_type}' report is ready.\n\n"
                        f"Download (link valid for 1 hour): {download_url}\n"
                    ),
                )

                # Advance only after successful generation+upload+enqueue.
                current_next = sched.next_run
                base = max(now, current_next) if isinstance(current_next, datetime) else now
                sched.next_run = compute_next_run(sched.frequency, base)  # type: ignore[assignment]
                await db.commit()
                delivered += 1
            except Exception:
                await db.rollback()
                failed += 1
                logger.exception(
                    "Failed to deliver scheduled report id=%s org=%s type=%s",
                    sched_id,
                    sched_org,
                    sched_type,
                )

    logger.info("Scheduled report delivery finished: delivered=%s failed=%s", delivered, failed)
    return {"delivered": delivered, "failed": failed}
