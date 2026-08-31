import asyncio
import io
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import Headers

from app.core.errors import APIException, ForbiddenError, NotFoundError
from app.models import Lead, User
from app.repositories.lead_repository import LeadRepository
from app.schemas.crm_schemas import LeadCreate, TaskCreate
from app.services.integration_service import integration_service
from app.services.lead_service import LeadService


def _make_lead(**overrides) -> Lead:
    defaults = {
        "id": "lead-1",
        "organization_id": "org-1",
        "title": "Acme Corp",
        "company": "Acme Inc",
        "contact_name": "Jane Doe",
        "email": "jane@acme.com",
        "phone": None,
        "website": None,
        "industry": None,
        "company_size": None,
        "country": None,
        "state": None,
        "city": None,
        "address": None,
        "postal_code": None,
        "status": "New",
        "source": "Website",
        "score": 50.0,
        "assigned_to": None,
        "is_archived": False,
    }
    defaults.update(overrides)
    return Lead(**defaults)


def _service_with(repo: LeadRepository) -> LeadService:
    return LeadService(repository=repo)


def _make_user(**overrides) -> User:
    defaults = {
        "id": "usr-1",
        "name": "Jane Admin",
        "email": "admin@acme.com",
        "hashed_password": "hashed",
        "organization_id": "org-1",
    }
    defaults.update(overrides)
    return User(**defaults)


@pytest.mark.asyncio
async def test_list_leads_returns_serialized_dicts():
    repo = LeadRepository()
    repo.list_leads = AsyncMock(return_value=[_make_lead()])
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.list_leads(db, page=1, limit=20)

    assert len(result) == 1
    assert result[0]["id"] == "lead-1"
    assert result[0]["contact_name"] == "Jane Doe"
    assert result[0]["organization_id"] == "org-1"
    assert result[0]["created_at"] == "2026-01-01"


@pytest.mark.asyncio
async def test_count_leads_forwards_filters():
    repo = LeadRepository()
    repo.count_leads = AsyncMock(return_value=7)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.count_leads(db, search="Acme", lead_status="New")

    assert result == 7
    repo.count_leads.assert_awaited_once_with(db, search="Acme", status="New")


@pytest.mark.asyncio
async def test_get_lead_raises_not_found_when_missing():
    repo = LeadRepository()
    repo.get_by_id = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_lead(db, "missing-lead")


@pytest.mark.asyncio
async def test_create_lead_resolves_org_and_serializes(monkeypatch):
    lead = _make_lead()
    repo = LeadRepository()
    repo.create = AsyncMock(return_value=lead)
    repo.get_organization = AsyncMock(return_value=object())
    repo.get_user = AsyncMock(return_value=None)
    service = _service_with(repo)
    monkeypatch.setattr(integration_service, "notify_slack_event", AsyncMock())
    db = AsyncMock(spec=AsyncSession)

    payload = LeadCreate(title="Acme Corp", company="Acme Inc", contact_name="Jane Doe", email="jane@acme.com")
    result = await service.create_lead(db, payload)

    assert result["id"] == "lead-1"
    assert result["status"] == "New"
    repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_lead_fires_lead_created_event(monkeypatch):
    lead = _make_lead()
    repo = LeadRepository()
    repo.create = AsyncMock(return_value=lead)
    repo.get_organization = AsyncMock(return_value=object())
    repo.get_user = AsyncMock(return_value=None)
    service = _service_with(repo)
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)
    db = AsyncMock(spec=AsyncSession)

    payload = LeadCreate(title="Acme Corp", company="Acme Inc", contact_name="Jane Doe", email="jane@acme.com")
    await service.create_lead(db, payload)

    notify.assert_awaited_once()
    kwargs = notify.await_args.kwargs
    assert kwargs["event_name"] == "lead.created"
    assert kwargs["org_id"] == "org-1"
    assert kwargs["data"]["id"] == "lead-1"
    assert kwargs["data"]["email"] == "jane@acme.com"


