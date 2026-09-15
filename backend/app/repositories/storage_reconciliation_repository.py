"""Persistence operations for durable object-storage reconciliation."""

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from sqlalchemy import String, column, delete, exists, func, or_, select, table, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, StorageReconciliation

FINDING_BATCH_SIZE = 500
CURRENT_FINDINGS_TABLE = table(
    "storage_reconciliation_current_findings",
    column("finding", String(32)),
    column("object_key", String(1024)),
)


@dataclass(frozen=True)
class StorageFindingReference:
    """Immutable identity used after refresh commits expire ORM state."""

    id: str
    object_key: str
    first_seen_at: datetime


@dataclass(frozen=True)
class StorageClaim:
    """Immutable claim data safe to retain across commit and rollback."""

    id: str
    organization_id: str
    object_key: str
    bucket: str
    endpoint: str
    attempts: int
    claim_token: str


class StorageReconciliationRepository:
    async def insert_findings(
        self,
        db: AsyncSession,
        *,
        organization_id: str,
        findings: set[tuple[str, str]],
        bucket: str,
        endpoint: str,
        now: datetime,
    ) -> None:
        values = [
            {
                "organization_id": organization_id,
                "object_key": object_key,
                "bucket": bucket,
                "endpoint": endpoint,
                "finding": finding,
                "status": "detected",
                "attempts": 0,
                "first_seen_at": now,
                "last_seen_at": now,
            }
            for finding, object_key in sorted(findings)
        ]
        for offset in range(0, len(values), FINDING_BATCH_SIZE):
            statement = (
                insert(StorageReconciliation)
                .values(values[offset : offset + FINDING_BATCH_SIZE])
                .on_conflict_do_nothing(constraint="uq_storage_reconciliation")
            )
            await db.execute(statement)

    async def synchronize_findings(
        self,
        db: AsyncSession,
        organization_id: str,
        findings: set[tuple[str, str]],
        *,
        now: datetime,
        max_attempts: int,
    ) -> None:
        """Atomically reconcile persisted state without overwriting live claims."""
        await db.execute(text("""
                CREATE TEMPORARY TABLE IF NOT EXISTS storage_reconciliation_current_findings (
                    finding VARCHAR(32) NOT NULL,
                    object_key VARCHAR(1024) NOT NULL,
                    PRIMARY KEY (finding, object_key)
                ) ON COMMIT DELETE ROWS
                """))
        await db.execute(delete(CURRENT_FINDINGS_TABLE))
        pairs = sorted(findings)
        for offset in range(0, len(pairs), FINDING_BATCH_SIZE):
            await db.execute(
                CURRENT_FINDINGS_TABLE.insert(),
                [
                    {"finding": finding, "object_key": object_key}
                    for finding, object_key in pairs[offset : offset + FINDING_BATCH_SIZE]
                ],
            )
        present = exists(
            select(1)
            .select_from(CURRENT_FINDINGS_TABLE)
            .where(
                CURRENT_FINDINGS_TABLE.c.finding == StorageReconciliation.finding,
                CURRENT_FINDINGS_TABLE.c.object_key == StorageReconciliation.object_key,
            )
        )
        disappeared = [
            StorageReconciliation.organization_id == organization_id,
            StorageReconciliation.status != "resolved",
            or_(
                StorageReconciliation.status != "deleting",
                StorageReconciliation.claimed_until.is_(None),
                StorageReconciliation.claimed_until < now,
            ),
        ]
        if findings:
            disappeared.append(~present)
        await db.execute(
            update(StorageReconciliation)
            .where(*disappeared)
            .values(
                status="resolved",
                resolved_at=now,
                claimed_until=None,
                claim_token=None,
            )
        )
        if not findings:
            return

        # A resolved key that genuinely reappears receives a fresh grace period.
        await db.execute(
            update(StorageReconciliation)
            .where(
                StorageReconciliation.organization_id == organization_id,
                present,
                StorageReconciliation.status == "resolved",
            )
            .values(
                status="detected",
                attempts=0,
                first_seen_at=now,
                last_seen_at=now,
                resolved_at=None,
                claimed_until=None,
                claim_token=None,
                last_error=None,
            )
        )
        # Touch current findings only; never mutate live claim ownership here.
        await db.execute(
            update(StorageReconciliation)
            .where(
                StorageReconciliation.organization_id == organization_id,
                present,
                StorageReconciliation.status != "resolved",
            )
            .values(last_seen_at=now)
        )
        # A crash after the final claim becomes explicit terminal work instead
        # of an unclaimable row that misleadingly returns to detected.
        await db.execute(
            update(StorageReconciliation)
            .where(
                StorageReconciliation.organization_id == organization_id,
                present,
                StorageReconciliation.status == "deleting",
                StorageReconciliation.claimed_until < now,
                StorageReconciliation.attempts >= max_attempts,
            )
            .values(
                status="terminal",
                claimed_until=None,
                claim_token=None,
                last_error="STORAGE_DELETE_FINAL_CLAIM_EXPIRED",
            )
        )

    async def count_active(self, db: AsyncSession, organization_id: str) -> int:
        return int(
            await db.scalar(
                select(func.count())
                .select_from(StorageReconciliation)
                .where(
                    StorageReconciliation.organization_id == organization_id,
                    StorageReconciliation.status != "resolved",
                )
            )
            or 0
        )

    async def list_claimable_orphans(
        self,
        db: AsyncSession,
        organization_id: str,
        *,
        eligible_before: datetime,
        now: datetime,
        max_attempts: int,
        limit: int,
    ) -> list[StorageFindingReference]:
        rows = await db.execute(
            select(
                StorageReconciliation.id,
                StorageReconciliation.object_key,
                StorageReconciliation.first_seen_at,
            )
            .where(
                StorageReconciliation.organization_id == organization_id,
                StorageReconciliation.finding == "orphan",
                StorageReconciliation.first_seen_at <= eligible_before,
                StorageReconciliation.attempts < max_attempts,
                or_(
                    StorageReconciliation.status.in_(("detected", "failed")),
                    (
                        (StorageReconciliation.status == "deleting")
                        & (StorageReconciliation.claimed_until < now)
                    ),
                ),
            )
            .order_by(StorageReconciliation.first_seen_at, StorageReconciliation.id)
            .limit(limit)
        )
        return [StorageFindingReference(*row) for row in rows]

    async def count_claimable_orphans(
        self,
        db: AsyncSession,
        organization_id: str,
        *,
        eligible_before: datetime,
        now: datetime,
        max_attempts: int,
    ) -> int:
        return int(
            await db.scalar(
                select(func.count())
                .select_from(StorageReconciliation)
                .where(
                    StorageReconciliation.organization_id == organization_id,
                    StorageReconciliation.finding == "orphan",
                    StorageReconciliation.first_seen_at <= eligible_before,
                    StorageReconciliation.attempts < max_attempts,
                    or_(
                        StorageReconciliation.status.in_(("detected", "failed")),
                        (
                            (StorageReconciliation.status == "deleting")
                            & (StorageReconciliation.claimed_until < now)
                        ),
                    ),
                )
            )
            or 0
        )

    async def prune_resolved(
        self, db: AsyncSession, organization_id: str, *, before: datetime
    ) -> None:
        await db.execute(
            delete(StorageReconciliation).where(
                StorageReconciliation.organization_id == organization_id,
                StorageReconciliation.status == "resolved",
                StorageReconciliation.resolved_at < before,
            )
        )

    async def claim_orphan(
        self,
        db: AsyncSession,
        *,
        finding_id: str,
        eligible_before: datetime,
        now: datetime,
        claimed_until: datetime,
        max_attempts: int,
    ) -> StorageClaim | None:
        claim_token = str(uuid4())
        result = await db.execute(
            update(StorageReconciliation)
            .where(
                StorageReconciliation.id == finding_id,
                StorageReconciliation.finding == "orphan",
                StorageReconciliation.first_seen_at <= eligible_before,
                StorageReconciliation.attempts < max_attempts,
                or_(
                    StorageReconciliation.status.in_(("detected", "failed")),
                    (
                        (StorageReconciliation.status == "deleting")
                        & (StorageReconciliation.claimed_until <= now)
                    ),
                ),
            )
            .values(
                status="deleting",
                attempts=StorageReconciliation.attempts + 1,
                claimed_until=claimed_until,
                claim_token=claim_token,
            )
            .returning(
                StorageReconciliation.id,
                StorageReconciliation.organization_id,
                StorageReconciliation.object_key,
                StorageReconciliation.bucket,
                StorageReconciliation.endpoint,
                StorageReconciliation.attempts,
                StorageReconciliation.claim_token,
            )
        )
        row = result.one_or_none()
        return StorageClaim(*row) if row is not None else None

    async def lock_claim(
        self,
        db: AsyncSession,
        *,
        finding_id: str,
        claim_token: str,
        now: datetime,
    ) -> bool:
        return bool(
            await db.scalar(
                select(StorageReconciliation.id)
                .where(
                    StorageReconciliation.id == finding_id,
                    StorageReconciliation.status == "deleting",
                    StorageReconciliation.claim_token == claim_token,
                    StorageReconciliation.claimed_until >= now,
                )
                .with_for_update()
            )
        )

    async def finish_claim(
        self,
        db: AsyncSession,
        *,
        claim: StorageClaim,
        status: str,
        now: datetime,
        error: str | None,
        audit_action: str | None = None,
    ) -> bool:
        result = await db.execute(
            update(StorageReconciliation)
            .where(
                StorageReconciliation.id == claim.id,
                StorageReconciliation.claim_token == claim.claim_token,
            )
            .values(
                status=status,
                resolved_at=now if status == "resolved" else None,
                claimed_until=None,
                claim_token=None,
                last_error=error,
            )
            .returning(StorageReconciliation.id)
        )
        if result.scalar_one_or_none() is None:
            return False
        if audit_action:
            db.add(
                AuditLog(
                    organization_id=claim.organization_id,
                    action=audit_action,
                    details=f"Deleted reconciled object: {claim.object_key}",
                )
            )
        return True
