import asyncio
import html
import io
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select, update

from app.core.logging import get_logger
from app.workers.celery_app import celery_app

logger = get_logger(__name__)

_INTEGRATION_CLAIM_TTL = timedelta(minutes=2)
_INTEGRATION_MAX_ATTEMPTS = 5


@celery_app.task(name="app.workers.tasks.cleanup_expired_auth_records", ignore_result=True)
def cleanup_expired_auth_records():
    """Remove only expired or already-revoked authentication records."""
    return asyncio.run(_cleanup_expired_auth_records())


async def _cleanup_expired_auth_records() -> dict[str, int]:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import settings
    from app.models import MagicLinkToken, PasswordReset, RefreshToken, UserSession

    now = datetime.now(UTC)
    engine = create_async_engine(settings.DATABASE_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as db:
            counts = {}
            for name, model, predicate in (
                (
                    "refresh_tokens",
                    RefreshToken,
                    (RefreshToken.expires_at <= now) | RefreshToken.is_revoked.is_(True),
                ),
                (
                    "sessions",
                    UserSession,
                    (UserSession.expires_at <= now) | UserSession.is_current.is_(False),
                ),
                (
                    "magic_links",
                    MagicLinkToken,
                    (MagicLinkToken.expires_at <= now) | MagicLinkToken.is_used.is_(True),
                ),
                (
                    "password_resets",
                    PasswordReset,
                    (PasswordReset.expires_at <= now) | PasswordReset.is_used.is_(True),
                ),
            ):
                result = await db.execute(model.__table__.delete().where(predicate))
                counts[name] = result.rowcount or 0
            await db.commit()
            return counts
    finally:
        await engine.dispose()


@celery_app.task(
    name="app.workers.tasks.cleanup_deleted_organization_files",
    ignore_result=True,
    queue="organization_cleanup",
)
def cleanup_deleted_organization_files():
    return asyncio.run(_cleanup_deleted_organization_files())


async def _cleanup_deleted_organization_files() -> int:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import settings
    from app.services.organization_cleanup_service import cleanup_organization_files

    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            return await cleanup_organization_files(db)
    finally:
        await engine.dispose()


@celery_app.task(name="app.workers.tasks.deliver_pending_integration_events", ignore_result=True)
def deliver_pending_integration_events():
    return asyncio.run(_deliver_pending_integration_events())


async def _deliver_pending_integration_events() -> dict[str, int]:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import settings
    from app.models import IntegrationDelivery

    engine = create_async_engine(settings.DATABASE_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    delivered = 0
    failed = 0
    lost_claim = 0
    try:
        now = datetime.now(UTC)
        async with factory() as db:
            result = await db.execute(
                select(IntegrationDelivery.id)
                .where(
                    or_(
                        and_(
                            IntegrationDelivery.status.in_(("Pending", "Retry")),
                            (IntegrationDelivery.next_attempt_at.is_(None))
                            | (IntegrationDelivery.next_attempt_at <= now),
                            (IntegrationDelivery.claimed_until.is_(None))
                            | (IntegrationDelivery.claimed_until < now),
                        ),
                        and_(
                            IntegrationDelivery.status == "Processing",
                            IntegrationDelivery.claimed_until < now,
                        ),
                    )
                )
                .order_by(IntegrationDelivery.created_at.asc())
                .limit(100)
            )
            delivery_ids = list(result.scalars().all())
        for delivery_id in delivery_ids:
            outcome = await _deliver_one_integration_event(factory, delivery_id)
            delivered += int(outcome == "delivered")
            failed += int(outcome == "failed")
            lost_claim += int(outcome == "lost_claim")
        return {"delivered": delivered, "failed": failed, "lost_claim": lost_claim}
    finally:
        await engine.dispose()


async def _deliver_one_integration_event(factory, delivery_id: str) -> str:
    import httpx

    from app.models import Integration, IntegrationDelivery
    from app.services.integration_service import IntegrationService

    now = datetime.now(UTC)
    claim_until = now + _INTEGRATION_CLAIM_TTL
    async with factory() as db:
        result = await db.execute(
            update(IntegrationDelivery)
            .where(
                IntegrationDelivery.id == delivery_id,
                or_(
                    and_(
                        IntegrationDelivery.status.in_(("Pending", "Retry")),
                        (IntegrationDelivery.next_attempt_at.is_(None))
                        | (IntegrationDelivery.next_attempt_at <= now),
                        (IntegrationDelivery.claimed_until.is_(None))
                        | (IntegrationDelivery.claimed_until < now),
                    ),
                    and_(
                        IntegrationDelivery.status == "Processing",
                        IntegrationDelivery.claimed_until < now,
                    ),
                ),
            )
            .values(status="Processing", claimed_until=claim_until)
            .returning(
                IntegrationDelivery.organization_id,
                IntegrationDelivery.integration_id,
                IntegrationDelivery.provider,
                IntegrationDelivery.payload,
                IntegrationDelivery.attempts,
            )
        )
        claimed = result.first()
        await db.commit()
    if claimed is None:
        return "skipped"

    organization_id, integration_id, provider, payload, previous_attempts = tuple(claimed)
    attempts = int(previous_attempts or 0) + 1
    error_message: str | None = None
    status_code: int | None = None
    try:
        async with factory() as db:
            integration = await db.get(Integration, integration_id)
        if (
            integration is None
            or integration.organization_id != organization_id
            or not integration.is_connected
        ):
            raise RuntimeError("integration disconnected")
        webhook_url = IntegrationService._decrypt_secret(integration.webhook_url)
        if not webhook_url:
            raise RuntimeError("integration webhook unavailable")
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                webhook_url,
                json=payload,
                headers={"Idempotency-Key": delivery_id},
            )
            status_code = response.status_code
            response.raise_for_status()
        async with factory() as db:
            finalized = await db.execute(
                update(IntegrationDelivery)
                .where(
                    IntegrationDelivery.id == delivery_id,
                    IntegrationDelivery.claimed_until == claim_until,
                )
                .values(
                    status="Delivered",
                    attempts=attempts,
                    delivered_at=datetime.now(UTC),
                    provider_status_code=status_code,
                    claimed_until=None,
                    last_error=None,
                )
            )
            integration = await db.get(Integration, integration_id)
            if finalized.rowcount > 0 and integration is not None:
                integration.status = "synced"
                integration.last_synced = datetime.now(UTC)
                integration.last_error = None
            await db.commit()
        if finalized.rowcount == 0:
            logger.warning(
                "Integration provider accepted delivery after its claim was lost delivery_id=%s",
                delivery_id,
            )
            return "lost_claim"
        return "delivered"
    except Exception as exc:
        error_message = f"{provider} delivery failed: {type(exc).__name__}"
        terminal = attempts >= _INTEGRATION_MAX_ATTEMPTS
        next_attempt = None if terminal else now + timedelta(minutes=min(2**attempts, 60))
        async with factory() as db:
            released = await db.execute(
                update(IntegrationDelivery)
                .where(
                    IntegrationDelivery.id == delivery_id,
                    IntegrationDelivery.claimed_until == claim_until,
                )
                .values(
                    status="Failed" if terminal else "Retry",
                    attempts=attempts,
                    next_attempt_at=next_attempt,
                    provider_status_code=status_code,
                    claimed_until=None,
                    last_error=error_message,
                )
            )
            integration = await db.get(Integration, integration_id)
            if released.rowcount > 0 and integration is not None:
                integration.status = "sync_failed" if terminal else "syncing"
                integration.last_error = error_message
            await db.commit()
        logger.warning(
            "Integration delivery failed delivery_id=%s provider=%s attempt=%s terminal=%s",
            delivery_id,
            provider,
            attempts,
            terminal,
        )
        return "failed"


@celery_app.task(name="app.workers.tasks.reconcile_provider_subscriptions", ignore_result=True)
def reconcile_provider_subscriptions():
    return asyncio.run(_reconcile_provider_subscriptions())


async def _reconcile_provider_subscriptions():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import settings
    from app.repositories.organization_repository import OrganizationRepository
    from app.services.subscription_billing_service import SubscriptionBillingService

    engine = create_async_engine(settings.DATABASE_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    repository = OrganizationRepository()
    service = SubscriptionBillingService(repository=repository)
    checked = 0
    changed = 0
    failed = 0
    cursor = None
    try:
        while True:
            async with factory() as db:
                organization_ids = await repository.list_provider_subscription_org_ids(
                    db, after_org_id=cursor, limit=200
                )
            if not organization_ids:
                break
            for organization_id in organization_ids:
                try:
                    async with factory() as db:
                        changed += int(
                            await service.reconcile_subscription(
                                db, organization_id=organization_id
                            )
                        )
                except Exception:
                    failed += 1
                    logger.exception(
                        "Subscription reconciliation failed organization=%s",
                        organization_id,
                    )
                checked += 1
            cursor = organization_ids[-1]
        logger.info(
            "Subscription reconciliation completed checked=%s changed=%s failed=%s",
            checked,
            changed,
            failed,
        )
        return {"checked": checked, "changed": changed, "failed": failed}
    finally:
        await engine.dispose()


@celery_app.task(name="app.workers.tasks.reconcile_invoice_payment_aggregates", ignore_result=True)
def reconcile_invoice_payment_aggregates():
    return asyncio.run(_reconcile_invoice_payment_aggregates())


async def _reconcile_invoice_payment_aggregates():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import settings
    from app.repositories.payment_repository import PaymentRepository
    from app.services.payment_service import PaymentService

    engine = create_async_engine(settings.DATABASE_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    repository = PaymentRepository()
    service = PaymentService(repository)
    checked = 0
    repaired = 0
    cursor = None
    try:
        while True:
            async with factory() as db:
                rows = await repository.list_invoice_ids_for_reconciliation(
                    db, after_id=cursor, limit=200
                )
            if not rows:
                break
            for invoice_id, organization_id in rows:
                async with factory() as db:
                    repaired += int(
                        await service.reconcile_invoice(
                            db,
                            invoice_id=invoice_id,
                            organization_id=organization_id,
                        )
                    )
                checked += 1
            cursor = rows[-1][0]
        logger.info(
            "Invoice payment reconciliation completed checked=%s repaired=%s",
            checked,
            repaired,
        )
        return {"checked": checked, "repaired": repaired}
    finally:
        await engine.dispose()


@celery_app.task(name="app.workers.tasks.deliver_pending_emails", ignore_result=True)
def deliver_pending_emails():
    return asyncio.run(_deliver_pending_emails())


async def _deliver_pending_emails():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import settings
    from app.services.email_domain_service import email_domain_service

    engine = create_async_engine(settings.DATABASE_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    count = 0
    try:
        for _ in range(20):
            if not await email_domain_service.deliver_one(factory):
                break
            count += 1
        logger.info("Email outbox sweep completed processed=%s", count)
        return count
    finally:
        await engine.dispose()


@celery_app.task(name="app.workers.tasks.deliver_pending_quotes", ignore_result=True)
def deliver_pending_quotes():
    return asyncio.run(_deliver_pending_quotes())


async def _deliver_pending_quotes():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import settings
    from app.services.quote_delivery_service import quote_delivery_service

    # Celery invokes a fresh event loop per task; do not reuse another loop's pool.
    engine = create_async_engine(settings.DATABASE_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    count = 0
    try:
        for _ in range(10):
            if not await quote_delivery_service.deliver_one(factory):
                break
            count += 1
        logger.info("Quote delivery sweep completed processed=%s", count)
        return count
    finally:
        await engine.dispose()


@celery_app.task(name="app.workers.tasks.deliver_pending_invoices", ignore_result=True)
def deliver_pending_invoices():
    return asyncio.run(_deliver_pending_invoices())


async def _deliver_pending_invoices():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import settings
    from app.services.invoice_delivery_service import invoice_delivery_service

    engine = create_async_engine(settings.DATABASE_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    count = 0
    try:
        for _ in range(10):
            if not await invoice_delivery_service.deliver_one(factory):
                break
            count += 1
        return count
    finally:
        await engine.dispose()


@celery_app.task(name="app.workers.tasks.deliver_pending_payment_receipts", ignore_result=True)
def deliver_pending_payment_receipts():
    return asyncio.run(_deliver_pending_payment_receipts())


async def _deliver_pending_payment_receipts():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import settings
    from app.services.invoice_delivery_service import invoice_delivery_service

    engine = create_async_engine(settings.DATABASE_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    count = 0
    try:
        for _ in range(10):
            if not await invoice_delivery_service.deliver_receipt_one(factory):
                break
            count += 1
        return count
    finally:
        await engine.dispose()


@celery_app.task(name="app.workers.tasks.send_due_invoice_reminders", ignore_result=True)
def send_due_invoice_reminders():
    return asyncio.run(_send_due_invoice_reminders())


async def _send_due_invoice_reminders():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import settings
    from app.core.errors import APIException
    from app.repositories.invoice_repository import invoice_repository
    from app.services.invoice_delivery_service import invoice_delivery_service

    engine = create_async_engine(settings.DATABASE_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    sent = 0
    failed = 0
    try:
        async with factory() as db:
            candidates = await invoice_repository.list_due_reminder_candidates(
                db, now=datetime.now(UTC)
            )
        for invoice_id, organization_id in candidates:
            async with factory() as db:
                try:
                    await invoice_delivery_service.send_reminder(
                        db,
                        invoice_id=invoice_id,
                        organization_id=organization_id,
                    )
                    sent += 1
                except APIException:
                    failed += 1
        return {"sent": sent, "failed": failed}
    finally:
        await engine.dispose()


logger = get_logger(__name__)

# Scheduled download links must comfortably outlive the hourly delivery
# sweep (MinIO/S3 allows up to 7 days).
_SCHEDULED_LINK_EXPIRY_SECONDS = 86400

# How long a worker's claim on a schedule stays valid. Sized against the
# worst case for delivering ONE schedule: tenant report generation (large
# CSVs, minutes) + S3 upload of that CSV (multipart, ~1 min for 100 MB) +
# one Brevo API call (30 s client timeout). A single schedule is claimed
# immediately before it is processed and finalized right after, so 30 min
# is >5x headroom on the slowest realistic step while capping how long a
# crashed worker can stall a schedule (it becomes claimable again once
# ``claimed_until`` passes, i.e. at most one sweep later).
_CLAIM_TTL = timedelta(minutes=30)


@celery_app.task(ignore_result=True)
def deliver_due_scheduled_reports():
    """Generate, email, and mark-delivered every scheduled report that is due.

    Runs hourly via celery beat using a claim/process/finalize pattern so
    concurrent sweeps can never double-deliver:

      Phase A (short txn): pick due, unclaimed schedule ids with
        ``FOR UPDATE SKIP LOCKED`` and commit immediately.
      Phase B (lock-free): atomically claim one schedule by stamping
        ``claimed_until``, then generate the CSV, upload to S3 and email
        the presigned link with NO database locks held.
      Phase C (short txn): advance ``next_run`` only when the update still
        matches this worker's exact claim token; on any failure just clear
        the claim so the next sweep retries naturally.
      Lost-claim reconcile: if Phase C matches zero rows the email has
        already been sent — the schedule MUST NOT stay due or the next
        sweep would email it again. A second update, guarded on "no live
        claim held" (never on our stale token), advances ``next_run`` and
        clears the claim. If another worker actively holds the claim we
        leave its state untouched and report ``lost_claim``.

    Delivery semantics are AT-LEAST-ONCE, not exactly-once: if delivery
    succeeds at the provider but the claim is lost to a worker that then
    delivers the same schedule *before* our reconcile runs, a duplicate
    email is possible. Exactly-once would require a per-(schedule, run)
    delivery record written transactionally with the send — a follow-up.

    There is intentionally NO Celery-level retry on this task: the hourly
    beat schedule plus per-schedule claim-clearing already provides retry-
    until-success semantics, and stacking a second retry mechanism would
    risk duplicate emails. Note: a permanently failing recipient/provider
    rejection currently retries once per sweep indefinitely; dead-letter
    handling (failure counters / schedule disabling) is a follow-up that
    needs schema support and provider error classification.
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
        return {"delivered": 0, "failed": 0, "lost_claim": 0, "skipped_unconfigured": True}

    now = datetime.now(UTC)

    # --- Phase A: collect due, unclaimed ids under a very short lock ---
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(ScheduledReport.id)
            .where(
                ScheduledReport.next_run.is_not(None),
                ScheduledReport.next_run <= now,
                (ScheduledReport.claimed_until.is_(None)) | (ScheduledReport.claimed_until < now),
            )
            .order_by(ScheduledReport.next_run.asc())
            .with_for_update(skip_locked=True)
        )
        due_ids = [row[0] for row in res.all()]
    # Session closed above -> row locks released before any network work.

    delivered = 0
    failed = 0
    lost_claim = 0
    for sched_id in due_ids:
        outcome = await _deliver_one(
            db_factory=AsyncSessionLocal,
            sched_id=sched_id,
            build_csv=report_service.build_report_csv_for_organization,
            upload=s3_service.upload_file,
            presign=s3_service.generate_presigned_url,
            send_email=send_email_via_brevo,
            compute_next=compute_next_run,
        )
        if outcome == "delivered":
            delivered += 1
        elif outcome == "failed":
            failed += 1
        elif outcome == "lost_claim":
            lost_claim += 1
        # "skipped" (claimed by another worker) counts as neither.

    logger.info(
        "Scheduled report delivery finished: delivered=%s failed=%s lost_claim=%s",
        delivered,
        failed,
        lost_claim,
    )
    return {"delivered": delivered, "failed": failed, "lost_claim": lost_claim}


def _claimable_condition(now: datetime):
    """WHERE fragment matching schedules this worker may claim."""
    from app.models.report import ScheduledReport

    return (ScheduledReport.claimed_until.is_(None)) | (ScheduledReport.claimed_until < now)


async def _deliver_one(
    *,
    db_factory,
    sched_id: str,
    build_csv,
    upload,
    presign,
    send_email,
    compute_next,
) -> str:
    """Claim, process, and finalize a single schedule.

    Returns "delivered", "skipped" (claim already held elsewhere),
    "failed" (delivery error; claim released for the next sweep), or
    "lost_claim" (email was sent but our claim token was gone before
    finalization — ``next_run`` is advanced by a reconcile guarded on no
    live claim, so the next sweep cannot re-send).

    Every claim/lease calculation uses a fresh ``datetime.now(UTC)``
    captured HERE, per schedule — never the stale sweep-level timestamp,
    which would shrink the effective lease (and skew the next_run base)
    for schedules processed late in a slow sweep.
    """
    from app.models.report import ScheduledReport

    # --- Phase B1: atomic claim (single UPDATE, no gap for another worker) ---
    now = datetime.now(UTC)
    claim_until = now + _CLAIM_TTL
    async with db_factory() as db:
        res = await db.execute(
            update(ScheduledReport)
            .where(
                ScheduledReport.id == sched_id,
                ScheduledReport.next_run.is_not(None),
                ScheduledReport.next_run <= now,
                _claimable_condition(now),
            )
            .values(claimed_until=claim_until)
            .returning(
                ScheduledReport.id,
                ScheduledReport.organization_id,
                ScheduledReport.report_type,
                ScheduledReport.email,
                ScheduledReport.frequency,
                ScheduledReport.next_run,
            )
        )
        row = res.first()
        await db.commit()

    if row is None:
        # Another sweep claimed it between Phase A and now — skip silently.
        logger.info("Schedule %s already claimed elsewhere; skipping", sched_id)
        return "skipped"

    (
        _sid,
        sched_org,
        sched_type,
        sched_email,
        sched_frequency,
        current_next,
    ) = tuple(row)
    # The exact claim token written above; finalization is only allowed to
    # touch the row while this token is still present.
    claim_token = claim_until

    s3_key: str | None = None
    try:
        # --- Phase B2: all slow/network work happens with zero DB locks ---
        async with db_factory() as db:
            csv_text = await build_csv(db, sched_org, sched_type)

        timestamp = now.strftime("%Y%m%dT%H%M%SZ")
        object_name = f"exports/scheduled/{sched_id}/{timestamp}.csv"
        s3_key = await asyncio.to_thread(
            upload,
            io.BytesIO(csv_text.encode("utf-8")),
            object_name=object_name,
            content_type="text/csv",
        )
        download_url = await asyncio.to_thread(
            presign, s3_key, expiration_seconds=_SCHEDULED_LINK_EXPIRY_SECONDS
        )

        sent = await asyncio.to_thread(
            send_email,
            to_email=sched_email,
            subject=f"Scheduled report: {sched_type}",
            html_content=(
                f"<p>Your scheduled <strong>{html.escape(str(sched_type), quote=True)}</strong> "
                f"report is ready.</p>"
                f'<p><a href="{html.escape(download_url, quote=True)}">Download the CSV</a> '
                f"(link valid for 24 hours).</p>"
            ),
        )
        if not sent:
            # The sender already logged the provider-side failure.
            raise RuntimeError("email delivery failed")

        # --- Phase C: finalize success, guarded by the exact claim token.
        # If the claim expired and another worker re-claimed/advanced the
        # schedule meanwhile, this matches zero rows and we must NOT
        # overwrite the newer worker's state.
        base = max(now, current_next) if isinstance(current_next, datetime) else now
        async with db_factory() as db:
            res = await db.execute(
                update(ScheduledReport)
                .where(
                    ScheduledReport.id == sched_id,
                    ScheduledReport.claimed_until == claim_token,
                )
                .values(next_run=compute_next(sched_frequency, base), claimed_until=None)
            )
            await db.commit()
        if res.rowcount == 0:
            # The email WAS sent but our exact claim token is gone (claim
            # expired + re-claimed elsewhere, or cleared by a crash/retry).
            # Leaving next_run untouched would make the next sweep deliver
            # the same report again, so attempt a reconcile — but ONLY when
            # no other worker holds a live claim (never overwrite an active
            # claim; that worker owns the schedule's state now).
            reconcile_time = datetime.now(UTC)
            async with db_factory() as db:
                rec = await db.execute(
                    update(ScheduledReport)
                    .where(
                        ScheduledReport.id == sched_id,
                        ScheduledReport.next_run == current_next,
                        _claimable_condition(reconcile_time),
                    )
                    .values(next_run=compute_next(sched_frequency, base), claimed_until=None)
                )
                await db.commit()
            if rec.rowcount > 0:
                logger.warning(
                    "Delivered schedule %s after losing its claim; reconciled "
                    "next_run so it will not be delivered twice",
                    sched_id,
                )
                return "lost_claim"
            logger.error(
                "Delivered schedule %s but another worker holds a live claim; "
                "leaving its state untouched (duplicate email possible)",
                sched_id,
            )
            return "lost_claim"
        return "delivered"

    except Exception:
        logger.exception(
            "Failed to deliver scheduled report id=%s org=%s type=%s",
            sched_id,
            sched_org,
            sched_type,
        )
        # Best-effort orphan prevention: remove the CSV we uploaded for a
        # delivery that never happened so failed sends don't accumulate
        # objects in the bucket.
        if s3_key is not None:
            try:
                await asyncio.to_thread(_delete_object_quietly, s3_key)
            except Exception:
                logger.warning("Could not clean up orphaned object %s", s3_key)
        # Release the claim (guarded by the token again) so the schedule is
        # retried by the next sweep. next_run is deliberately left unchanged.
        try:
            async with db_factory() as db:
                await db.execute(
                    update(ScheduledReport)
                    .where(
                        ScheduledReport.id == sched_id,
                        ScheduledReport.claimed_until == claim_token,
                    )
                    .values(claimed_until=None)
                )
                await db.commit()
        except Exception:
            # The stale claim will expire on its own after _CLAIM_TTL.
            logger.exception("Failed to release claim for schedule %s", sched_id)
        return "failed"


def _delete_object_quietly(s3_key: str) -> None:
    from app.services.s3_service import s3_service

    s3_service.delete_file(s3_key)


@celery_app.task(name="app.workers.tasks.process_workflow_events", ignore_result=True)
def process_workflow_events():
    return asyncio.run(_process_workflow_events())


async def _process_workflow_events() -> dict[str, int]:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import settings
    from app.repositories.workflow_repository import workflow_repository
    from app.services.workflow_service import workflow_service

    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    processed = 0
    try:
        async with factory() as db:
            event_ids = [item.id for item in await workflow_repository.pending_events(db)]
        for event_id in event_ids:
            async with factory() as db:
                event = await workflow_repository.claim_event(db, event_id)
                if not event:
                    continue
                try:
                    await workflow_service.process_event(db, event)
                    processed += 1
                except Exception as exc:
                    await db.rollback()
                    await workflow_repository.retry_event(db, event_id, type(exc).__name__)
        return {"processed": processed}
    finally:
        await engine.dispose()
