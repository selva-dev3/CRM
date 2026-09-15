from io import BytesIO
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import UploadFile
from sqlalchemy import func, select
from starlette.datastructures import Headers

from app.core.errors import ConflictError
from app.models import Document, Ticket, TicketComment, TicketStatusHistory
from app.schemas.support import TicketCommentCreate, TicketCreate, TicketUpdate
from app.services.document_service import DocumentService
from app.services.support_service import SupportService
from app.tests.integration.test_sales_quote_workflow import sales_database as sales_database


@pytest.mark.asyncio
async def test_customer_ticket_assignment_comment_attachment_resolution_and_reopen(
    sales_database, monkeypatch
):
    sessions, org, user, company, contact, *_ = sales_database
    service = SupportService()

    async with sessions() as db:
        ticket = await service.create_ticket(
            db,
            user,
            TicketCreate(
                subject="Production incident",
                description="Customer cannot complete checkout",
                priority="High",
                contact_id=contact.id,
                company_id=company.id,
            ),
        )
        ticket_id = ticket.id
        assert ticket.ticket_number.startswith("TKT-")
        assert ticket.status == "New"
        assert ticket.first_response_due_at is not None
        assert ticket.resolution_due_at is not None

        assigned = await service.update_ticket(
            db,
            user,
            ticket_id,
            TicketUpdate(),
            assignment={"assigned_to": user.id},
        )
        assert assigned.assigned_to == user.id

        comment = await service.add_comment(
            db,
            user,
            ticket_id,
            TicketCommentCreate(body="Customer confirmed the failure", is_internal=False),
        )
        assert comment.ticket_id == ticket_id
        assert assigned.first_responded_at is not None

    monkeypatch.setattr(
        "app.services.document_service.auth_service.get_user_permissions",
        AsyncMock(return_value=["tickets:read"]),
    )
    monkeypatch.setattr(
        "app.services.document_service.s3_service.upload_file",
        Mock(return_value=f"documents/{org.id}/evidence.txt"),
    )
    monkeypatch.setattr(
        "app.services.document_service.s3_service.generate_presigned_url",
        Mock(return_value="https://storage.example.test/evidence.txt"),
    )
    upload = UploadFile(
        filename="evidence.txt",
        file=BytesIO(b"support evidence"),
        headers=Headers({"content-type": "text/plain"}),
        size=16,
    )
    async with sessions() as db:
        document = await DocumentService().upload_document(
            db, upload, current_user=user, ticket_id=ticket_id
        )
        assert document["ticket_id"] == ticket_id

        resolved = await service.update_ticket(db, user, ticket_id, TicketUpdate(status="Resolved"))
        first_resolved_at = resolved.resolved_at
        assert first_resolved_at is not None

        reopened = await service.update_ticket(db, user, ticket_id, TicketUpdate(status="Open"))
        assert reopened.resolved_at is None
        assert reopened.closed_at is None

        resolved_again = await service.update_ticket(
            db, user, ticket_id, TicketUpdate(status="Resolved")
        )
        assert resolved_again.resolved_at is not None
        closed = await service.update_ticket(db, user, ticket_id, TicketUpdate(status="Closed"))
        assert closed.closed_at is not None
        with pytest.raises(ConflictError):
            await service.update_ticket(db, user, ticket_id, TicketUpdate(status="Resolved"))
        await db.rollback()

    async with sessions() as db:
        persisted = await db.get(Ticket, ticket_id)
        assert persisted is not None and persisted.status == "Closed"
        assert (
            await db.scalar(
                select(func.count())
                .select_from(TicketComment)
                .where(TicketComment.ticket_id == ticket_id)
            )
            == 1
        )
        assert (
            await db.scalar(
                select(func.count()).select_from(Document).where(Document.ticket_id == ticket_id)
            )
            == 1
        )
        assert (
            await db.scalar(
                select(func.count())
                .select_from(TicketStatusHistory)
                .where(TicketStatusHistory.ticket_id == ticket_id)
            )
            == 5
        )
