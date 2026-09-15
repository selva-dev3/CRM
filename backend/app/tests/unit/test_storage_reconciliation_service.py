from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models import StorageReconciliation
from app.services import storage_reconciliation_service as service_module
from app.services.storage_reconciliation_service import classify_storage


def test_classify_storage_reports_orphans_and_missing_references():
    orphaned, missing = classify_storage(
        {"documents/org-a/kept.pdf", "documents/org-a/missing.pdf"},
        {"documents/org-a/kept.pdf", "documents/org-a/orphan.pdf"},
    )

    assert orphaned == {"documents/org-a/orphan.pdf"}
    assert missing == {"documents/org-a/missing.pdf"}


def test_classify_storage_is_idempotent_for_matching_inventory():
    assert classify_storage({"documents/org-a/kept.pdf"}, {"documents/org-a/kept.pdf"}) == (
        set(),
        set(),
    )


class _Repository:
    async def storage_references(self, db, organization_id, *, owned_only=None):
        if False:
            yield None

    async def storage_prefix_owners(self, db, organization_id):
        yield "organization", organization_id


def _db(existing=None):
    db = SimpleNamespace(
        scalars=AsyncMock(return_value=existing or []),
        commit=AsyncMock(),
        add=MagicMock(),
    )
    return db


@pytest.mark.asyncio
async def test_reconcile_records_orphan_without_deleting_during_grace(monkeypatch):
    db = _db()
    monkeypatch.setattr(service_module, "OrganizationLifecycleRepository", _Repository)
    monkeypatch.setattr(
        service_module.s3_service,
        "list_file_keys",
        lambda prefix, limit, known: (
            ["documents/org-a/orphan.pdf"] if prefix == "documents/org-a/" else []
        ),
    )
    delete = MagicMock(return_value=True)
    monkeypatch.setattr(service_module.s3_service, "delete_file", delete)

    result = await service_module.reconcile_organization_storage(db, "org-a")

    assert result["orphaned"] == 1
    assert result["deleted"] == 0
    delete.assert_not_called()
    finding = db.add.call_args.args[0]
    assert finding.finding == "orphan"
    assert finding.status == "detected"


@pytest.mark.asyncio
async def test_reconcile_deletes_only_after_grace_and_audits_repair(monkeypatch):
    now = datetime.now(UTC)
    row = StorageReconciliation(
        organization_id="org-a",
        object_key="documents/org-a/orphan.pdf",
        bucket=service_module.settings.AWS_S3_BUCKET,
        endpoint=service_module.settings.AWS_ENDPOINT_URL,
        finding="orphan",
        status="detected",
        first_seen_at=now - timedelta(hours=25),
        last_seen_at=now - timedelta(hours=25),
    )
    db = _db([row])
    monkeypatch.setattr(service_module, "OrganizationLifecycleRepository", _Repository)
    monkeypatch.setattr(
        service_module.s3_service,
        "list_file_keys",
        lambda prefix, limit, known: (
            ["documents/org-a/orphan.pdf"] if prefix == "documents/org-a/" else []
        ),
    )
    delete = MagicMock(return_value=True)
    monkeypatch.setattr(service_module.s3_service, "delete_file", delete)

    result = await service_module.reconcile_organization_storage(db, "org-a", now=now)

    assert result["deleted"] == 1
    assert row.status == "resolved"
    delete.assert_called_once_with("documents/org-a/orphan.pdf")
    assert any(
        item.action == "storage.reconciliation.orphan_deleted"
        for item in (call.args[0] for call in db.add.call_args_list)
    )
