import asyncio
import io
from datetime import datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, create_autospec

import pytest
from fastapi import UploadFile
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import Headers

from app.core.errors import APIException, ForbiddenError, NotFoundError
from app.models import Lead, User
from app.repositories.lead_repository import LeadRepository
from app.schemas.crm_schemas import (
    EmailSendRequest,
    LeadCreate,
    LeadDisqualificationRequest,
    LeadQualificationRequest,
    TaskCreate,
)
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
    repo: Any = LeadRepository()
    repo.list_leads = AsyncMock(return_value=[_make_lead()])
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.list_leads(db, page=1, limit=20, organization_id="org-1")

    assert len(result) == 1
    assert result[0]["id"] == "lead-1"
    assert result[0]["contact_name"] == "Jane Doe"
    assert result[0]["organization_id"] == "org-1"
    assert result[0]["created_at"] == ""


@pytest.mark.asyncio
async def test_count_leads_forwards_filters():
    repo: Any = LeadRepository()
    repo.count_leads = AsyncMock(return_value=7)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.count_leads(
        db, organization_id="org-1", search="Acme", lead_status="New"
    )

    assert result == 7
    repo.count_leads.assert_awaited_once_with(
        db, organization_id="org-1", search="Acme", status="New"
    )


@pytest.mark.asyncio
async def test_get_lead_raises_not_found_when_missing():
    repo: Any = LeadRepository()
    repo.get_by_id_for_org = AsyncMock(return_value=None)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(NotFoundError):
        await service.get_lead(db, "missing-lead", organization_id="org-1")


@pytest.mark.asyncio
async def test_send_email_uses_the_leads_primary_email(monkeypatch):
    lead = _make_lead(email="jane@acme.com")
    repo: Any = LeadRepository()
    repo.get_by_id_for_org = AsyncMock(return_value=lead)
    queue_email = AsyncMock(return_value={"id": "email-1", "status": "Pending"})
    monkeypatch.setattr(
        "app.services.email_domain_service.email_domain_service.queue_email", queue_email
    )
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    await service.send_email(
        db,
        lead.id,
        EmailSendRequest(to=[lead.email], subject="Hello", body="Hi Jane"),
        organization_id=lead.organization_id,
    )

    queue_email.assert_awaited_once_with(
        db,
        organization_id=lead.organization_id,
        to_email=lead.email,
        subject="Hello",
        body="Hi Jane",
        idempotency_key=None,
        lead_id=lead.id,
    )


@pytest.mark.asyncio
async def test_send_email_rejects_recipient_override(monkeypatch):
    lead = _make_lead(email="jane@acme.com")
    repo: Any = LeadRepository()
    repo.get_by_id_for_org = AsyncMock(return_value=lead)
    queue_email = AsyncMock()
    monkeypatch.setattr(
        "app.services.email_domain_service.email_domain_service.queue_email", queue_email
    )
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException, match="primary email address"):
        await service.send_email(
            db,
            lead.id,
            EmailSendRequest(to=["other@example.com"], subject="Hello", body="Hi Jane"),
            organization_id=lead.organization_id,
        )

    queue_email.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_email_rejects_multiple_recipients(monkeypatch):
    lead = _make_lead(email="jane@example.com")
    repo: Any = LeadRepository()
    repo.get_by_id_for_org = AsyncMock(return_value=lead)
    service = _service_with(repo)
    queue_email = AsyncMock()
    monkeypatch.setattr(
        "app.services.email_domain_service.email_domain_service.queue_email", queue_email
    )

    with pytest.raises(APIException, match="primary email address"):
        await service.send_email(
            AsyncMock(),
            lead.id,
            EmailSendRequest(
                to=["jane@example.com", "other@example.com"],
                subject="Hello",
                body="Body",
            ),
            organization_id=lead.organization_id,
        )

    queue_email.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_email_rejects_lead_without_valid_email(monkeypatch):
    lead = _make_lead(email="")
    repo: Any = LeadRepository()
    repo.get_by_id_for_org = AsyncMock(return_value=lead)
    queue_email = AsyncMock()
    monkeypatch.setattr(
        "app.services.email_domain_service.email_domain_service.queue_email", queue_email
    )
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException, match="valid email address"):
        await service.send_email(
            db,
            lead.id,
            EmailSendRequest(to=["lead@example.com"], subject="Hello", body="Hi Jane"),
            organization_id=lead.organization_id,
        )

    queue_email.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("with_calls", [False, True])
