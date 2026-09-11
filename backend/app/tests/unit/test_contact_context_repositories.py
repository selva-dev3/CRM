from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.repositories.call_repository import CallRepository
from app.repositories.email_repository import EmailRepository
from app.repositories.meeting_repository import MeetingRepository


def test_email_contact_query_keeps_only_unambiguous_legacy_fallback_scoped():
    statement = str(
        EmailRepository._for_contact_query(
            organization_id="org-a",
            contact_id="contact-a",
            recipient_email=" Customer@Example.Test ",
        )
    )

    assert "emails.organization_id" in statement
    assert "emails.contact_id" in statement
    assert "emails.contact_id IS NULL" in statement
    assert "lower(trim(emails.to_email))" in statement
    assert "count(contacts.id)" in statement
    assert "contacts.organization_id" in statement


@pytest.mark.asyncio
async def test_email_contact_history_applies_limit_offset_status_and_search():
    result = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))
    db = SimpleNamespace(execute=AsyncMock(return_value=result))

    await EmailRepository().list_for_contact(
        db,
        organization_id="org-a",
        contact_id="contact-a",
        recipient_email="customer@example.test",
        limit=5,
        offset=5,
        statuses=["Sent"],
        search="Quote",
    )

    statement = str(db.execute.await_args.args[0])
    assert "emails.status IN" in statement
    assert "lower(emails.subject) LIKE lower" in statement
    assert "LIMIT" in statement
    assert "OFFSET" in statement


@pytest.mark.asyncio
async def test_meeting_contact_history_allows_only_unambiguous_attendee_fallback():
    result = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))
    db = SimpleNamespace(execute=AsyncMock(return_value=result))

    await MeetingRepository().list_for_contact(
        db,
        organization_id="org-a",
        contact_id="contact-a",
        contact_email="customer@example.test",
        limit=3,
        statuses=["Scheduled"],
    )

    statement = str(db.execute.await_args.args[0])
    assert "meetings.organization_id" in statement
    assert "meetings.contact_id" in statement
    assert "meetings.contact_id IS NULL" in statement
    assert "meeting_attendees.email" in statement
    assert "count(contacts.id)" in statement
    assert "contacts.organization_id" in statement


@pytest.mark.asyncio
async def test_call_contact_history_applies_contact_scope_and_limit():
    result = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))
    db = SimpleNamespace(execute=AsyncMock(return_value=result))

    await CallRepository().list_by_contact(
        db,
        organization_id="org-a",
        contact_id="contact-a",
        limit=3,
        search="Follow-up",
    )

    statement = str(db.execute.await_args.args[0])
    assert "call_logs.organization_id" in statement
    assert "call_logs.contact_id" in statement
    assert "lower(call_logs.subject) LIKE lower" in statement
    assert "LIMIT" in statement
