"""Tenant-scoped, grace-period protected object-storage reconciliation."""

import asyncio
import logging
import re
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.repositories.organization_lifecycle_repository import OrganizationLifecycleRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.storage_reconciliation_repository import (
    StorageClaim,
    StorageFindingReference,
    StorageReconciliationRepository,
)
from app.services.organization_lifecycle_service import storage_key, storage_prefixes
from app.services.s3_service import s3_service

logger = logging.getLogger(__name__)

ORPHAN_GRACE_PERIOD = timedelta(hours=24)
CLAIM_LEASE = timedelta(minutes=10)
RESOLVED_RETENTION = timedelta(days=30)
MAX_DELETE_ATTEMPTS = 5
MAX_OBJECTS_PER_ORGANIZATION = 10_000
MAX_PREFIXES_PER_ORGANIZATION = 10_000
ORGANIZATION_BATCH_SIZE = 200
MAX_FINDINGS_PER_ORGANIZATION = MAX_OBJECTS_PER_ORGANIZATION * 2
MAX_DELETE_OPERATIONS_PER_ORGANIZATION = 100


def classify_storage(
    referenced_keys: set[str], inventory_keys: set[str]
) -> tuple[set[str], set[str]]:
    """Return (orphaned_objects, missing_references) deterministically."""
    return inventory_keys - referenced_keys, referenced_keys - inventory_keys


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def _owned_references(
    db: AsyncSession,
    organization_id: str,
    lifecycle_repository: OrganizationLifecycleRepository,
) -> set[str]:
    references: set[str] = set()
    async for _, value, kind in lifecycle_repository.storage_references(
        db, organization_id, owned_only=True
    ):
        key = storage_key(value, kind)
        if key is None:
            raise ValueError("Tenant storage contains an invalid or external reference")
        references.add(key)
        if len(references) > MAX_OBJECTS_PER_ORGANIZATION:
            raise ValueError("Tenant storage reference inventory exceeds the online limit")
    return references


async def _owned_prefixes(
    db: AsyncSession,
    organization_id: str,
    lifecycle_repository: OrganizationLifecycleRepository,
) -> list[str]:
    owned_prefixes: set[str] = set()
    async for kind, identifier in lifecycle_repository.storage_prefix_owners(db, organization_id):
        owned_prefixes.update(storage_prefixes(kind, identifier))
        if len(owned_prefixes) > MAX_PREFIXES_PER_ORGANIZATION:
            raise ValueError("Tenant storage prefix inventory exceeds the online limit")
    prefixes: list[str] = []
    for prefix in sorted(owned_prefixes):
        if not prefixes or not prefix.startswith(prefixes[-1]):
            prefixes.append(prefix)
    if await lifecycle_repository.storage_prefix_conflict(db, organization_id, prefixes):
        raise ValueError("Tenant storage prefixes overlap another organization")
    return prefixes


async def _inventory_for_prefixes(prefixes: list[str]) -> set[str]:
    inventory: set[str] = set()
    for prefix in prefixes:
        remaining = MAX_OBJECTS_PER_ORGANIZATION - len(inventory)
        new_keys = await asyncio.to_thread(s3_service.list_file_keys, prefix, remaining, inventory)
        if any(not key.startswith(prefix) or storage_key(key, "key") != key for key in new_keys):
            raise ValueError("Tenant storage inventory contains an invalid object key")
        inventory.update(new_keys)
        if len(inventory) > MAX_OBJECTS_PER_ORGANIZATION:
            raise ValueError("Tenant storage inventory exceeds the online deletion limit")
    return inventory


def _percent_encoded_character(character: str) -> str:
    encoded = []
    for value in character.encode("utf-8"):
        digits = f"{value:02X}"
        encoded.append(
            "%"
            + "".join(f"[{digit.lower()}{digit}]" if digit.isalpha() else digit for digit in digits)
        )
    return "".join(encoded)


