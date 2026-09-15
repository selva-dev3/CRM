"""Tenant-scoped, grace-period protected object-storage reconciliation."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import AuditLog, Organization, StorageReconciliation
from app.repositories.organization_lifecycle_repository import OrganizationLifecycleRepository
from app.services.organization_lifecycle_service import storage_key, storage_prefixes
from app.services.s3_service import s3_service

logger = logging.getLogger(__name__)

ORPHAN_GRACE_PERIOD = timedelta(hours=24)
MAX_OBJECTS_PER_PREFIX = 10_000


def classify_storage(
    referenced_keys: set[str], inventory_keys: set[str]
) -> tuple[set[str], set[str]]:
    """Return (orphaned_objects, missing_references) deterministically."""
    return inventory_keys - referenced_keys, referenced_keys - inventory_keys


async def reconcile_organization_storage(
    db: AsyncSession, organization_id: str, *, now: datetime | None = None
) -> dict[str, int]:
    now = now or datetime.now(UTC)
    repository = OrganizationLifecycleRepository()
    references: set[str] = set()
    async for _, value, kind in repository.storage_references(db, organization_id, owned_only=True):
        key = storage_key(value, kind)
        if key:
            references.add(key)

    inventory: set[str] = set()
    async for kind, identifier in repository.storage_prefix_owners(db, organization_id):
        for prefix in storage_prefixes(kind, identifier):
            inventory.update(
                await asyncio.to_thread(
                    s3_service.list_file_keys,
                    prefix,
                    MAX_OBJECTS_PER_PREFIX,
                    None,
                )
            )

    orphaned, missing = classify_storage(references, inventory)
    findings = {("orphan", key) for key in orphaned} | {("missing", key) for key in missing}
    existing = {
        (row.finding, row.object_key): row
        for row in await db.scalars(
            select(StorageReconciliation).where(
                StorageReconciliation.organization_id == organization_id
            )
        )
    }
    deleted = 0
    failed = 0
    for finding, key in sorted(findings):
        row = existing.get((finding, key))
        if row is None:
            row = StorageReconciliation(
                organization_id=organization_id,
                object_key=key,
                bucket=settings.AWS_S3_BUCKET,
                endpoint=settings.AWS_ENDPOINT_URL,
                finding=finding,
                status="detected",
                first_seen_at=now,
                last_seen_at=now,
            )
            db.add(row)
            existing[(finding, key)] = row
        else:
            row.last_seen_at = now
            row.resolved_at = None
            row.status = "detected"

        if finding != "orphan" or now - row.first_seen_at < ORPHAN_GRACE_PERIOD:
            continue
        if row.endpoint != settings.AWS_ENDPOINT_URL or row.bucket != settings.AWS_S3_BUCKET:
            row.status = "failed"
            row.last_error = "STORAGE_CONFIGURATION_CHANGED"
            failed += 1
            continue
        row.attempts = (row.attempts or 0) + 1
        try:
            deleted_ok = await asyncio.to_thread(s3_service.delete_file, key)
            if not deleted_ok:
                raise RuntimeError("storage delete returned false")
        except Exception as exc:
            row.status = "failed"
            row.last_error = type(exc).__name__
            failed += 1
            continue
        row.status = "resolved"
        row.resolved_at = now
        row.last_error = None
        db.add(
            AuditLog(
                organization_id=organization_id,
                action="storage.reconciliation.orphan_deleted",
                details=f"Deleted orphaned object after grace period: {key}",
            )
        )
        deleted += 1

    for reconciliation_key, row in existing.items():
        if (
            reconciliation_key[0] not in {"orphan", "missing"}
            or reconciliation_key in findings
            or row.status == "resolved"
        ):
            continue
        row.status = "resolved"
        row.resolved_at = now

    await db.commit()
    return {
        "orphaned": len(orphaned),
        "missing": len(missing),
        "deleted": deleted,
        "failed": failed,
    }


async def reconcile_all_organizations(db: AsyncSession) -> dict[str, int]:
    totals = {"organizations": 0, "orphaned": 0, "missing": 0, "deleted": 0, "failed": 0}
    for organization_id in await db.scalars(select(Organization.id).order_by(Organization.id)):
        result = await reconcile_organization_storage(db, organization_id)
        totals["organizations"] += 1
        for key in ("orphaned", "missing", "deleted", "failed"):
            totals[key] += result[key]
        if result["failed"]:
            logger.error(
                "Storage reconciliation failed organization_id=%s count=%s",
                organization_id,
                result["failed"],
            )
    return totals