async def test_get_timeline_passes_lead_id_to_email_and_call_repositories(
    with_calls, monkeypatch
):
    lead = _make_lead(created_at=datetime(2026, 9, 1))
    calls = (
        [
            SimpleNamespace(
                id="call-1",
                call_type="Outbound",
                notes="Discussed proposal\n[Lead:lead-1]",
                duration_seconds=60,
                timestamp=datetime(2026, 9, 2),
            ),
            SimpleNamespace(
                id="call-2",
                call_type="Inbound",
                notes=None,
                duration_seconds=30,
                timestamp=datetime(2026, 9, 3),
            ),
        ]
        if with_calls
        else []
    )
    repo: Any = LeadRepository()
    repo.get_by_id_for_org = AsyncMock(return_value=lead)
    repo.list_activities = AsyncMock(return_value=[])
    repo.list_notes = AsyncMock(return_value=[])
    repo.list_attachments = AsyncMock(return_value=[])
    repo.list_tasks = AsyncMock(return_value=[])
    repo.list_emails = AsyncMock(return_value=[])
    repo.list_calls = create_autospec(repo.list_calls, return_value=calls)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    actor = _make_user()
    actor.__dict__["_api_key_scopes"] = {"calls:read"}
    monkeypatch.setattr(
        "app.services.lead_service.auth_service.get_user_permissions",
        AsyncMock(return_value=["calls:read"]),
    )

    result = await service.get_timeline(
        db,
        lead.id,
        organization_id=lead.organization_id,
        current_user=actor,
    )

    assert result
    repo.list_emails.assert_awaited_once_with(
        db,
        organization_id=lead.organization_id,
        lead_id=lead.id,
        lead_tag=f"[Lead:{lead.id}]",
    )
    repo.list_calls.assert_awaited_once_with(
        db,
        organization_id=lead.organization_id,
        lead_id=lead.id,
        lead_tag=f"[Lead:{lead.id}]",
    )
    if with_calls:
        assert [event["id"] for event in result] == ["call-call-2", "call-call-1", "created-lead-1"]
        assert result[0] == {
            "id": "call-call-2",
            "event_type": "call_logged",
            "title": "Inbound Call Logged",
            "description": "Duration: 30 sec · Direction: Inbound",
            "timestamp": "2026-09-03 00:00:00",
        }
        assert result[1]["description"] == "Discussed proposal · Direction: Outbound"
    else:
        assert [event["event_type"] for event in result] == ["lead_created"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role_permissions", "api_key_scopes"),
    [
        (["leads:read"], None),
        (["leads:read", "calls:read"], {"leads:read"}),
    ],
)
async def test_timeline_does_not_expose_calls_without_effective_calls_read(
    role_permissions, api_key_scopes, monkeypatch
):
    lead = _make_lead(created_at=datetime(2026, 9, 1))
    repo: Any = LeadRepository()
    repo.get_by_id_for_org = AsyncMock(return_value=lead)
    repo.list_activities = AsyncMock(return_value=[])
    repo.list_notes = AsyncMock(return_value=[])
    repo.list_attachments = AsyncMock(return_value=[])
    repo.list_tasks = AsyncMock(return_value=[])
    repo.list_emails = AsyncMock(return_value=[])
    repo.list_calls = AsyncMock()
    monkeypatch.setattr(
        "app.services.lead_service.auth_service.get_user_permissions",
        AsyncMock(return_value=role_permissions),
    )
    actor = _make_user()
    if api_key_scopes is not None:
        actor.__dict__["_api_key_scopes"] = api_key_scopes

    result = await _service_with(repo).get_timeline(
        AsyncMock(spec=AsyncSession),
        lead.id,
        organization_id=lead.organization_id,
        current_user=actor,
    )

    assert all(item["event_type"] != "call_logged" for item in result)
    repo.list_calls.assert_not_called()


