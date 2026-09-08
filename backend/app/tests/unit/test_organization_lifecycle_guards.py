from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from app.core.config import settings
from app.core.errors import ForbiddenError
from app.models import User
from app.schemas.organization_invitation_schemas import AcceptInvitationRequest
from app.schemas.organization_lifecycle import PlatformOrganizationCreate
from app.services.organization_lifecycle_service import (
    OrganizationLifecycleService,
    storage_key,
)
from app.services.s3_service import S3Service


@pytest.mark.parametrize("password", ["a" * 7, "a" * 73, "é" * 37])
def test_organization_invitation_password_policy_rejects_invalid_boundaries(password):
    with pytest.raises(ValidationError):
        AcceptInvitationRequest(password=password)


@pytest.mark.parametrize("password", ["a" * 8, "a" * 72, "é" * 36])
def test_organization_invitation_password_policy_accepts_valid_boundaries(password):
    assert AcceptInvitationRequest(password=password).password == password


@pytest.mark.asyncio
async def test_platform_api_keys_cannot_provision_or_delete():
    user = User(id="platform-test", is_platform_admin=True, organization_id=None)
    user.__dict__["_api_key_scopes"] = {"*"}
    db = AsyncMock()
    service = OrganizationLifecycleService()
    with pytest.raises(ForbiddenError):
        await service.create(db, PlatformOrganizationCreate(name="Rejected"), user)
    with pytest.raises(ForbiddenError):
        await service.delete(db, "organization-test", user)
    db.commit.assert_not_awaited()
    db.execute.assert_not_awaited()


@pytest.mark.parametrize(
    "key", ["../other", "/absolute", "a/../b", "a//b", "bad\x00key", "a" * 1025]
)
def test_storage_keys_reject_unsafe_paths(key):
    assert storage_key(key, "key") is None


def test_storage_urls_are_limited_to_configured_bucket(monkeypatch):
    monkeypatch.setattr(settings, "AWS_ENDPOINT_URL", "https://storage.example.com")
    monkeypatch.setattr(settings, "AWS_S3_BUCKET", "crm-test")
    assert (
        storage_key("https://storage.example.com/crm-test/tenant/file.txt?signature=ignored", "url")
        == "tenant/file.txt"
    )
    assert storage_key("https://external.example.com/crm-test/tenant/file.txt", "url") is None
    assert storage_key("https://storage.example.com/another-bucket/file.txt", "url") is None
    assert storage_key("https://storage.example.com/crm-test/%2e%2e/file.txt", "url") is None


def test_prefix_inventory_counts_only_keys_not_already_referenced():
    service = object.__new__(S3Service)
    service.bucket_name = "test-bucket"
    service.minio_client = MagicMock()
    service.minio_client.list_objects.return_value = [
        SimpleNamespace(object_name="documents/org-1/already-a"),
        SimpleNamespace(object_name="documents/org-1/already-b"),
        SimpleNamespace(object_name="documents/org-1/orphan"),
    ]

    result = service.list_file_keys(
        "documents/org-1/",
        limit=1,
        known_keys={
            "documents/org-1/already-a",
            "documents/org-1/already-b",
        },
    )

    assert result == ["documents/org-1/orphan"]


@pytest.mark.asyncio
async def test_cleanup_inventories_retained_files_once_per_batch(monkeypatch):
    from types import SimpleNamespace

    from app.repositories.organization_lifecycle_repository import OrganizationLifecycleRepository
    from app.services.organization_cleanup_service import cleanup_organization_files

    db = AsyncMock()
    items = [
        SimpleNamespace(
            id=f"item-{i}",
            operation_id="operation",
            object_key=f"controlled/{i}",
            endpoint=settings.AWS_ENDPOINT_URL,
            bucket=settings.AWS_S3_BUCKET,
        )
        for i in range(3)
    ]
    monkeypatch.setattr(
        OrganizationLifecycleRepository, "claim_file", AsyncMock(side_effect=[*items, None])
    )
    monkeypatch.setattr(OrganizationLifecycleRepository, "finish_file", AsyncMock())
    monkeypatch.setattr(OrganizationLifecycleRepository, "renew_file_claim", AsyncMock(return_value=True))
    monkeypatch.setattr(
        OrganizationLifecycleRepository,
        "get_deletion",
        AsyncMock(return_value=SimpleNamespace(organization_id="deleted")),
    )
    calls = []

    async def references(*args):
        calls.append(1)
        for i in range(10001):
            yield False, f"retained/{i}", "key"

    monkeypatch.setattr(OrganizationLifecycleRepository, "storage_references", references)
    monkeypatch.setattr(
        "app.services.organization_cleanup_service.s3_service.delete_file", lambda _: True
    )
    assert await cleanup_organization_files(db) == 3
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_prefix_collision_check_returns_exists_without_streaming_platform_owners():
    from app.repositories.organization_lifecycle_repository import OrganizationLifecycleRepository
    db = AsyncMock()
    db.scalar.return_value = None
    assert not await OrganizationLifecycleRepository().storage_prefix_conflict(db, 'org-1', ['documents/org-1/', 'branding/org-1_'])
    assert db.scalar.await_count == 4
    db.stream.assert_not_awaited()
    db.stream_scalars.assert_not_awaited()


@pytest.mark.asyncio
async def test_cleanup_does_not_delete_after_another_worker_reclaims_lease(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock

    from app.repositories.organization_lifecycle_repository import OrganizationLifecycleRepository
    from app.services.organization_cleanup_service import cleanup_organization_files

    db = AsyncMock()
    item = SimpleNamespace(id='item', operation_id='operation', object_key='controlled/file', endpoint=settings.AWS_ENDPOINT_URL, bucket=settings.AWS_S3_BUCKET)
    monkeypatch.setattr(OrganizationLifecycleRepository, 'claim_file', AsyncMock(side_effect=[item, None]))
    monkeypatch.setattr(OrganizationLifecycleRepository, 'get_deletion', AsyncMock(return_value=SimpleNamespace(organization_id='deleted')))
    monkeypatch.setattr(OrganizationLifecycleRepository, 'renew_file_claim', AsyncMock(return_value=False))
    async def references(*args):
        yield False, 'unrelated/file', 'key'
    monkeypatch.setattr(OrganizationLifecycleRepository, 'storage_references', references)
    remove = Mock()
    monkeypatch.setattr('app.services.organization_cleanup_service.s3_service.delete_file', remove)
    assert await cleanup_organization_files(db) == 0
    remove.assert_not_called()


@pytest.mark.asyncio
async def test_deletion_preparation_timeout_rolls_back(monkeypatch):
    from app.core.errors import APIException
    monkeypatch.setattr(settings, 'ORGANIZATION_DELETION_ENABLED', True)
    service = OrganizationLifecycleService()
    monkeypatch.setattr(service.repository, 'set_lock_timeout', AsyncMock(side_effect=TimeoutError))
    db = AsyncMock()
    with pytest.raises(APIException) as error:
        await service.delete(db, 'org-test', User(id='platform', is_platform_admin=True, organization_id=None))
    assert error.value.status_code == 503
    assert error.value.code == 'ORGANIZATION_DELETION_TIMEOUT'
    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()
