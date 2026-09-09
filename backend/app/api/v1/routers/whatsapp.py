"""Public provider webhooks and session-only CRM channel endpoints."""

import hmac
from uuid import uuid4

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import PlainTextResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import require_user_session
from app.core.config import settings
from app.core.errors import APIException, ForbiddenError
from app.core.logging import get_logger
from app.core.whatsapp_security import enforce_rate_limit, verify_signature
from app.db.session import get_db
from app.models import User
from app.schemas.whatsapp import (
    AssigneeRead,
    ConversationRead,
    ConversationReadWrite,
    ConversationWrite,
    IdentityConsent,
    IdentityResolve,
    IntegrationRead,
    IntegrationWrite,
    MessageRead,
    MessageWrite,
    TemplateMessageWrite,
    TemplateRead,
    WebhookPayload,
    WhatsAppAck,
)
from app.services.whatsapp_service import whatsapp_service as service

router = APIRouter()
logger = get_logger(__name__)


@router.get("/webhook", response_class=PlainTextResponse)
async def verify_webhook(
    mode: str = Query(alias="hub.mode", max_length=30),
    token: str = Query(alias="hub.verify_token", max_length=4096),
    challenge: str = Query(alias="hub.challenge", min_length=1, max_length=1000),
) -> str:
    service.available()
    await enforce_rate_limit("verification", 60)
    expected = settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN
    if (
        mode != "subscribe"
        or not expected
        or not hmac.compare_digest(token.encode(), expected.encode())
    ):
        raise ForbiddenError(message="Webhook verification failed.")
    return challenge


@router.post("/webhook", status_code=204)
async def receive_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> Response:
    service.available()
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > settings.WHATSAPP_WEBHOOK_MAX_BYTES:
            raise APIException(message="Webhook payload too large.", status_code=413)
        body.extend(chunk)
    correlation_id = str(uuid4())
    try:
        verify_signature(
            bytes(body), request.headers.get("x-hub-signature-256"), settings.WHATSAPP_APP_SECRET
        )
    except ForbiddenError:
        logger.warning("whatsapp.webhook_rejected", extra={"request_id": correlation_id})
        raise
    await enforce_rate_limit("webhook", settings.WHATSAPP_WEBHOOK_RATE_PER_MINUTE)
    try:
        payload = WebhookPayload.model_validate_json(body)
    except ValidationError as exc:
        raise APIException(
            message="Invalid WhatsApp webhook payload.",
            code="WHATSAPP_INVALID_WEBHOOK",
            status_code=400,
        ) from exc
    result = await service.ingest_webhook(db, payload, correlation_id)
    await service.commit(db)
    # DB inbox + existing beat sweep means queue outages cannot lose an ACKed event.
    logger.info(
        "whatsapp.webhook_received",
        extra={
            "request_id": correlation_id,
            "matched_changes": result.matched_changes,
            "unmatched_changes": result.unmatched_changes,
            "inserted_messages": result.inserted_messages,
            "inserted_statuses": result.inserted_statuses,
            "duplicate_events": result.duplicate_events,
        },
    )
    if result.unmatched_changes:
        logger.warning(
            "whatsapp.webhook_integration_unmatched",
            extra={
                "request_id": correlation_id,
                "unmatched_changes": result.unmatched_changes,
            },
        )
    return Response(status_code=204)


@router.get("/status", response_model=IntegrationRead)
async def integration_status(
    db: AsyncSession = Depends(get_db), user: User = Depends(require_user_session)
):
    return await service.status(db, user)


@router.post("/integration", response_model=IntegrationRead)
@router.patch("/integration", response_model=IntegrationRead)
async def configure_integration(
    payload: IntegrationWrite,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user_session),
):
    return await service.configure(db, user, payload)


@router.post("/integration/verify", response_model=IntegrationRead)
async def verify_integration(
    db: AsyncSession = Depends(get_db), user: User = Depends(require_user_session)
):
    return await service.verify(db, user)


@router.post("/integration/normalize-phones", response_model=IntegrationRead)
async def normalize_phones(
    db: AsyncSession = Depends(get_db), user: User = Depends(require_user_session)
):
    return await service.backfill(db, user)


