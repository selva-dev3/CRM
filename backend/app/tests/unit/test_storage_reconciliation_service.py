import re
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models import StorageReconciliation
from app.repositories.storage_reconciliation_repository import (
    StorageClaim,
    StorageFindingReference,
)
from app.services import storage_reconciliation_service as service_module
from app.services.storage_reconciliation_service import classify_storage


def test_classify_storage_reports_orphans_and_missing_references():
    orphaned, missing = classify_storage(
        {"documents/org-a/kept.pdf", "documents/org-a/missing.pdf"},
        {"documents/org-a/kept.pdf", "documents/org-a/orphan.pdf"},
    )
    assert orphaned == {"documents/org-a/orphan.pdf"}
    assert missing == {"documents/org-a/missing.pdf"}


@pytest.mark.parametrize(
    "path_suffix",
    [
        "documents/org-a/orphan.pdf#preview",
        "documents%2Forg-a%2Forphan.pdf?signature=test",
        "%64ocuments/org-a/orphan.pdf",
    ],
)
def test_reference_pattern_matches_every_supported_url_spelling(path_suffix):
    object_key = "documents/org-a/orphan.pdf"
    endpoint = service_module.urlsplit(service_module.settings.AWS_ENDPOINT_URL)
    scheme = "https" if endpoint.scheme == "http" else "http"
    value = f"{scheme}://{endpoint.netloc}/{service_module.settings.AWS_S3_BUCKET}/{path_suffix}"

    assert service_module.storage_key(value, "url") == object_key
    assert re.fullmatch(service_module._object_url_pattern(object_key), value)


class _LifecycleRepository:
    owned_references: list[tuple[bool, str, str]] = []
    all_references: list[tuple[bool, str, str]] = []
    prefix_conflict = False

    async def storage_references(self, db, organization_id, *, owned_only=None):
        rows = self.owned_references if owned_only is True else self.all_references
        for row in rows:
            yield row

    async def storage_prefix_owners(self, db, organization_id):
        yield "organization", organization_id

    async def storage_prefix_conflict(self, db, organization_id, prefixes):
        return self.prefix_conflict

    async def storage_key_prefix_conflict(self, db, organization_id, object_key):
        return self.prefix_conflict

    async def storage_reference_exists(self, db, *, object_key, object_url_pattern):
        return any(
            service_module.storage_key(value, kind) == object_key
            for _, value, kind in self.all_references
        )


class _OrganizationRepository:
    organization = SimpleNamespace(id="org-a")
    pages: list[list[str]] = []

    async def get_by_id_for_update(self, db, organization_id):
        return self.organization

    async def list_ids_for_reconciliation(self, db, *, after_id=None, limit=200):
        return self.pages.pop(0) if self.pages else []