@pytest.mark.asyncio
async def test_create_lead_resolves_org_and_serializes(monkeypatch):
    lead = _make_lead()
    repo: Any = LeadRepository()
    repo.create = AsyncMock(return_value=lead)
    repo.get_organization = AsyncMock(return_value=SimpleNamespace(id="org-1"))
    repo.get_user = AsyncMock(return_value=None)
    service = _service_with(repo)
    monkeypatch.setattr(integration_service, "notify_slack_event", AsyncMock())
    db = AsyncMock(spec=AsyncSession)

    payload = LeadCreate(
        title="Acme Corp", company="Acme Inc", contact_name="Jane Doe", email="jane@acme.com"
    )
    result = await service.create_lead(db, payload, _make_user())

    assert result["id"] == "lead-1"
    assert result["status"] == "New"
    repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_lead_validates_and_persists_custom_fields(monkeypatch):
    lead = _make_lead(custom_fields={"territory": "South"})
    repo: Any = LeadRepository()
    repo.create = AsyncMock(return_value=lead)
    repo.get_organization = AsyncMock(return_value=SimpleNamespace(id="org-1"))
    custom_fields = AsyncMock()
    custom_fields.validate_values.return_value = {"territory": "South"}
    service = LeadService(repository=repo, custom_field_service_instance=custom_fields)
    monkeypatch.setattr(integration_service, "notify_slack_event", AsyncMock())
    db = AsyncMock(spec=AsyncSession)

    payload = LeadCreate(
        title="Acme Corp",
        company="Acme Inc",
        contact_name="Jane Doe",
        email="jane@acme.com",
        custom_fields={"territory": "South"},
    )
    result = await service.create_lead(db, payload, _make_user())

    assert repo.create.await_args.kwargs["data"]["custom_fields"] == {"territory": "South"}
    assert result["custom_fields"] == {"territory": "South"}
    custom_fields.validate_values.assert_awaited_once_with(
        db,
        organization_id="org-1",
        entity_type="Lead",
        values={"territory": "South"},
    )


@pytest.mark.asyncio
async def test_create_lead_fires_lead_created_event(monkeypatch):
    lead = _make_lead()
    repo: Any = LeadRepository()
    repo.create = AsyncMock(return_value=lead)
    repo.get_organization = AsyncMock(return_value=SimpleNamespace(id="org-1"))
    repo.get_user = AsyncMock(return_value=None)
    service = _service_with(repo)
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)
    db = AsyncMock(spec=AsyncSession)

    payload = LeadCreate(
        title="Acme Corp", company="Acme Inc", contact_name="Jane Doe", email="jane@acme.com"
    )
    await service.create_lead(db, payload, _make_user())

    notify.assert_awaited_once()
    kwargs = notify.await_args_list[-1].kwargs
    assert kwargs["event_name"] == "lead.created"
    assert kwargs["org_id"] == "org-1"
    assert kwargs["data"]["id"] == "lead-1"
    assert kwargs["data"]["email"] == "jane@acme.com"


