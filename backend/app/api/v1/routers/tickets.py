import csv
import io

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models import User
from app.schemas.support import (
    KnowledgeArticleResponse,
    TicketArticleLinkCreate,
    TicketAssignmentUpdate,
    TicketCommentCreate,
    TicketCommentResponse,
    TicketCreate,
    TicketResponse,
    TicketUpdate,
)
from app.services.support_service import support_service

router = APIRouter()


@router.get(
    "",
    response_model=list[TicketResponse],
    dependencies=[Depends(require_permission("tickets:read"))],
)
async def list_tickets(
    response: Response,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = None,
    ticket_status: str | None = Query(None, alias="status"),
    priority: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows, total = await support_service.list_tickets(
        db, user, search, ticket_status, priority, page, limit
    )
    response.headers["X-Total-Count"] = str(total)
    return rows


@router.get("/export", dependencies=[Depends(require_permission("tickets:export"))])
async def export_tickets(
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    rows, _ = await support_service.list_tickets(db, user, None, None, None, 1, 10000)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Ticket", "Subject", "Status", "Priority", "Created"])
    for item in rows:
        writer.writerow(
            [
                item.ticket_number,
                item.subject,
                item.status,
                item.priority,
                item.created_at.isoformat(),
            ]
        )
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=tickets.csv"},
    )


@router.post(
    "",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("tickets:create"))],
)
async def create_ticket(
    payload: TicketCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await support_service.create_ticket(db, user, payload)


@router.get(
    "/{ticket_id}",
    response_model=TicketResponse,
    dependencies=[Depends(require_permission("tickets:read"))],
)
async def get_ticket(
    ticket_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    return await support_service.ticket(db, user, ticket_id)


@router.patch(
    "/{ticket_id}",
    response_model=TicketResponse,
    dependencies=[Depends(require_permission("tickets:update"))],
)
async def update_ticket(
    ticket_id: str,
    payload: TicketUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await support_service.update_ticket(db, user, ticket_id, payload)


@router.patch(
    "/{ticket_id}/assignment",
    response_model=TicketResponse,
    dependencies=[Depends(require_permission("tickets:assign"))],
)
async def assign_ticket(
    ticket_id: str,
    payload: TicketAssignmentUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await support_service.update_ticket(
        db, user, ticket_id, TicketUpdate(), assignment=payload.model_dump(exclude_unset=True)
    )


@router.delete(
    "/{ticket_id}", status_code=204, dependencies=[Depends(require_permission("tickets:delete"))]
)
async def archive_ticket(
    ticket_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    await support_service.archive_ticket(db, user, ticket_id)
    return Response(status_code=204)


@router.get(
    "/{ticket_id}/comments",
    response_model=list[TicketCommentResponse],
    dependencies=[Depends(require_permission("tickets:read"))],
)
async def list_comments(
    ticket_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    return await support_service.comments(db, user, ticket_id)


@router.post(
    "/{ticket_id}/comments",
    response_model=TicketCommentResponse,
    status_code=201,
    dependencies=[Depends(require_permission("tickets:update"))],
)
async def add_comment(
    ticket_id: str,
    payload: TicketCommentCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await support_service.add_comment(db, user, ticket_id, payload)


@router.get(
    "/{ticket_id}/knowledge-articles",
    response_model=list[KnowledgeArticleResponse],
    dependencies=[
        Depends(require_permission("tickets:read")),
        Depends(require_permission("knowledge_base:read")),
    ],
)
async def list_ticket_articles(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await support_service.ticket_articles(db, user, ticket_id)


@router.post(
    "/{ticket_id}/knowledge-articles",
    response_model=KnowledgeArticleResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(require_permission("tickets:update")),
        Depends(require_permission("knowledge_base:read")),
    ],
)
async def link_ticket_article(
    ticket_id: str,
    payload: TicketArticleLinkCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await support_service.link_ticket_article(db, user, ticket_id, payload.article_id)


@router.delete(
    "/{ticket_id}/knowledge-articles/{article_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("tickets:update"))],
)
async def unlink_ticket_article(
    ticket_id: str,
    article_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await support_service.unlink_ticket_article(db, user, ticket_id, article_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