class _FindingRepository:
    rows: dict[tuple[str, str], StorageReconciliation] = {}
    claim_windows: list[tuple[datetime, datetime]] = []

    async def prune_resolved(self, db, organization_id, *, before):
        return None

    async def insert_findings(self, db, *, organization_id, findings, bucket, endpoint, now):
        for finding, object_key in findings:
            self.rows.setdefault(
                (finding, object_key),
                StorageReconciliation(
                    id=f"{finding}:{object_key}",
                    organization_id=organization_id,
                    object_key=object_key,
                    bucket=bucket,
                    endpoint=endpoint,
                    finding=finding,
                    status="detected",
                    attempts=0,
                    first_seen_at=now,
                    last_seen_at=now,
                ),
            )

    async def synchronize_findings(self, db, organization_id, findings, *, now, max_attempts):
        for key, row in self.rows.items():
            if key not in findings:
                if row.status != "deleting" or not row.claimed_until or row.claimed_until < now:
                    row.status = "resolved"
                    row.resolved_at = now
                    row.claimed_until = None
                    row.claim_token = None
                continue
            if row.status == "resolved":
                row.status = "detected"
                row.attempts = 0
                row.first_seen_at = now
                row.resolved_at = None
                row.claimed_until = None
                row.claim_token = None
                row.last_error = None
            row.last_seen_at = now
            if (
                row.status == "deleting"
                and row.claimed_until
                and row.claimed_until < now
                and row.attempts >= max_attempts
            ):
                row.status = "terminal"
                row.claimed_until = None
                row.claim_token = None
                row.last_error = "STORAGE_DELETE_FINAL_CLAIM_EXPIRED"

    async def count_active(self, db, organization_id):
        return sum(row.status != "resolved" for row in self.rows.values())

    def _claimable(self, organization_id, eligible_before, now, max_attempts):
        return sorted(
            (
                row
                for row in self.rows.values()
                if row.organization_id == organization_id
                and row.finding == "orphan"
                and row.first_seen_at <= eligible_before
                and row.attempts < max_attempts
                and (
                    row.status in {"detected", "failed"}
                    or (row.status == "deleting" and row.claimed_until and row.claimed_until < now)
                )
            ),
            key=lambda row: (row.first_seen_at, row.id),
        )

    async def list_claimable_orphans(
        self, db, organization_id, *, eligible_before, now, max_attempts, limit
    ):
        return [
            StorageFindingReference(row.id, row.object_key, row.first_seen_at)
            for row in self._claimable(organization_id, eligible_before, now, max_attempts)[:limit]
        ]

    async def count_claimable_orphans(
        self, db, organization_id, *, eligible_before, now, max_attempts
    ):
        return len(self._claimable(organization_id, eligible_before, now, max_attempts))

    async def claim_orphan(
        self, db, *, finding_id, eligible_before, now, claimed_until, max_attempts
    ):
        row = next((item for item in self.rows.values() if item.id == finding_id), None)
        if (
            row is None
            or row.first_seen_at > eligible_before
            or row.attempts >= max_attempts
            or row.status == "terminal"
        ):
            return None
        row.status = "deleting"
        row.attempts += 1
        row.claimed_until = claimed_until
        row.claim_token = str(uuid4())
        self.claim_windows.append((now, claimed_until))
        return StorageClaim(
            row.id,
            row.organization_id,
            row.object_key,
            row.bucket,
            row.endpoint,
            row.attempts,
            row.claim_token,
        )

    async def lock_claim(self, db, *, finding_id, claim_token, now):
        row = next((item for item in self.rows.values() if item.id == finding_id), None)
        return bool(
            row
            and row.status == "deleting"
            and row.claim_token == claim_token
            and row.claimed_until
            and row.claimed_until >= now
        )

    async def finish_claim(self, db, *, claim, status, now, error, audit_action=None):
        finding = next((item for item in self.rows.values() if item.id == claim.id), None)
        if finding is None or finding.claim_token != claim.claim_token:
            return False
        finding.status = status
        finding.resolved_at = now if status == "resolved" else None
        finding.claimed_until = None
        finding.claim_token = None
        finding.last_error = error
        if audit_action:
            db.add(SimpleNamespace(action=audit_action))
        return True


def _db():
    return SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock(), add=MagicMock())


@pytest.fixture(autouse=True)
def repositories(monkeypatch):
    _LifecycleRepository.owned_references = []
    _LifecycleRepository.all_references = []
    _LifecycleRepository.prefix_conflict = False
    _OrganizationRepository.organization = SimpleNamespace(id="org-a")
    _OrganizationRepository.pages = []
    _FindingRepository.rows = {}
    _FindingRepository.claim_windows = []
    monkeypatch.setattr(service_module, "OrganizationLifecycleRepository", _LifecycleRepository)
    monkeypatch.setattr(service_module, "OrganizationRepository", _OrganizationRepository)
    monkeypatch.setattr(service_module, "StorageReconciliationRepository", _FindingRepository)
    monkeypatch.setattr(
        service_module.s3_service,
        "list_file_keys",
        lambda prefix, limit, known: (
            ["documents/org-a/orphan.pdf"] if prefix == "documents/org-a/" else []
        ),
    )


@pytest.mark.asyncio
async def test_reconcile_records_orphan_without_deleting_during_grace(monkeypatch):
    delete = MagicMock(return_value=True)
    monkeypatch.setattr(service_module.s3_service, "delete_file", delete)
    result = await service_module.reconcile_organization_storage(_db(), "org-a")
    assert result == {
        "orphaned": 1,
        "missing": 0,
        "deleted": 0,
        "failed": 0,
        "deferred": 0,
    }
    delete.assert_not_called()


@pytest.mark.asyncio
async def test_reconcile_records_missing_reference(monkeypatch):
    _LifecycleRepository.owned_references = [(True, "documents/org-a/missing.pdf", "key")]
    monkeypatch.setattr(
        service_module.s3_service, "list_file_keys", lambda prefix, limit, known: []
    )
    result = await service_module.reconcile_organization_storage(_db(), "org-a")
    assert result == {
        "orphaned": 0,
        "missing": 1,
        "deleted": 0,
        "failed": 0,
        "deferred": 0,
    }
    assert ("missing", "documents/org-a/missing.pdf") in _FindingRepository.rows