def _object_url_pattern(object_key: str) -> str:
    """Match every URL spelling that ``storage_key`` resolves to this key.

    The raw-percent alternative can conservatively retain an object for an
    ambiguous malformed escape, but the expression must never miss a valid
    stored reference before deletion.
    """
    endpoint = urlsplit(settings.AWS_ENDPOINT_URL)
    key_pattern = "".join(
        (
            _percent_encoded_character(character)
            if character in {"?", "#"}
            else f"(?:{re.escape(character)}|{_percent_encoded_character(character)})"
        )
        for character in object_key
    )
    return (
        rf"^[hH][tT][tT][pP][sS]?://{re.escape(endpoint.netloc)}/"
        rf"{re.escape(settings.AWS_S3_BUCKET)}/{key_pattern}(?:[?#].*)?$"
    )


async def _reference_exists(
    db: AsyncSession,
    object_key: str,
    lifecycle_repository: OrganizationLifecycleRepository,
) -> bool:
    return await lifecycle_repository.storage_reference_exists(
        db, object_key=object_key, object_url_pattern=_object_url_pattern(object_key)
    )


async def _refresh_findings(
    db: AsyncSession,
    organization_id: str,
    findings: set[tuple[str, str]],
    now: datetime,
    repository: StorageReconciliationRepository,
) -> list[StorageFindingReference]:
    await repository.prune_resolved(db, organization_id, before=now - RESOLVED_RETENTION)
    await repository.insert_findings(
        db,
        organization_id=organization_id,
        findings=findings,
        bucket=settings.AWS_S3_BUCKET,
        endpoint=settings.AWS_ENDPOINT_URL,
        now=now,
    )
    await repository.synchronize_findings(
        db,
        organization_id,
        findings,
        now=now,
        max_attempts=MAX_DELETE_ATTEMPTS,
    )
    if await repository.count_active(db, organization_id) > MAX_FINDINGS_PER_ORGANIZATION:
        raise ValueError("Tenant reconciliation findings exceed the online limit")
    claimable = await repository.list_claimable_orphans(
        db,
        organization_id,
        eligible_before=now - ORPHAN_GRACE_PERIOD,
        now=now,
        max_attempts=MAX_DELETE_ATTEMPTS,
        limit=MAX_DELETE_OPERATIONS_PER_ORGANIZATION,
    )
    await db.commit()
    return claimable


async def _finish_failure(
    db: AsyncSession,
    claim: StorageClaim,
    now: datetime,
    error: str,
    repository: StorageReconciliationRepository,
) -> bool:
    status = "terminal" if claim.attempts >= MAX_DELETE_ATTEMPTS else "failed"
    finalized = await repository.finish_claim(db, claim=claim, status=status, now=now, error=error)
    if not finalized:
        await db.rollback()
        logger.warning(
            "Storage reconciliation claim ownership changed before failure finalization "
            "organization_id=%s finding_id=%s",
            claim.organization_id,
            claim.id,
        )
        return False
    await db.commit()
    return True


