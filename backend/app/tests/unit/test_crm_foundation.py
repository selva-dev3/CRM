from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from app.core.errors import ConflictError, ForbiddenError
from app.core.record_access import RecordAccessContext
from app.schemas.dashboard_layout import DashboardLayoutUpdate
from app.schemas.record_access import RoleRecordScopeUpdate
from app.schemas.support import (
    KnowledgeArticleUpdate,
    TicketCommentCreate,
    TicketCreate,
    TicketUpdate,
)
from app.schemas.workflow import WorkflowCreate, WorkflowUpdate
from app.services.auth_service import AuthService
from app.services.record_access_service import RecordAccessService
from app.services.support_service import SupportService
from app.services.workflow_service import WorkflowService


def _context(scope: str) -> RecordAccessContext:
    return RecordAccessContext(
        scope=scope,
        user_id="user-1",
        team_ids=frozenset({"team-1"}),
        team_user_ids=frozenset({"user-1", "user-2"}),
    )


@pytest.mark.parametrize(
    ("scope", "assigned_to", "created_by", "team_id", "expected"),
    [
        ("all", None, None, None, True),
        ("none", "user-1", "user-1", "team-1", False),
        ("own", "user-2", "user-1", None, True),
        ("assigned", "user-1", "user-2", None, True),
        ("team", "user-2", "user-3", None, True),
        ("team", "user-3", "user-3", "team-1", True),
        ("team", "user-3", "user-3", "team-2", False),
    ],
)
def test_record_access_scopes(scope, assigned_to, created_by, team_id, expected):
    assert (
        RecordAccessService.allows(
            _context(scope),
            assigned_to=assigned_to,
            created_by=created_by,
            team_id=team_id,
        )
        is expected
    )


def test_record_scope_payload_rejects_duplicate_modules():
    with pytest.raises(ValidationError):
        RoleRecordScopeUpdate.model_validate(
            {
                "scopes": [
                    {"module": "leads", "scope": "own"},
                    {"module": "leads", "scope": "team"},
                ]
            }
        )


def test_ticket_requires_contact_or_company():
    with pytest.raises(ValidationError):
        TicketCreate(subject="Help", description="Something is not working")


@pytest.mark.parametrize(
    "action",
    [
        {"type": "assign", "user_id": "user-1"},
        {"type": "update_field", "field": "status", "value": "Open"},
        {"type": "create_task", "title": "Follow up", "due_days": 2},
        {"type": "notification", "title": "Review required"},
        {
            "type": "email",
            "to_email": "sales@example.com",
            "subject": "Review required",
            "body": "Please review this record.",
        },
        {"type": "webhook", "integration_id": "integration-1"},
    ],
)
def test_workflow_accepts_each_supported_action(action):
    workflow = WorkflowCreate(
        name="Automation",
        module="leads",
        trigger="record.created",
        actions=[action],
    )
    assert workflow.actions[0].type == action["type"]


def test_workflow_rejects_unknown_action():
    with pytest.raises(ValidationError):
        WorkflowCreate(
            name="Automation",
            module="leads",
            trigger="record.created",
            actions=[{"type": "shell", "command": "unsafe"}],
        )


@pytest.mark.parametrize(
    ("schema", "payload"),
    [
        (WorkflowUpdate, {"actions": None}),
        (DashboardLayoutUpdate, {"widgets": None}),
        (TicketUpdate, {"status": None}),
        (KnowledgeArticleUpdate, {"slug": None}),
    ],
)
def test_patch_schemas_reject_null_for_nonnullable_fields(schema, payload):
    with pytest.raises(ValidationError):
        schema.model_validate(payload)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action",
    [
        {"type": "update_field", "field": "status", "value": "Contacted"},
        {"type": "assign", "user_id": "user-2"},
    ],
)
async def test_workflow_record_mutations_require_module_permission(monkeypatch, action):
    monkeypatch.setattr(AuthService, "get_user_permissions", AsyncMock(return_value=[]))
    with pytest.raises(ForbiddenError):
        await WorkflowService()._validate(AsyncMock(), object(), "leads", [action])


@pytest.mark.asyncio
async def test_workflow_rejects_null_update_field_value(monkeypatch):
    monkeypatch.setattr(
        AuthService, "get_user_permissions", AsyncMock(return_value=["projects:update"])
    )

    with pytest.raises(ConflictError, match="cannot be null"):
        await WorkflowService()._validate(
            AsyncMock(),
            object(),
            "projects",
            [{"type": "update_field", "field": "completion_percentage", "value": None}],
        )


@pytest.mark.asyncio
async def test_active_workflow_definition_edit_rebinds_execution_user():
    service = WorkflowService()
    workflow = SimpleNamespace(
        module="leads",
        actions=[{"type": "notification"}],
        conditions=[],
        trigger="record.created",
        is_active=True,
        activated_by="admin-1",
    )
    service.get = AsyncMock(return_value=workflow)
    service._validate = AsyncMock()
    db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    editor = SimpleNamespace(id="editor-1")

    await service.update(
        db,
        editor,
        "workflow-1",
        WorkflowUpdate(conditions=[{"field": "status", "operator": "equals", "value": "New"}]),
    )

    assert workflow.activated_by == "editor-1"


@pytest.mark.asyncio
async def test_workflow_lead_status_uses_domain_service(monkeypatch):
    update_lead = AsyncMock()
    monkeypatch.setattr("app.services.lead_service.lead_service.update_lead", update_lead)
    db = AsyncMock()
    actor = SimpleNamespace(id="user-1")
    event = SimpleNamespace(module="leads", organization_id="org-1")
    entity = SimpleNamespace(id="lead-1")

    await WorkflowService()._update_field(
        db,
        actor,
        event,
        entity,
        {"type": "update_field", "field": "status", "value": "Contacted"},
    )

    update_lead.assert_awaited_once()
    assert update_lead.await_args.args[1] == "lead-1"
    assert update_lead.await_args.args[2].status == "Contacted"
    assert update_lead.await_args.args[3] is actor
    assert update_lead.await_args.kwargs == {"emit_workflow": False}


@pytest.mark.asyncio
async def test_failed_workflow_run_discards_uncommitted_action_progress():
    service = WorkflowService()
    run = SimpleNamespace(
        status="Running",
        action_results=[{"action_index": 0, "status": "completed"}],
        error=None,
        finished_at=None,
    )
    db = SimpleNamespace(commit=AsyncMock(), add=MagicMock())

    await service._record_failed_run(
        db,
        "event-1",
        "workflow-1",
        run,
        "RuntimeError",
        results=[],
    )

    assert run.status == "Failed"
    assert run.action_results == []
    assert run.error == "RuntimeError"


@pytest.mark.asyncio
async def test_internal_ticket_comment_does_not_satisfy_first_response_sla():
    service = SupportService()
    ticket = SimpleNamespace(id="ticket-1", first_responded_at=None)
    service.ticket = AsyncMock(return_value=ticket)
    db = SimpleNamespace(add=MagicMock(), commit=AsyncMock(), refresh=AsyncMock())

    await service.add_comment(
        db,
        SimpleNamespace(id="user-1"),
        "ticket-1",
        TicketCommentCreate(body="Internal investigation", is_internal=True),
    )

    assert ticket.first_responded_at is None
