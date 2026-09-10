from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.schemas.whatsapp import CustomerAIPlan
from app.services.customer_crm_context_service import CustomerCRMContextService


@pytest.mark.asyncio
async def test_context_uses_revalidated_contact_id_for_each_requested_source():
    repository = SimpleNamespace(
        match=AsyncMock(return_value=("MATCHED_CONTACT", "contact-a", None))
    )
    service = CustomerCRMContextService(whatsapp_repository=repository)
    service._render_source = AsyncMock(side_effect=["Deal data", "Meeting data"])
    config = SimpleNamespace(organization_id="org-a")
    identity = SimpleNamespace(normalized_phone_number="+14155552671", contact_id="contact-a")
    plan = CustomerAIPlan(topic="combined", sources=["deal", "meeting"])

    answer = await service.answer(
        AsyncMock(),
        config,
        identity,
        {"contacts:read", "deals:read", "meetings:read"},
        plan,
    )

    assert answer == "Deal data\n\nMeeting data"
    assert service._render_source.await_count == 2
    assert all(
        call.kwargs["contact_id"] == "contact-a" and call.kwargs["organization_id"] == "org-a"
        for call in service._render_source.await_args_list
    )


@pytest.mark.asyncio
async def test_context_rejects_changed_phone_contact_binding():
    repository = SimpleNamespace(
        match=AsyncMock(return_value=("MATCHED_CONTACT", "contact-b", None))
    )
    service = CustomerCRMContextService(whatsapp_repository=repository)
    service._render_source = AsyncMock()

    answer = await service.answer(
        AsyncMock(),
        SimpleNamespace(organization_id="org-a"),
        SimpleNamespace(normalized_phone_number="+14155552671", contact_id="contact-a"),
        {"contacts:read", "deals:read"},
        CustomerAIPlan(topic="deal"),
    )

    assert answer is None
    service._render_source.assert_not_awaited()


@pytest.mark.asyncio
async def test_context_requires_permission_for_every_source():
    repository = SimpleNamespace(
        match=AsyncMock(return_value=("MATCHED_CONTACT", "contact-a", None))
    )
    service = CustomerCRMContextService(whatsapp_repository=repository)
    service._render_source = AsyncMock()

    answer = await service.answer(
        AsyncMock(),
        SimpleNamespace(organization_id="org-a"),
        SimpleNamespace(normalized_phone_number="+14155552671", contact_id="contact-a"),
        {"contacts:read", "deals:read"},
        CustomerAIPlan(topic="combined", sources=["deal", "invoice"]),
    )

    assert answer is None
    service._render_source.assert_not_awaited()


def test_customer_ai_plan_limits_sources_and_results():
    plan = CustomerAIPlan(
        topic="combined",
        sources=["contact", "deal", "meeting", "invoice"],
        reference="ABC",
        time_scope="tomorrow",
        limit=5,
    )

    assert plan.sources == ["contact", "deal", "meeting", "invoice"]
    assert plan.limit == 5


@pytest.mark.asyncio
async def test_email_context_requires_contact_and_recipient_email_match():
    db = SimpleNamespace(scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: [])))
    service = CustomerCRMContextService()

    await service._render_source(
        db,
        organization_id="org-a",
        contact_id="contact-a",
        source="email",
        plan=CustomerAIPlan(topic="email"),
    )

    statement = str(db.scalars.await_args.args[0])
    assert "JOIN contacts" in statement
    assert "lower(trim(emails.to_email)) = lower(trim(contacts.email))" in statement


@pytest.mark.asyncio
async def test_recent_meetings_and_tomorrow_tasks_apply_time_windows():
    db = SimpleNamespace(scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: [])))
    service = CustomerCRMContextService()

    await service._render_source(
        db,
        organization_id="org-a",
        contact_id="contact-a",
        source="meeting",
        plan=CustomerAIPlan(topic="meeting", time_scope="recent"),
    )
    meeting_statement = str(db.scalars.await_args.args[0])
    assert "meetings.start_time >=" in meeting_statement
    assert "meetings.start_time <" in meeting_statement
    assert "meetings.start_time DESC" in meeting_statement

    await service._render_source(
        db,
        organization_id="org-a",
        contact_id="contact-a",
        source="task",
        plan=CustomerAIPlan(topic="task", time_scope="tomorrow"),
    )
    task_statement = str(db.scalars.await_args.args[0])
    assert "tasks.due_date >=" in task_statement
    assert "tasks.due_date <" in task_statement


@pytest.mark.asyncio
async def test_context_caps_long_whatsapp_answers():
    repository = SimpleNamespace(
        match=AsyncMock(return_value=("MATCHED_CONTACT", "contact-a", None))
    )
    service = CustomerCRMContextService(whatsapp_repository=repository)
    service._render_source = AsyncMock(return_value="x" * 2100)

    answer = await service.answer(
        AsyncMock(),
        SimpleNamespace(organization_id="org-a"),
        SimpleNamespace(normalized_phone_number="+14155552671", contact_id="contact-a"),
        {"contacts:read", "deals:read"},
        CustomerAIPlan(topic="deal"),
    )

    assert answer is not None
    assert len(answer) == 1900
    assert answer.endswith("...")
