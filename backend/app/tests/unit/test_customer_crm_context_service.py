import typing
from unittest.mock import AsyncMock

import pytest

from app.schemas.whatsapp import CustomerAIPlan
from app.services.customer_crm_context_service import CustomerCRMContextService
from app.tests.mock_helpers import as_async_mock, loose_fixture, replace_attr, require_await


@pytest.mark.asyncio
async def test_context_uses_revalidated_contact_id_for_each_requested_source():
    repository: typing.Any = loose_fixture(
        match=AsyncMock(return_value=("MATCHED_CONTACT", "contact-a", None))
    )
    service = CustomerCRMContextService(whatsapp_repository=repository)
    replace_attr(service, "_render_source", AsyncMock(side_effect=["Deal data", "Meeting data"]))
    config: typing.Any = loose_fixture(organization_id="org-a")
    identity: typing.Any = loose_fixture(
        normalized_phone_number="+14155552671", contact_id="contact-a"
    )
    plan = CustomerAIPlan(topic="combined", sources=["deal", "meeting"])

    answer = await service.answer(
        AsyncMock(),
        config,
        identity,
        {"contacts:read", "deals:read", "meetings:read"},
        plan,
    )

    assert answer == "Deal data\n\nMeeting data"
    assert as_async_mock(service._render_source).await_count == 2
    assert all(
        call.kwargs["contact_id"] == "contact-a" and call.kwargs["organization_id"] == "org-a"
        for call in as_async_mock(service._render_source).await_args_list
    )


@pytest.mark.asyncio
async def test_context_rejects_changed_phone_contact_binding():
    repository: typing.Any = loose_fixture(
        match=AsyncMock(return_value=("MATCHED_CONTACT", "contact-b", None))
    )
    service = CustomerCRMContextService(whatsapp_repository=repository)
    replace_attr(service, "_render_source", AsyncMock())

    answer = await service.answer(
        AsyncMock(),
        loose_fixture(organization_id="org-a"),
        loose_fixture(normalized_phone_number="+14155552671", contact_id="contact-a"),
        {"contacts:read", "deals:read"},
        CustomerAIPlan(topic="deal"),
    )

    assert answer is None
    as_async_mock(service._render_source).assert_not_awaited()


@pytest.mark.asyncio
async def test_context_requires_permission_for_every_source():
    repository: typing.Any = loose_fixture(
        match=AsyncMock(return_value=("MATCHED_CONTACT", "contact-a", None))
    )
    service = CustomerCRMContextService(whatsapp_repository=repository)
    replace_attr(service, "_render_source", AsyncMock())

    answer = await service.answer(
        AsyncMock(),
        loose_fixture(organization_id="org-a"),
        loose_fixture(normalized_phone_number="+14155552671", contact_id="contact-a"),
        {"contacts:read", "deals:read"},
        CustomerAIPlan(topic="combined", sources=["deal", "invoice"]),
    )

    assert answer is None
    as_async_mock(service._render_source).assert_not_awaited()


@pytest.mark.asyncio
async def test_verified_whatsapp_contact_resolves_email_history_by_contact():
    whatsapp_repository: typing.Any = loose_fixture(
        match=AsyncMock(return_value=("MATCHED_CONTACT", "contact-a", None))
    )
    email_repository: typing.Any = loose_fixture(
        list_for_contact=AsyncMock(
            return_value=[
                loose_fixture(
                    subject="Quote QUO-2026-000014",
                    from_email="sales@example.test",
                    to_email="customer@example.test",
                    sent_at=loose_fixture(isoformat=lambda: "2026-09-07T10:00:00+00:00"),
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
    db: typing.Any = loose_fixture(scalar=AsyncMock(return_value="customer@example.test"))

    answer = await service.answer(
        db,
        loose_fixture(organization_id="org-a"),
        loose_fixture(normalized_phone_number="+14155552671", contact_id="contact-a"),
        {"contacts:read", "emails:read"},
        CustomerAIPlan(topic="email"),
    )

    assert answer is not None
    assert "Quote QUO-2026-000014" in answer
    as_async_mock(email_repository.list_for_contact).assert_awaited_once_with(
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
        loose_fixture(
            subject=f"Quote QUO-{number}",
            from_email="sales@example.test",
            to_email="customer@example.test",
            sent_at=None,
            created_at=loose_fixture(isoformat=lambda: "2026-09-07T10:00:00+00:00"),
        )
        for number in range(1, 4)
    ]
    email_repository: typing.Any = loose_fixture(
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
    as_async_mock(email_repository.list_for_contact).assert_awaited_once_with(
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
    email_repository: typing.Any = loose_fixture(
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
    db: typing.Any = loose_fixture(scalars=AsyncMock(return_value=loose_fixture(all=lambda: [])))
    meeting_repository: typing.Any = loose_fixture(list_for_contact=AsyncMock(return_value=[]))
    service = CustomerCRMContextService(meeting_repository=meeting_repository)

    await service._render_source(
        db,
        organization_id="org-a",
        contact_id="contact-a",
        contact_email="customer@example.test",
        source="meeting",
        plan=CustomerAIPlan(topic="meeting", time_scope="recent"),
    )
    meeting_call = require_await(meeting_repository.list_for_contact).kwargs
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
    task_statement = str(require_await(db.scalars).args[0])
    assert "tasks.due_date >=" in task_statement
    assert "tasks.due_date <" in task_statement


@pytest.mark.asyncio
async def test_context_caps_long_whatsapp_answers():
    repository: typing.Any = loose_fixture(
        match=AsyncMock(return_value=("MATCHED_CONTACT", "contact-a", None))
    )
    service = CustomerCRMContextService(whatsapp_repository=repository)
    replace_attr(service, "_render_source", AsyncMock(return_value="x" * 2100))

    answer = await service.answer(
        AsyncMock(),
        loose_fixture(organization_id="org-a"),
        loose_fixture(normalized_phone_number="+14155552671", contact_id="contact-a"),
        {"contacts:read", "deals:read"},
        CustomerAIPlan(topic="deal"),
    )

    assert answer is not None
    assert len(answer) == 1900
    assert answer.endswith("...")