@pytest.mark.asyncio
async def test_update_lead_only_applies_provided_fields(monkeypatch):
    lead = _make_lead()
    repo = LeadRepository()
    repo.get_by_id_for_org = AsyncMock(return_value=lead)
    service = _service_with(repo)
    monkeypatch.setattr(integration_service, "notify_slack_event", AsyncMock())
    db = AsyncMock(spec=AsyncSession)

    from app.schemas.crm_schemas import LeadUpdate

    result = await service.update_lead(
        db, "lead-1", LeadUpdate(status="Qualified"), _make_user()
    )

    assert result["status"] == "Qualified"
    assert lead.status == "Qualified"
    assert lead.title == "Acme Corp"
    repo.get_by_id_for_org.assert_awaited_once_with(db, "lead-1", "org-1")


@pytest.mark.asyncio
async def test_update_lead_fires_lead_updated_event(monkeypatch):
    lead = _make_lead()
    repo = LeadRepository()
    repo.get_by_id_for_org = AsyncMock(return_value=lead)
    service = _service_with(repo)
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)
    db = AsyncMock(spec=AsyncSession)

    from app.schemas.crm_schemas import LeadUpdate

    await service.update_lead(db, "lead-1", LeadUpdate(status="Qualified"), _make_user())

    notify.assert_awaited_once()
    kwargs = notify.await_args.kwargs
    assert kwargs["event_name"] == "lead.updated"
    assert kwargs["org_id"] == "org-1"
    assert kwargs["data"]["status"] == "Qualified"


@pytest.mark.asyncio
async def test_update_lead_rejects_organization_transfer():
    lead = _make_lead()
    repo = LeadRepository()
    repo.get_by_id_for_org = AsyncMock(return_value=lead)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    from app.schemas.crm_schemas import LeadUpdate

    with pytest.raises(ForbiddenError):
        await service.update_lead(
            db,
            "lead-1",
            LeadUpdate(organization_id="org-2"),
            _make_user(),
        )

    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_lead_rejects_assignee_from_another_organization():
    lead = _make_lead()
    repo = LeadRepository()
    repo.get_by_id_for_org = AsyncMock(return_value=lead)
    repo.get_user = AsyncMock(return_value=_make_user(id="usr-2", organization_id="org-2"))
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    from app.schemas.crm_schemas import LeadUpdate

    with pytest.raises(APIException, match="Assignee must be"):
        await service.update_lead(
            db, "lead-1", LeadUpdate(assigned_to="usr-2"), _make_user()
        )

    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_bulk_update_status_returns_early_for_empty_ids():
    repo = LeadRepository()
    repo.list_by_ids = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.bulk_update_status(db, [], "Qualified")

    assert result == {"affected_count": 0, "message": "No lead IDs provided"}
    repo.list_by_ids.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_bulk_update_status_rejects_unknown_status():
    repo = LeadRepository()
    repo.list_by_ids = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException, match="Unsupported lead status"):
        await service.bulk_update_status(db, ["lead-1"], "anything")

    repo.list_by_ids.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_bulk_update_status_stores_canonical_status():
    lead = _make_lead()
    repo = LeadRepository()
    repo.list_by_ids = AsyncMock(return_value=[lead])
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.bulk_update_status(db, ["lead-1"], " qualified ")

    assert lead.status == "Qualified"
    assert result["message"] == "Status updated to Qualified"


@pytest.mark.asyncio
async def test_download_document_rejects_attachment_from_another_lead():
    repo = LeadRepository()
    repo.get_by_id_for_org = AsyncMock(return_value=_make_lead())
    repo.get_attachment_for_lead = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError, match="attachment record"):
        await service.download_document(db, "lead-1", "doc-2", _make_user())


