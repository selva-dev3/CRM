import asyncio
import io
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.logging import get_logger
from app.workers.celery_app import celery_app

logger = get_logger(__name__)

# Scheduled download links must comfortably outlive the hourly delivery
# sweep (MinIO/S3 allows up to 7 days).
_SCHEDULED_LINK_EXPIRY_SECONDS = 86400


@celery_app.task
def calculate_lead_score_async(lead_id: str):
    # Background AI scoring job
    logger.info("Calculating AI lead score for lead: %s", lead_id)
    return {"lead_id": lead_id, "status": "processed"}


@celery_app.task(ignore_result=True)
def deliver_due_scheduled_reports():
    """Generate, email, and mark-delivered every scheduled report that is due.

    Runs hourly via celery beat. For each due schedule it builds the report
    CSV from live data, uploads it to object storage, emails a presigned
    download link through the production email sender, and only then
    advances ``next_run`` — a failed send leaves the schedule untouched so
    it is retried on the next sweep. Each schedule commits independently.
    """
    return asyncio.run(_deliver_due_reports())


async def _deliver_due_reports() -> dict:
    from app.core.config import settings
    from app.db.session import AsyncSessionLocal
    from app.models.report import ScheduledReport
    from app.services.email_service import send_email as send_email_via_brevo
    from app.services.report_service import compute_next_run, report_service
    from app.services.s3_service import s3_service

    if not settings.BREVO_API_KEY:
        logger.error(
            "Scheduled report delivery skipped entirely: BREVO_API_KEY is not "
            "configured; due schedules were left untouched and will be retried."
        )
        return {"delivered": 0, "failed": 0, "skipped_unconfigured": True}

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
                download_url = s3_service.generate_presigned_url(
                    s3_key, expiration_seconds=_SCHEDULED_LINK_EXPIRY_SECONDS
                )

                sent = await asyncio.to_thread(
                    send_email_via_brevo,
                    to_email=sched_email,
                    subject=f"Scheduled report: {sched_type}",
                    html_content=(
                        f"<p>Your scheduled <strong>{sched_type}</strong> report is ready.</p>"
                        f'<p><a href="{download_url}">Download the CSV</a> '
                        f"(link valid for 24 hours).</p>"
                    ),
                )
                if not sent:
                    # The sender already logged the provider-side failure.
                    raise RuntimeError("email delivery failed")

                # Advance only after generation+upload+actual delivery succeeded.
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