def _old_orphan(now: datetime, **overrides) -> StorageReconciliation:
    values = {
        "id": "finding",
        "organization_id": "org-a",
        "object_key": "documents/org-a/orphan.pdf",
        "bucket": service_module.settings.AWS_S3_BUCKET,
        "endpoint": service_module.settings.AWS_ENDPOINT_URL,
        "finding": "orphan",
        "status": "detected",
        "attempts": 0,
        "first_seen_at": now - timedelta(days=2),
        "last_seen_at": now - timedelta(days=2),
    }
    values.update(overrides)
    return StorageReconciliation(**values)


@pytest.mark.asyncio
async def test_eligible_orphan_is_deleted_and_audited(monkeypatch):
    now = datetime.now(UTC)
    row = _old_orphan(now)
    _FindingRepository.rows[(row.finding, row.object_key)] = row
    delete = MagicMock(return_value=True)
    monkeypatch.setattr(service_module.s3_service, "delete_file", delete)
    db = _db()
    result = await service_module.reconcile_organization_storage(db, "org-a", now=now)
    assert result["deleted"] == 1
    assert row.status == "resolved"
    delete.assert_called_once_with(row.object_key)
    assert any(
        call.args[0].action == "storage.reconciliation.orphan_deleted"
        for call in db.add.call_args_list
    )


@pytest.mark.asyncio
async def test_reappearing_resolved_orphan_receives_a_fresh_grace_period(monkeypatch):
    now = datetime.now(UTC)
    row = _old_orphan(
        now,
        status="resolved",
        attempts=4,
        first_seen_at=now - timedelta(days=10),
        resolved_at=now - timedelta(days=2),
    )
    _FindingRepository.rows[(row.finding, row.object_key)] = row
    delete = MagicMock(return_value=True)
    monkeypatch.setattr(service_module.s3_service, "delete_file", delete)
    await service_module.reconcile_organization_storage(_db(), "org-a", now=now)
    assert row.first_seen_at == now
    assert row.attempts == 0
    assert row.status == "detected"
    delete.assert_not_called()


@pytest.mark.asyncio
async def test_delete_failure_becomes_terminal_after_max_attempts(monkeypatch):
    now = datetime.now(UTC)
    row = _old_orphan(now, status="failed", attempts=4)
    _FindingRepository.rows[(row.finding, row.object_key)] = row
    monkeypatch.setattr(
        service_module.s3_service,
        "delete_file",
        MagicMock(side_effect=RuntimeError("provider unavailable")),
    )
    result = await service_module.reconcile_organization_storage(_db(), "org-a", now=now)
    assert result["failed"] == 1
    assert row.status == "terminal"
    assert row.last_error == "RuntimeError"


@pytest.mark.asyncio
async def test_expired_final_claim_becomes_terminal_without_another_delete(monkeypatch):
    now = datetime.now(UTC)
    row = _old_orphan(
        now,
        status="deleting",
        attempts=service_module.MAX_DELETE_ATTEMPTS,
        claimed_until=now - timedelta(minutes=1),
        claim_token=str(uuid4()),
    )
    _FindingRepository.rows[(row.finding, row.object_key)] = row
    delete = MagicMock(return_value=True)
    monkeypatch.setattr(service_module.s3_service, "delete_file", delete)

    result = await service_module.reconcile_organization_storage(_db(), "org-a", now=now)

    assert result["failed"] == 0
    assert row.status == "terminal"
    assert row.last_error == "STORAGE_DELETE_FINAL_CLAIM_EXPIRED"
    assert row.claim_token is None
    delete.assert_not_called()


@pytest.mark.asyncio
async def test_delete_work_is_bounded_and_reports_deferred_objects(monkeypatch):
    now = datetime.now(UTC)
    total = service_module.MAX_DELETE_OPERATIONS_PER_ORGANIZATION + 2
    keys = [f"documents/org-a/orphan-{index}.pdf" for index in range(total)]
    for key in keys:
        row = _old_orphan(now, id=key, object_key=key)
        _FindingRepository.rows[(row.finding, row.object_key)] = row
    monkeypatch.setattr(
        service_module.s3_service,
        "list_file_keys",
        lambda prefix, limit, known: keys if prefix == "documents/org-a/" else [],
    )
    delete = MagicMock(return_value=True)
    monkeypatch.setattr(service_module.s3_service, "delete_file", delete)

    result = await service_module.reconcile_organization_storage(_db(), "org-a", now=now)

    assert result["deleted"] == service_module.MAX_DELETE_OPERATIONS_PER_ORGANIZATION
    assert result["deferred"] == 2
    assert delete.call_count == service_module.MAX_DELETE_OPERATIONS_PER_ORGANIZATION