@pytest.mark.asyncio
async def test_download_document_reads_s3_off_event_loop(monkeypatch):
    attachment = SimpleNamespace(
        id="doc-1",
        lead_id="lead-1",
        filename="proposal.pdf",
        file_url="",
        mime_type="application/pdf",
    )
    repo = LeadRepository()
    repo.get_by_id_for_org = AsyncMock(return_value=_make_lead())
    repo.get_attachment_for_lead = AsyncMock(return_value=attachment)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    body = SimpleNamespace(read=MagicMock(return_value=b"pdf bytes"))
    get_object = MagicMock(return_value={"Body": body})
    monkeypatch.setattr("app.services.lead_service.s3_service.s3_client.get_object", get_object)
    to_thread = AsyncMock(side_effect=lambda function, *args, **kwargs: function(*args, **kwargs))
    monkeypatch.setattr(asyncio, "to_thread", to_thread)

    result = await service.download_document(db, "lead-1", "doc-1", _make_user())

    assert result == (b"pdf bytes", "application/pdf", "proposal.pdf")
    to_thread.assert_awaited_once()
    body.read.assert_called_once_with()


@pytest.mark.asyncio
async def test_upload_document_rejects_oversize_before_s3(monkeypatch):
    repo = LeadRepository()
    repo.get_by_id_for_org = AsyncMock(return_value=_make_lead())
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    file = UploadFile(
        io.BytesIO(b"123456"),
        filename="proposal.pdf",
        size=6,
        headers=Headers({"content-type": "application/pdf"}),
    )
    monkeypatch.setattr("app.services.lead_service.settings.MAX_DOCUMENT_UPLOAD_SIZE", 5)
    upload = MagicMock()
    monkeypatch.setattr("app.services.lead_service.s3_service.upload_file", upload)

    with pytest.raises(APIException) as exc_info:
        await service.upload_document(db, "lead-1", file, _make_user())

    assert exc_info.value.status_code == 413
    upload.assert_not_called()


@pytest.mark.asyncio
async def test_upload_document_rejects_unsupported_content_type(monkeypatch):
    repo = LeadRepository()
    repo.get_by_id_for_org = AsyncMock(return_value=_make_lead())
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    file = UploadFile(
        io.BytesIO(b"executable"),
        filename="payload.exe",
        size=10,
        headers=Headers({"content-type": "application/octet-stream"}),
    )
    upload = MagicMock()
    monkeypatch.setattr("app.services.lead_service.s3_service.upload_file", upload)

    with pytest.raises(APIException, match="Unsupported file extension"):
        await service.upload_document(db, "lead-1", file, _make_user())

    upload.assert_not_called()


@pytest.mark.asyncio
async def test_assign_lead_fires_lead_assigned_event(monkeypatch):
    lead = _make_lead()
    repo = LeadRepository()
    repo.get_by_id = AsyncMock(return_value=lead)
    service = _service_with(repo)
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)
    db = AsyncMock(spec=AsyncSession)

    await service.assign_lead(db, "lead-1", "usr-9")

    notify.assert_awaited_once()
    kwargs = notify.await_args.kwargs
    assert kwargs["event_name"] == "lead.assigned"
    assert kwargs["org_id"] == "org-1"
    assert kwargs["data"]["assigned_to"] == "usr-9"


@pytest.mark.asyncio
async def test_lead_create_task_fires_task_created_event(monkeypatch):
    from app.models.task import Task

    lead = _make_lead()
    task = Task(
        id="task-1",
        organization_id="org-1",
        title="Call back",
        status="Pending",
        priority="High",
        assigned_to="usr-1",
    )
    repo = LeadRepository()
    repo.get_by_id = AsyncMock(return_value=lead)
    repo.get_first_user = AsyncMock(return_value=None)
    repo.create_user = AsyncMock(return_value=type("U", (), {"id": "usr-1"})())
    repo.create_task = AsyncMock(return_value=task)
    service = _service_with(repo)
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)
    db = AsyncMock(spec=AsyncSession)

    await service.create_task(db, "lead-1", TaskCreate(title="Call back"))

    notify.assert_awaited_once()
    kwargs = notify.await_args.kwargs
    assert kwargs["event_name"] == "task.created"
    assert kwargs["org_id"] == "org-1"
    assert kwargs["data"]["title"] == "Call back"