async def reconcile_organization_storage(
    db: AsyncSession, organization_id: str, *, now: datetime | None = None
) -> dict[str, int]:
    now = now or _utcnow()
    lifecycle_repository = OrganizationLifecycleRepository()
    organization_repository = OrganizationRepository()
    reconciliation_repository = StorageReconciliationRepository()
    references = await _owned_references(db, organization_id, lifecycle_repository)
    prefixes = await _owned_prefixes(db, organization_id, lifecycle_repository)
    inventory = await _inventory_for_prefixes(prefixes)
    orphaned, missing = classify_storage(references, inventory)
    findings = {("orphan", key) for key in orphaned} | {("missing", key) for key in missing}
    claimable = await _refresh_findings(
        db, organization_id, findings, now, reconciliation_repository
    )
    claimable_count = await reconciliation_repository.count_claimable_orphans(
        db,
        organization_id,
        eligible_before=now - ORPHAN_GRACE_PERIOD,
        now=now,
        max_attempts=MAX_DELETE_ATTEMPTS,
    )
    deferred = max(0, claimable_count - len(claimable))
    if deferred:
        logger.warning(
            "Storage reconciliation deferred bounded work organization_id=%s deferred=%s",
            organization_id,
            deferred,
        )

    deleted = 0
    failed = 0
    for candidate in claimable:
        object_key = candidate.object_key
        claim_now = _utcnow()
        claimed = await reconciliation_repository.claim_orphan(
            db,
            finding_id=candidate.id,
            eligible_before=now - ORPHAN_GRACE_PERIOD,
            now=claim_now,
            claimed_until=claim_now + CLAIM_LEASE,
            max_attempts=MAX_DELETE_ATTEMPTS,
        )
        await db.commit()
        if claimed is None:
            continue
        if (
            claimed.endpoint != settings.AWS_ENDPOINT_URL
            or claimed.bucket != settings.AWS_S3_BUCKET
        ):
            await _finish_failure(
                db,
                claimed,
                claim_now,
                "STORAGE_CONFIGURATION_CHANGED",
                reconciliation_repository,
            )
            failed += 1
            continue
        try:
            # Writers hold KEY SHARE until metadata commits. FOR UPDATE closes
            # the final reference-check/delete race for this organization.
            organization = await organization_repository.get_by_id_for_update(db, organization_id)
            if organization is None:
                raise RuntimeError("ORGANIZATION_NOT_FOUND")
            if not await reconciliation_repository.lock_claim(
                db,
                finding_id=claimed.id,
                claim_token=claimed.claim_token,
                now=_utcnow(),
            ):
                await db.rollback()
                continue
            if await lifecycle_repository.storage_key_prefix_conflict(
                db, organization_id, object_key
            ):
                raise RuntimeError("STORAGE_PREFIX_CONFLICT")
            if await _reference_exists(db, object_key, lifecycle_repository):
                finalized = await reconciliation_repository.finish_claim(
                    db, claim=claimed, status="resolved", now=_utcnow(), error=None
                )
                if not finalized:
                    raise RuntimeError("STORAGE_CLAIM_LOST")
                await db.commit()
                continue
            if not await asyncio.to_thread(s3_service.delete_file, object_key):
                raise RuntimeError("STORAGE_DELETE_FAILED")
            finalized = await reconciliation_repository.finish_claim(
                db,
                claim=claimed,
                status="resolved",
                now=_utcnow(),
                error=None,
                audit_action="storage.reconciliation.orphan_deleted",
            )
            await db.commit()
            deleted += int(finalized)
        except Exception as exc:
            await db.rollback()
            error = str(exc) if str(exc).isupper() else type(exc).__name__
            await _finish_failure(db, claimed, _utcnow(), error, reconciliation_repository)
            failed += 1
    return {
        "orphaned": len(orphaned),
        "missing": len(missing),
        "deleted": deleted,
        "failed": failed,
        "deferred": deferred,
    }


async def reconcile_all_organizations(db: AsyncSession) -> dict[str, int]:
    organization_repository = OrganizationRepository()
    totals = {
        "organizations": 0,
        "orphaned": 0,
        "missing": 0,
        "deleted": 0,
        "failed": 0,
        "deferred": 0,
    }
    cursor: str | None = None
    while True:
        organization_ids = await organization_repository.list_ids_for_reconciliation(
            db, after_id=cursor, limit=ORGANIZATION_BATCH_SIZE
        )
        if not organization_ids:
            break
        for organization_id in organization_ids:
            totals["organizations"] += 1
            try:
                result = await reconcile_organization_storage(db, organization_id)
            except Exception:
                await db.rollback()
                totals["failed"] += 1
                logger.exception(
                    "Storage reconciliation failed organization_id=%s", organization_id
                )
                continue
            for key in ("orphaned", "missing", "deleted", "failed", "deferred"):
                totals[key] += result[key]
        cursor = organization_ids[-1]
    return totals