@pytest.mark.asyncio
async def test_each_claim_receives_a_fresh_lease_during_a_long_run(monkeypatch):
    snapshot = datetime.now(UTC)
    keys = ["documents/org-a/first.pdf", "documents/org-a/second.pdf"]
    for key in keys:
        row = _old_orphan(snapshot, id=key, object_key=key)
        _FindingRepository.rows[(row.finding, row.object_key)] = row
    monkeypatch.setattr(
        service_module.s3_service,
        "list_file_keys",
        lambda prefix, limit, known: keys if prefix == "documents/org-a/" else [],
    )
    first = snapshot + timedelta(minutes=9)
    second = snapshot + timedelta(minutes=20)
    monkeypatch.setattr(
        service_module,
        "_utcnow",
        MagicMock(side_effect=[first, first, first, second, second, second]),
    )
    delete = MagicMock(return_value=True)
    monkeypatch.setattr(service_module.s3_service, "delete_file", delete)

    result = await service_module.reconcile_organization_storage(_db(), "org-a", now=snapshot)

    assert result["deleted"] == 2
    assert _FindingRepository.claim_windows == [
        (first, first + service_module.CLAIM_LEASE),
        (second, second + service_module.CLAIM_LEASE),
    ]


@pytest.mark.asyncio
async def test_configuration_change_prevents_deletion(monkeypatch):
    now = datetime.now(UTC)
    row = _old_orphan(now, bucket="old-bucket", endpoint="https://old-storage.example")
    _FindingRepository.rows[(row.finding, row.object_key)] = row
    delete = MagicMock(return_value=True)
    monkeypatch.setattr(service_module.s3_service, "delete_file", delete)
    result = await service_module.reconcile_organization_storage(_db(), "org-a", now=now)
    assert result["failed"] == 1
    assert row.status == "failed"
    assert row.last_error == "STORAGE_CONFIGURATION_CHANGED"
    delete.assert_not_called()


@pytest.mark.asyncio
async def test_cross_tenant_reference_revalidation_prevents_stale_snapshot_deletion(monkeypatch):
    now = datetime.now(UTC)
    row = _old_orphan(now)
    _FindingRepository.rows[(row.finding, row.object_key)] = row
    _LifecycleRepository.all_references = [(False, row.object_key, "key")]
    delete = MagicMock(return_value=True)
    monkeypatch.setattr(service_module.s3_service, "delete_file", delete)
    result = await service_module.reconcile_organization_storage(_db(), "org-a", now=now)
    assert result["deleted"] == 0
    assert row.status == "resolved"
    delete.assert_not_called()


@pytest.mark.asyncio
async def test_prefix_conflict_fails_closed_before_deletion(monkeypatch):
    _LifecycleRepository.prefix_conflict = True
    delete = MagicMock(return_value=True)
    monkeypatch.setattr(service_module.s3_service, "delete_file", delete)
    with pytest.raises(ValueError, match="overlap"):
        await service_module.reconcile_organization_storage(_db(), "org-a")
    delete.assert_not_called()


@pytest.mark.asyncio
async def test_disappeared_finding_is_resolved():
    now = datetime.now(UTC)
    row = _old_orphan(now, object_key="documents/org-a/old.pdf", status="failed", attempts=1)
    _FindingRepository.rows[(row.finding, row.object_key)] = row
    await service_module.reconcile_organization_storage(_db(), "org-a", now=now)
    assert row.status == "resolved"
    assert row.resolved_at == now


@pytest.mark.asyncio
async def test_all_organizations_isolates_failures_and_continues(monkeypatch):
    _OrganizationRepository.pages = [["org-a", "org-b"], []]
    reconcile = AsyncMock(
        side_effect=[
            ValueError("inventory too large"),
            {"orphaned": 1, "missing": 2, "deleted": 0, "failed": 0, "deferred": 0},
        ]
    )
    monkeypatch.setattr(service_module, "reconcile_organization_storage", reconcile)
    result = await service_module.reconcile_all_organizations(_db())
    assert result == {
        "organizations": 2,
        "orphaned": 1,
        "missing": 2,
        "deleted": 0,
        "failed": 1,
        "deferred": 0,
    }
    assert reconcile.await_count == 2