@router.delete("/integration", response_model=WhatsAppAck)
async def disconnect_integration(
    db: AsyncSession = Depends(get_db), user: User = Depends(require_user_session)
) -> WhatsAppAck:
    await service.disconnect(db, user)
    return WhatsAppAck(message="WhatsApp disconnected; history retained.")


@router.get("/templates", response_model=list[TemplateRead])
async def list_templates(
    db: AsyncSession = Depends(get_db), user: User = Depends(require_user_session)
):
    return await service.templates(db, user)


@router.post("/templates/sync", response_model=list[TemplateRead])
async def sync_templates(
    db: AsyncSession = Depends(get_db), user: User = Depends(require_user_session)
):
    return await service.sync_templates(db, user)


@router.get("/conversations", response_model=list[ConversationRead])
async def list_conversations(
    search: str = Query(default="", max_length=64),
    offset: int = Query(default=0, ge=0, le=10000),
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user_session),
):
    return await service.conversations(db, user, search, offset, limit)


@router.get("/assignees", response_model=list[AssigneeRead])
async def list_assignees(
    db: AsyncSession = Depends(get_db), user: User = Depends(require_user_session)
):
    return await service.assignees(db, user)


@router.get("/conversations/{conversation_id}", response_model=ConversationRead)
async def conversation_detail(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user_session),
):
    return await service.conversation_payload(db, user, conversation_id)


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageRead])
async def message_history(
    conversation_id: str,
    offset: int = Query(default=0, ge=0, le=100000),
    limit: int = Query(default=100, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user_session),
):
    return await service.message_history(db, user, conversation_id, offset, limit)


@router.get("/conversations/{conversation_id}/messages/{message_id}/media")
async def download_media(
    conversation_id: str,
    message_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user_session),
):
    return RedirectResponse(
        await service.media_url(db, user, conversation_id, message_id), status_code=307
    )


@router.post(
    "/conversations/{conversation_id}/messages", response_model=MessageRead, status_code=202
)
async def send_message(
    conversation_id: str,
    payload: MessageWrite,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user_session),
):
    return await service.send(db, user, conversation_id, payload)


@router.post(
    "/conversations/{conversation_id}/template-messages",
    response_model=MessageRead,
    status_code=202,
)
async def send_template_message(
    conversation_id: str,
    payload: TemplateMessageWrite,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user_session),
):
    return await service.send_template(db, user, conversation_id, payload)


@router.post(
    "/conversations/{conversation_id}/messages/{message_id}/retry",
    response_model=MessageRead,
    status_code=202,
)
async def retry_failed_message(
    conversation_id: str,
    message_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user_session),
):
    return await service.retry_failed_message(db, user, conversation_id, message_id)


@router.patch("/conversations/{conversation_id}", response_model=ConversationRead)
async def update_conversation(
    conversation_id: str,
    payload: ConversationWrite,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user_session),
):
    await service.update(db, user, conversation_id, payload)
    return await service.conversation_payload(db, user, conversation_id)


@router.post("/conversations/{conversation_id}/takeover", response_model=ConversationRead)
async def takeover(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user_session),
):
    await service.takeover(db, user, conversation_id)
    return await service.conversation_payload(db, user, conversation_id)


@router.post("/conversations/{conversation_id}/read", response_model=WhatsAppAck)
async def mark_read(
    conversation_id: str,
    payload: ConversationReadWrite,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user_session),
) -> WhatsAppAck:
    await service.mark_read(db, user, conversation_id, payload.message_id)
    return WhatsAppAck(message="Conversation marked as read.")


@router.post("/identities/{identity_id}/resolve", response_model=WhatsAppAck)
async def resolve_identity(
    identity_id: str,
    payload: IdentityResolve,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user_session),
) -> WhatsAppAck:
    await service.resolve(db, user, identity_id, payload)
    return WhatsAppAck(message="Identity verified.")


@router.patch("/identities/{identity_id}/consent", response_model=WhatsAppAck)
async def update_consent(
    identity_id: str,
    payload: IdentityConsent,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user_session),
) -> WhatsAppAck:
    await service.set_consent(db, user, identity_id, payload.consent)
    return WhatsAppAck(message="Communication preference updated.")