@pytest.mark.asyncio
async def test_update_lead_only_applies_provided_fields(monkeypatch):
    lead = _make_lead()
    repo: Any = LeadRepository()
    repo.get_by_id_for_org = AsyncMock(return_value=lead)
    repo.record_activity = AsyncMock()
    service = _service_with(repo)
    monkeypatch.setattr(integration_service, "notify_slack_event", AsyncMock())
    db = AsyncMock(spec=AsyncSession)

    from app.schemas.crm_schemas import LeadUpdate

    result = await service.update_lead(db, "lead-1", LeadUpdate(status="Contacted"), _make_user())

    assert result["status"] == "Contacted"
    assert lead.status == "Contacted"
    assert lead.title == "Acme Corp"
    repo.get_by_id_for_org.assert_awaited_once_with(db, "lead-1", "org-1")
    repo.record_activity.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_lead_rejects_qualification_without_customer_details():
    lead = _make_lead(company="")
    repo: Any = LeadRepository()
    repo.get_by_id_for_org = AsyncMock(return_value=lead)
    repo.record_activity = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException, match="required to qualify"):
        await service.qualify_lead(
            db, "lead-1", LeadQualificationRequest(), _make_user()
        )

    repo.record_activity.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_lead_fires_lead_updated_event(monkeypatch):
    lead = _make_lead()
    repo: Any = LeadRepository()
    repo.get_by_id_for_org = AsyncMock(return_value=lead)
    service = _service_with(repo)
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)
    db = AsyncMock(spec=AsyncSession)

    from app.schemas.crm_schemas import LeadUpdate

    await service.update_lead(db, "lead-1", LeadUpdate(status="Contacted"), _make_user())

    notify.assert_awaited_once()
    kwargs = notify.await_args_list[-1].kwargs
    assert kwargs["event_name"] == "lead.updated"
    assert kwargs["org_id"] == "org-1"
    assert kwargs["data"]["status"] == "Contacted"


@pytest.mark.asyncio
async def test_update_lead_rejects_organization_transfer():
    lead = _make_lead()
    repo: Any = LeadRepository()
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
async def test_update_lead_rejects_assignee_from_another_organization(monkeypatch):
    lead = _make_lead()
    repo: Any = LeadRepository()
    repo.get_by_id_for_org = AsyncMock(return_value=lead)
    repo.get_user = AsyncMock(return_value=_make_user(id="usr-2", organization_id="org-2"))
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    monkeypatch.setattr(
        "app.services.lead_service.auth_service.get_user_permissions",
        AsyncMock(return_value=["leads:assign"]),
    )

    from app.schemas.crm_schemas import LeadUpdate

    with pytest.raises(APIException, match="Assignee must be"):
        await service.update_lead(db, "lead-1", LeadUpdate(assigned_to="usr-2"), _make_user())

    db.commit.assert_not_awaited()


def test_generic_update_rejects_controlled_lifecycle_statuses():
    from app.schemas.crm_schemas import LeadUpdate

    for controlled_status in ("Qualified", "Unqualified", "Converted"):
        with pytest.raises(ValidationError):
            LeadUpdate(status=controlled_status)


@pytest.mark.asyncio
async def test_update_lead_requires_assign_permission(monkeypatch):
    lead = _make_lead()
    repo: Any = LeadRepository()
    repo.get_by_id_for_org = AsyncMock(return_value=lead)
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    monkeypatch.setattr(
        "app.services.lead_service.auth_service.get_user_permissions",
        AsyncMock(return_value=[]),
    )

    from app.schemas.crm_schemas import LeadUpdate

    with pytest.raises(ForbiddenError, match="leads:assign"):
        await service.update_lead(
            db, "lead-1", LeadUpdate(assigned_to="usr-2"), _make_user()
        )

    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_qualification_disqualification_and_reopen_are_audited():
    lead = _make_lead(status="Contacted")
    repo: Any = LeadRepository()
    repo.get_by_id_for_org = AsyncMock(return_value=lead)
    repo.record_activity = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)
    user = _make_user()

    qualified = await service.qualify_lead(
        db, lead.id, LeadQualificationRequest(reason="Budget confirmed"), user
    )
    assert qualified["status"] == "Qualified"
    assert lead.qualified_by == user.id

    disqualified = await service.disqualify_lead(
        db,
        lead.id,
        LeadDisqualificationRequest(reason="Project paused"),
        user,
    )
    assert disqualified["status"] == "Unqualified"
    assert lead.disqualified_by == user.id

    reopened = await service.reopen_lead(db, lead.id, user)
    assert reopened["status"] == "Contacted"
    assert repo.record_activity.await_count == 3


