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


@pytest.mark.asyncio
async def test_verified_whatsapp_contact_resolves_email_history_by_contact():
    whatsapp_repository = SimpleNamespace(
        match=AsyncMock(return_value=("MATCHED_CONTACT", "contact-a", None))
    )
    email_repository = SimpleNamespace(
        list_for_contact=AsyncMock(
            return_value=[
                SimpleNamespace(
                    subject="Quote QUO-2026-000014",
                    from_email="sales@example.test",
                    to_email="customer@example.test",
                    sent_at=SimpleNamespace(isoformat=lambda: "2026-09-07T10:00:00+00:00"),
                    created_at=None,
                )
            ]
        ),
        count_for_contact=AsyncMock(return_value=1),
    )
    service = CustomerCRMContextService(
        whatsapp_repository=whatsapp_repository,
        email_repository=email_repository,
    )
    db = SimpleNamespace(scalar=AsyncMock(return_value="customer@example.test"))

    answer = await service.answer(
        db,
        SimpleNamespace(organization_id="org-a"),
        SimpleNamespace(normalized_phone_number="+14155552671", contact_id="contact-a"),
        {"contacts:read", "emails:read"},
        CustomerAIPlan(topic="email"),
    )

    assert answer is not None
    assert "Quote QUO-2026-000014" in answer
    email_repository.list_for_contact.assert_awaited_once_with(
        db,
        organization_id="org-a",
        contact_id="contact-a",
        recipient_email="customer@example.test",
        limit=3,
        statuses=["Sent"],
        search=None,
    )


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
async def test_email_context_uses_shared_contact_history_and_reports_truncation():
    rows = [
        SimpleNamespace(
            subject=f"Quote QUO-{number}",
            from_email="sales@example.test",
            to_email="customer@example.test",
            sent_at=None,
            created_at=SimpleNamespace(isoformat=lambda: "2026-09-07T10:00:00+00:00"),
        )
        for number in range(1, 4)
    ]
    email_repository = SimpleNamespace(
        list_for_contact=AsyncMock(return_value=rows),
        count_for_contact=AsyncMock(return_value=6),
    )
    service = CustomerCRMContextService(email_repository=email_repository)
    db = AsyncMock()

    answer = await service._render_source(
        db,
        organization_id="org-a",
        contact_id="contact-a",
        contact_email="customer@example.test",
        source="email",
        plan=CustomerAIPlan(topic="email"),
    )

    assert answer is not None
    assert "You have 6 CRM emails sent to you. Here are the 3 most recent:" in answer
    assert "Quote QUO-1" in answer
    email_repository.list_for_contact.assert_awaited_once_with(
        db,
        organization_id="org-a",
        contact_id="contact-a",
        recipient_email="customer@example.test",
        limit=3,
        statuses=["Sent"],
        search=None,
    )


@pytest.mark.asyncio
async def test_email_context_returns_customer_safe_empty_result():
    email_repository = SimpleNamespace(
        list_for_contact=AsyncMock(return_value=[]),
        count_for_contact=AsyncMock(return_value=0),
    )
    service = CustomerCRMContextService(email_repository=email_repository)

    answer = await service._render_source(
        AsyncMock(),
        organization_id="org-a",
        contact_id="contact-a",
        contact_email="customer@example.test",
        source="email",
        plan=CustomerAIPlan(topic="email"),
    )

    assert answer == "I couldn't find any matching emails in your CRM history."


@pytest.mark.asyncio
async def test_recent_meetings_and_tomorrow_tasks_apply_time_windows():
    db = SimpleNamespace(scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: [])))
    meeting_repository = SimpleNamespace(list_for_contact=AsyncMock(return_value=[]))
    service = CustomerCRMContextService(meeting_repository=meeting_repository)

    await service._render_source(
        db,
        organization_id="org-a",
        contact_id="contact-a",
        contact_email="customer@example.test",
        source="meeting",
        plan=CustomerAIPlan(topic="meeting", time_scope="recent"),
    )
    meeting_call = meeting_repository.list_for_contact.await_args.kwargs
    assert meeting_call["statuses"] is None
    assert meeting_call["start"] < meeting_call["end"]
    assert meeting_call["newest_first"] is True

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