@pytest.mark.asyncio
async def test_create_follow_up_rejects_invalid_due_date():
    lead = _make_lead()
    repo: Any = LeadRepository()
    repo.get_by_id_for_org = AsyncMock(return_value=lead)
    repo.get_user = AsyncMock(return_value=_make_user())
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException, match="ISO-8601"):
        await service.create_task(
            db,
            lead.id,
            TaskCreate(title="Call back", due_date="not-a-date"),
            organization_id="org-1",
            actor_id="usr-1",
        )


@pytest.mark.asyncio
async def test_bulk_update_status_returns_early_for_empty_ids():
    repo: Any = LeadRepository()
    repo.list_by_ids = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.bulk_update_status(
        db, [], "Contacted", organization_id="org-1", actor_id="usr-1"
    )

    assert result == {"affected_count": 0, "message": "No lead IDs provided"}
    repo.list_by_ids.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_bulk_update_status_rejects_unknown_status():
    repo: Any = LeadRepository()
    repo.list_by_ids = AsyncMock()
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    with pytest.raises(APIException, match="Unsupported lead status"):
        await service.bulk_update_status(
            db, ["lead-1"], "anything", organization_id="org-1", actor_id="usr-1"
        )

    repo.list_by_ids.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_bulk_update_status_stores_canonical_status():
    lead = _make_lead()
    repo: Any = LeadRepository()
    repo.list_by_ids = AsyncMock(return_value=[lead])
    service = _service_with(repo)
    db = AsyncMock(spec=AsyncSession)

    result = await service.bulk_update_status(
        db, ["lead-1"], " contacted ", organization_id="org-1", actor_id="usr-1"
    )

    assert lead.status == "Contacted"
    assert result["message"] == "Status updated to Contacted"


@pytest.mark.asyncio
async def test_download_document_rejects_attachment_from_another_lead():
    repo: Any = LeadRepository()
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
    repo: Any = LeadRepository()
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
    repo: Any = LeadRepository()
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
    repo: Any = LeadRepository()
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
    repo: Any = LeadRepository()
    repo.get_by_id_for_org = AsyncMock(return_value=lead)
    repo.get_user = AsyncMock(return_value=_make_user(id="usr-9"))
    service = _service_with(repo)
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)
    db = AsyncMock(spec=AsyncSession)

    await service.assign_lead(
        db, "lead-1", "usr-9", organization_id="org-1", actor_id="usr-1"
    )

    notify.assert_awaited_once()
    kwargs = notify.await_args_list[-1].kwargs
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
    repo: Any = LeadRepository()
    repo.get_by_id_for_org = AsyncMock(return_value=lead)
    repo.get_user = AsyncMock(return_value=_make_user())
    repo.create_task = AsyncMock(return_value=task)
    service = _service_with(repo)
    notify = AsyncMock()
    monkeypatch.setattr(integration_service, "notify_slack_event", notify)
    db = AsyncMock(spec=AsyncSession)

    await service.create_task(
        db,
        "lead-1",
        TaskCreate(title="Call back", due_date="2026-09-07T10:00:00+00:00"),
        organization_id="org-1",
        actor_id="usr-1",
    )

    notify.assert_awaited_once()
    kwargs = notify.await_args_list[-1].kwargs
    assert kwargs["event_name"] == "task.created"
    assert kwargs["org_id"] == "org-1"
    assert kwargs["data"]["title"] == "Call back"
