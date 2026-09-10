"""Durable inbox/outbox sweeper on the existing Celery deployment.

Sending leases never return to PENDING: Meta does not provide a safe resend
contract for an ambiguous network failure. Such sends require reconciliation.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from io import BytesIO
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.errors import APIException
from app.core.live_events import publish_live_event
from app.core.logging import get_logger
from app.core.whatsapp_security import (
    enforce_rate_limit,
    record_worker_heartbeat,
    service_window_open,
    whatsapp_sweep_lock,
)
from app.models.whatsapp import WhatsAppConversation as Conversation
from app.models.whatsapp import WhatsAppMessage as Message
from app.models.whatsapp import WhatsAppWebhookEvent as Event
from app.schemas.whatsapp import InboundEvent, StatusEvent
from app.services.ai_domain_service import ai_domain_service
from app.services.whatsapp_service import whatsapp_service as service
from app.workers.celery_app import celery_app
from app.workers.whatsapp_dispatch import enqueue_message

logger = get_logger(__name__)
DOWNLOADABLE_MEDIA_TYPES = frozenset({"image", "audio", "video", "document"})


@celery_app.task(
    name="app.workers.whatsapp.process_pending",
    ignore_result=True,
    soft_time_limit=240,
    time_limit=270,
)
def process_pending() -> None:
    if settings.WHATSAPP_ENABLED and not settings.ORGANIZATION_CLEANUP_ONLY:
        asyncio.run(sweep())


@celery_app.task(
    name="app.workers.whatsapp.process_webhook_event",
    ignore_result=True,
    soft_time_limit=240,
    time_limit=270,
)
def process_webhook_event(event_id: str, organization_id: str) -> None:
    if settings.WHATSAPP_ENABLED and not settings.ORGANIZATION_CLEANUP_ONLY:
        asyncio.run(run_targeted_event(event_id, organization_id))


@celery_app.task(
    name="app.workers.whatsapp.process_message",
    ignore_result=True,
    soft_time_limit=240,
    time_limit=270,
)
def process_whatsapp_message(message_id: str, organization_id: str) -> None:
    if settings.WHATSAPP_ENABLED and not settings.ORGANIZATION_CLEANUP_ONLY:
        asyncio.run(run_targeted_message(message_id, organization_id))


async def process_event(
    db,
    *,
    event_id: str | None = None,
    organization_id: str | None = None,
    queued_messages: list[tuple[str, str]] | None = None,
) -> bool:
    filters = [Event.status == "PENDING", Event.next_attempt_at <= datetime.now(UTC)]
    if event_id is not None:
        filters.extend((Event.id == event_id, Event.organization_id == organization_id))
    event = (
        await db.execute(
            select(Event)
            .where(*filters)
            .order_by(Event.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
    ).scalar_one_or_none()
    if event is None:
        return False
    config = await service.repository.configuration(db, event.organization_id)
    if config is None or config.id != event.integration_id:
        event.status = "FAILED"
        event.error_code = "INTEGRATION_MISSING"
    elif event.payload.get(
        "kind"
    ) == "message" and not await service.repository.organization_active(db, event.organization_id):
        if event.error_code != "ORGANIZATION_INACTIVE":
            service.audit(db, event.organization_id, "processing_suspended", event.id)
        event.error_code = "ORGANIZATION_INACTIVE"
        event.next_attempt_at = datetime.now(UTC) + timedelta(minutes=5)
    else:
        event.attempts += 1
        event.error_code = None
        try:
            if event.payload["kind"] == "message":
                result = await service.repository.persist_inbound(
                    db, config, InboundEvent.model_validate(event.payload["data"])
                )
                if result:
                    conversation, message = result
                    if queued_messages is not None:
                        queued_messages.append((message.id, config.organization_id))
                    logger.info(
                        "whatsapp.inbound_persisted",
                        extra={
                            "request_id": event.correlation_id,
                            "message_id": message.id,
                            "message_type": message.message_type,
                        },
                    )
                    await service.ensure_eligible_assignee(db, conversation, config)
                    text = (message.body or "").strip().lower()
                    identity = await service.repository.identity(db, conversation)
                    if text in {"stop", "unsubscribe", "stop messaging me", "do not contact me"}:
                        identity.consent = "OPTED_OUT"
                        identity.consent_updated_at = datetime.now(UTC)
                        conversation.ai_enabled = False
                        conversation.status = "HUMAN_HANDOFF"
                        message.work_status = "DONE"
                        service.audit(db, config.organization_id, "customer_opted_out", identity.id)
                        await service.notify(
                            db, conversation, "The customer opted out of WhatsApp communication."
                        )
                    needs_human = any(
                        term in text
                        for term in (
                            "speak to a human",
                            "speak with a sales representative",
                            "talk to an agent",
                            "human please",
                        )
                    )
                    if (
                        needs_human
                        or not identity.state.startswith("MATCHED")
                        or message.message_type != "text"
                    ):
                        conversation.ai_enabled = False
                        conversation.status = "HUMAN_HANDOFF"
                        if message.message_type not in DOWNLOADABLE_MEDIA_TYPES:
                            message.work_status = "DONE"
                        if (
                            needs_human
                            and identity.state.startswith("MATCHED")
                            and config.ai_user_id
                        ):
                            handoff_message_id = str(uuid4())
                            db.add(
                                Message(
                                    id=handoff_message_id,
                                    organization_id=config.organization_id,
                                    integration_id=config.id,
                                    conversation_id=conversation.id,
                                    idempotency_key="handoff_" + message.id,
                                    reply_to_message_id=message.id,
                                    direction="OUTBOUND",
                                    source="SYSTEM",
                                    message_type="text",
                                    body="I'll ask a team member to help with your request.",
                                    sender_phone=(
                                        config.display_phone_number or config.phone_number_id
                                    ),
                                    recipient_phone=identity.normalized_phone_number,
                                    actor_user_id=config.ai_user_id,
                                    status="PENDING",
                                    work_status="PENDING",
                                )
                            )
                            if queued_messages is not None:
                                queued_messages.append((handoff_message_id, config.organization_id))
                        service.audit(db, config.organization_id, "human_handoff", conversation.id)
                        await service.notify(
                            db, conversation, "A customer conversation requires human assistance."
                        )
                event.status = "DONE"
            else:
                done = await service.repository.apply_status(
                    db, config, StatusEvent.model_validate(event.payload["data"])
                )
                event.status = "DONE" if done else ("FAILED" if event.attempts >= 8 else "PENDING")
                event.next_attempt_at = datetime.now(UTC) + timedelta(
                    seconds=min(3600, 30 * 2**event.attempts)
                )
                if not done:
                    event.error_code = "UNMATCHED_PROVIDER_RECEIPT"
            if event.status in {"DONE", "FAILED"}:
                event.payload = {
                    "kind": event.payload.get("kind"),
                    "provider_event_id": event.payload.get("data", {}).get("id"),
                }
        except (ValueError, KeyError, OverflowError):
            event.status = "FAILED"
            event.error_code = "INVALID_PROVIDER_EVENT"
    await service.commit(db)
    logger.info(
        "whatsapp.webhook_processed",
        extra={"request_id": event.correlation_id, "event_status": event.status},
    )
    return True


async def process_message(
    factory,
    *,
    message_id: str | None = None,
    organization_id: str | None = None,
    queued_messages: list[tuple[str, str]] | None = None,
    scheduled_messages: list[tuple[str, str, int]] | None = None,
    processed_messages: list[tuple[str, str, str]] | None = None,
) -> bool:
    async with factory() as db:
        filters = [
            Message.work_status == "PENDING",
            Message.next_attempt_at <= datetime.now(UTC),
        ]
        if message_id is not None:
            filters.extend(
                (Message.id == message_id, Message.organization_id == organization_id)
            )
        message = (
            await db.execute(
                select(Message)
                .where(*filters)
                .order_by(Message.created_at, Message.id)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
        ).scalar_one_or_none()
        if message is None:
            return False
        message.work_status = "PROCESSING"
        message.claimed_at = datetime.now(UTC)
        message.attempts += 1
        if message.direction == "OUTBOUND":
            message.status = "PROCESSING"
        message_id, organization_id = message.id, message.organization_id
        if processed_messages is not None:
            processed_messages.append(
                (message.organization_id, message.conversation_id, message.id)
            )
        await service.commit(db)

    async with factory() as db:
        message = (
            await db.execute(
                select(Message).where(
                    Message.id == message_id, Message.organization_id == organization_id
                )
            )
        ).scalar_one()
        if message.direction == "OUTBOUND" and message.source == "AI":
            # AI send authorization re-matches the CRM phone later in this
            # transaction, so acquire the shared phone guard before row locks.
            await service.repository.lock_phone_guard(db, organization_id)
        # Lock the conversation at the final send boundary. Takeover and disconnect
        # cannot race a permission check and external transmission in this transaction.
        conversation = (
            await db.execute(
                select(Conversation)
                .where(
                    Conversation.id == message.conversation_id,
                    Conversation.organization_id == organization_id,
                )
                .with_for_update()
            )
        ).scalar_one()
        config = await service.repository.configuration(db, organization_id, lock=True)
        identity = await service.repository.identity(db, conversation)
        try:
            if not await service.repository.organization_active(db, organization_id):
                raise APIException(
                    message="Organization is unavailable.", code="WHATSAPP_ORGANIZATION_INACTIVE"
                )
            if config is None or not config.enabled or identity.consent == "OPTED_OUT":
                raise APIException(message="Sending is disabled.", code="WHATSAPP_SENDING_DISABLED")
            if (
                message.direction == "OUTBOUND"
                and await service.repository.has_pending_inbound_events(
                    db, organization_id, config.id
                )
            ):
                message.work_status = "PENDING"
                message.status = "PENDING"
                message.claimed_at = None
                message.attempts = max(0, message.attempts - 1)
                message.next_attempt_at = datetime.now(UTC) + timedelta(seconds=30)
                await service.commit(db)
                if scheduled_messages is not None:
                    scheduled_messages.append((message.id, organization_id, 30))
                return True
            if (
                message.direction == "OUTBOUND"
                and message.message_type != "template"
                and not service_window_open(conversation.last_customer_message_at)
            ):
                raise APIException(
                    message="An approved template is required.", code="WHATSAPP_TEMPLATE_REQUIRED"
                )
            if message.direction == "INBOUND":
                if message.message_type != "text":
                    if message.message_type not in DOWNLOADABLE_MEDIA_TYPES:
                        message.work_status = "DONE"
                        await service.commit(db)
                        return True
                    metadata = message.media_metadata or {}
                    media_id = metadata.get("id")
                    if not isinstance(media_id, str):
                        raise APIException(
                            message="Media metadata is invalid.", code="WHATSAPP_MEDIA_INVALID"
                        )
                    client = await service.provider(db, config)
                    content, content_type = await client.download_media(
                        media_id, metadata.get("sha256")
                    )
                    from app.services.s3_service import s3_service

                    key = f"organizations/{organization_id}/whatsapp/{message.id}"
                    try:
                        message.media_s3_key = await asyncio.to_thread(
                            s3_service.upload_file, BytesIO(content), key, content_type
                        )
                    except Exception as exc:
                        raise APIException(
                            message="WhatsApp media storage is temporarily unavailable.",
                            code="WHATSAPP_MEDIA_STORAGE_UNAVAILABLE",
                            status_code=503,
                        ) from exc
                    message.work_status = "DONE"
                    await service.commit(db)
                    return True
                if (
                    not conversation.ai_enabled
                    or conversation.status != "OPEN"
                    or not identity.state.startswith("MATCHED")
                ):
                    message.work_status = "DONE"
                    await service.commit(db)
                    return True
                user = await service.repository.user(db, organization_id, config.ai_user_id)
                if user is None:
                    raise APIException(
                        message="AI user unavailable.", code="WHATSAPP_AI_USER_INVALID"
                    )
                history = [
                    {"source": row.source, "body": (row.body or "")[:1000]}
                    for row in await service.repository.messages(db, conversation, limit=10)
                ]
                await enforce_rate_limit("ai:" + conversation.id, 5)
                # Existing AI runtime owns its credit/run transactions. Release row
                # locks before generation and re-check takeover state after it returns.
                await service.commit(db)
                logger.info(
                    "whatsapp.ai_processing_started",
                    extra={"request_id": message.id, "conversation_id": conversation.id},
                )
                reply, handoff, topic, query_plan = await ai_domain_service.whatsapp_customer_chat(
                    db,
                    current_user=user,
                    conversation_id=conversation.id,
                    message=message.body or "",
                    history=history,
                )
                logger.info(
                    "whatsapp.ai_processing_completed",
                    extra={
                        "request_id": message.id,
                        "conversation_id": conversation.id,
                        "handoff": handoff,
                        "topic": topic,
                    },
                )
                await db.refresh(conversation, with_for_update=True)
                await db.refresh(message, with_for_update=True)
                if (
                    message.work_status != "PROCESSING"
                    or not conversation.ai_enabled
                    or conversation.status != "OPEN"
                ):
                    message.work_status = "DONE"
                    await service.commit(db)
                    return True
                if handoff:
                    conversation.ai_enabled = False
                    conversation.status = "HUMAN_HANDOFF"
                    await service.ensure_eligible_assignee(db, conversation, config)
                    outbound_message_id = str(uuid4())
                    db.add(
                        Message(
                            id=outbound_message_id,
                            organization_id=organization_id,
                            integration_id=config.id,
                            conversation_id=conversation.id,
                            idempotency_key="handoff_" + message.id,
                            reply_to_message_id=message.id,
                            direction="OUTBOUND",
                            source="SYSTEM",
                            message_type="text",
                            body=reply,
                            ai_topic=topic,
                            ai_query_plan=query_plan,
                            sender_phone=config.display_phone_number or config.phone_number_id,
                            recipient_phone=identity.normalized_phone_number,
                            actor_user_id=user.id,
                            status="PENDING",
                            work_status="PENDING",
                        )
                    )
                    await service.notify(
                        db, conversation, "The AI could not safely complete this customer request."
                    )
                    service.audit(db, organization_id, "human_handoff", conversation.id)
                else:
                    outbound_message_id = str(uuid4())
                    db.add(
                        Message(
                            id=outbound_message_id,
                            organization_id=organization_id,
                            integration_id=config.id,
                            conversation_id=conversation.id,
                            idempotency_key="ai_" + message.id,
                            reply_to_message_id=message.id,
                            direction="OUTBOUND",
                            source="AI",
                            message_type="text",
                            body=reply,
                            ai_topic=topic,
                            ai_query_plan=query_plan,
                            sender_phone=config.display_phone_number or config.phone_number_id,
                            recipient_phone=identity.normalized_phone_number,
                            actor_user_id=user.id,
                            status="PENDING",
                            work_status="PENDING",
                        )
                    )
                if queued_messages is not None:
                    queued_messages.append((outbound_message_id, organization_id))
                message.work_status = "DONE"
            else:
                user = await service.repository.user(db, organization_id, message.actor_user_id)
                if user is None:
                    raise APIException(
                        message="Sender no longer authorized.", code="WHATSAPP_SENDER_INVALID"
                    )
                permissions = await service.permissions(db, user, "whatsapp:send")
                await service.repository.conversation(
                    db, organization_id, conversation.id, user.id, permissions
                )
                if message.source == "AI":
                    if (
                        not conversation.ai_enabled
                        or conversation.status != "OPEN"
                        or user.id != config.ai_user_id
                    ):
                        raise APIException(message="AI is disabled.", code="WHATSAPP_AI_DISABLED")
                    await service.permissions(db, user, "ai:generate")
                    state, contact_id, lead_id = await service.repository.match(
                        db, config, identity.normalized_phone_number
                    )
                    if not state.startswith("MATCHED") or (contact_id, lead_id) != (
                        identity.contact_id,
                        identity.lead_id,
                    ):
                        raise APIException(
                            message="Identity changed.", code="WHATSAPP_IDENTITY_CHANGED"
                        )
                    if message.ai_topic and message.ai_topic != "greeting":
                        if (
                            getattr(message, "ai_query_plan", None)
                            and identity.state == "MATCHED_CONTACT"
                        ):
                            from app.schemas.whatsapp import CustomerAIPlan
                            from app.services.customer_crm_context_service import (
                                customer_crm_context_service,
                            )

                            try:
                                plan = CustomerAIPlan.model_validate(message.ai_query_plan)
                            except ValueError:
                                try:
                                    plan = CustomerAIPlan(topic=message.ai_topic)
                                except ValueError as exc:
                                    raise APIException(
                                        message="Stored AI query plan is invalid.",
                                        code="WHATSAPP_AI_PLAN_INVALID",
                                    ) from exc

                            current_answer = await customer_crm_context_service.answer(
                                db,
                                config,
                                identity,
                                permissions,
                                plan,
                            )
                        else:
                            current_answer = await service.repository.customer_answer(
                                db, config, identity, permissions, message.ai_topic
                            )
                        if current_answer is None:
                            raise APIException(
                                message="CRM authorization or data changed before sending.",
                                code="WHATSAPP_AI_AUTHORIZATION_CHANGED",
                            )
                        message.body = current_answer
                await enforce_rate_limit(
                    "outbound:" + organization_id, settings.WHATSAPP_SEND_RATE_PER_MINUTE
                )
                if not await service.repository.organization_active(db, organization_id):
                    raise APIException(
                        message="Organization is unavailable.",
                        code="WHATSAPP_ORGANIZATION_INACTIVE",
                    )
                client = await service.provider(db, config)
                logger.info(
                    "whatsapp.provider_send_started",
                    extra={
                        "request_id": message.id,
                        "message_type": message.message_type,
                    },
                )
                if message.message_type == "template":
                    template_data = message.template_payload or {}
                    template = await service.repository.template(
                        db, organization_id, str(template_data.get("template_id", ""))
                    )
                    parameters = template_data.get("parameters", [])
                    if (
                        template.status != "APPROVED"
                        or not isinstance(parameters, list)
                        or len(parameters) != template.body_parameter_count
                    ):
                        raise APIException(
                            message="Template is no longer sendable.",
                            code="WHATSAPP_TEMPLATE_INVALID",
                        )
                    if identity.consent == "OPTED_OUT" or (
                        template.category == "MARKETING" and identity.consent != "OPTED_IN"
                    ):
                        raise APIException(
                            message="Customer consent prohibits this template.",
                            code="WHATSAPP_CONSENT_REQUIRED",
                        )
                    provider_id = await client.send_template(
                        config.phone_number_id,
                        identity.normalized_phone_number,
                        template.name,
                        template.language,
                        parameters,
                        message.id,
                    )
                else:
                    provider_id = await client.send_text(
                        config.phone_number_id,
                        identity.normalized_phone_number,
                        message.body or "",
                        message.id,
                    )
                message.provider_message_id = provider_id
                message.status = "ACCEPTED"
                message.work_status = "DONE"
                logger.info(
                    "whatsapp.provider_send_accepted",
                    extra={"request_id": message.id, "message_status": message.status},
                )
                config.last_successful_message_at = datetime.now(UTC)
                conversation.last_message_at = datetime.now(UTC)
                service.audit(db, organization_id, "outbound_accepted", message.id, user.id)
        except APIException as exc:
            message.error_code = exc.code
            message.error_message = exc.message[:255]
            retryable_inbound = message.direction == "INBOUND" and exc.code in {
                "AI_PROVIDER_TIMEOUT",
                "AI_PROVIDER_CONNECTION_ERROR",
                "AI_PROVIDER_RATE_LIMITED",
                "AI_PROVIDER_UNAVAILABLE",
                "WHATSAPP_MEDIA_UNAVAILABLE",
                "WHATSAPP_MEDIA_STORAGE_UNAVAILABLE",
                "WHATSAPP_OUTCOME_UNKNOWN",
                "WHATSAPP_RATE_LIMITED",
                "WHATSAPP_RATE_LIMIT_UNAVAILABLE",
            }
            retryable_outbound = message.direction == "OUTBOUND" and exc.code in {
                "WHATSAPP_RATE_LIMITED",
                "WHATSAPP_RATE_LIMIT_UNAVAILABLE",
                "WHATSAPP_PROVIDER_RATE_LIMITED",
            }
            if (retryable_inbound or retryable_outbound) and message.attempts < 3:
                message.work_status = "PENDING"
                if message.direction == "OUTBOUND":
                    message.status = "PENDING"
                retry_after = (exc.fields or {}).get("retry_after_seconds")
                delay_seconds = (
                    retry_after
                    if isinstance(retry_after, int)
                    else 30 * 2 ** (message.attempts - 1)
                )
                message.next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay_seconds)
                await service.commit(db)
                if scheduled_messages is not None:
                    scheduled_messages.append(
                        (message.id, organization_id, max(1, delay_seconds))
                    )
                logger.warning(
                    "whatsapp.message_retry_scheduled",
                    extra={"request_id": message.id, "error_code": exc.code},
                )
                return True
            message.work_status = "FAILED"
            if message.direction == "OUTBOUND":
                message.status = "UNKNOWN" if exc.code == "WHATSAPP_OUTCOME_UNKNOWN" else "FAILED"
                if message.status == "FAILED":
                    message.failed_at = datetime.now(UTC)
            else:
                conversation.ai_enabled = False
                conversation.status = "HUMAN_HANDOFF"
            await service.notify(
                db,
                conversation,
                "WhatsApp processing failed. Review this conversation before retrying.",
            )
            service.audit(db, organization_id, "processing_failed", message.id)
        await service.commit(db)
        logger.info(
            "whatsapp.message_processed",
            extra={"request_id": message.id, "message_status": message.status},
        )
        return True


async def recover_interrupted(db) -> None:
    stale = datetime.now(UTC) - timedelta(minutes=10)
    stale_messages = list(
        (
            await db.execute(
                select(Message)
                .where(Message.work_status == "PROCESSING", Message.claimed_at < stale)
                .with_for_update(skip_locked=True)
            )
        )
        .scalars()
        .all()
    )
    for message in stale_messages:
        conversation = await db.scalar(
            select(Conversation).where(
                Conversation.id == message.conversation_id,
                Conversation.organization_id == message.organization_id,
            )
        )
        if message.direction == "INBOUND" and message.attempts < 3:
            message.work_status = "PENDING"
            message.next_attempt_at = datetime.now(UTC)
            message.error_code = "AI_WORKER_INTERRUPTED_RETRY"
            continue
        message.work_status = "FAILED"
        message.error_code = (
            "WORKER_INTERRUPTED" if message.direction == "OUTBOUND" else "AI_WORKER_INTERRUPTED"
        )
        if conversation is not None:
            if message.direction == "OUTBOUND":
                message.status = "UNKNOWN"
            else:
                conversation.ai_enabled = False
                conversation.status = "HUMAN_HANDOFF"
            await service.notify(
                db,
                conversation,
                "WhatsApp processing was interrupted and requires attention.",
            )
            service.audit(db, message.organization_id, "worker_interrupted", message.id)
    await service.commit(db)


async def _dispatch_follow_up_messages(messages: list[tuple[str, str]]) -> None:
    for message_id, organization_id in messages:
        await asyncio.to_thread(enqueue_message, message_id, organization_id)


async def _dispatch_scheduled_messages(messages: list[tuple[str, str, int]]) -> None:
    for message_id, organization_id, delay_seconds in messages:
        await asyncio.to_thread(
            enqueue_message,
            message_id,
            organization_id,
            delay_seconds=delay_seconds,
        )


async def run_targeted_event(event_id: str, organization_id: str) -> None:
    engine = create_async_engine(settings.DATABASE_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    queued_messages: list[tuple[str, str]] = []
    try:
        await record_worker_heartbeat()
        async with factory() as db:
            processed = await process_event(
                db,
                event_id=event_id,
                organization_id=organization_id,
                queued_messages=queued_messages,
            )
        if processed:
            await publish_live_event(organization_id)
            await _dispatch_follow_up_messages(queued_messages)
        await record_worker_heartbeat()
    finally:
        await engine.dispose()


async def run_targeted_message(message_id: str, organization_id: str) -> None:
    engine = create_async_engine(settings.DATABASE_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    queued_messages: list[tuple[str, str]] = []
    scheduled_messages: list[tuple[str, str, int]] = []
    processed_messages: list[tuple[str, str, str]] = []
    try:
        await record_worker_heartbeat()
        processed = await process_message(
            factory,
            message_id=message_id,
            organization_id=organization_id,
            queued_messages=queued_messages,
            scheduled_messages=scheduled_messages,
            processed_messages=processed_messages,
        )
        if processed:
            for org_id, conversation_id, processed_id in processed_messages:
                await publish_live_event(
                    org_id, conversation_id=conversation_id, message_id=processed_id
                )
            await _dispatch_follow_up_messages(queued_messages)
            await _dispatch_scheduled_messages(scheduled_messages)
        await record_worker_heartbeat()
    finally:
        await engine.dispose()


async def sweep() -> None:
    async with whatsapp_sweep_lock() as acquired:
        if not acquired:
            logger.info("whatsapp.sweep_skipped_locked")
            return
        engine = create_async_engine(settings.DATABASE_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        queued_messages: list[tuple[str, str]] = []
        scheduled_messages: list[tuple[str, str, int]] = []
        processed_messages: list[tuple[str, str, str]] = []
        try:
            await record_worker_heartbeat()
            async with factory() as db:
                await recover_interrupted(db)
            async with factory() as db:
                if await service.repository.repair_phone_batch(db):
                    await service.commit(db)
            async with factory() as db:
                config = await service.repository.next_phone_backfill_configuration(db)
                if config is not None:
                    await service.repository.backfill_phone_batch(db, config)
                    await service.commit(db)
            for _ in range(50):
                async with factory() as db:
                    if not await process_event(db, queued_messages=queued_messages):
                        break
            for _ in range(10):
                if not await process_message(
                    factory,
                    queued_messages=queued_messages,
                    scheduled_messages=scheduled_messages,
                    processed_messages=processed_messages,
                ):
                    break
            for org_id, conversation_id, processed_id in processed_messages:
                await publish_live_event(
                    org_id, conversation_id=conversation_id, message_id=processed_id
                )
            await _dispatch_follow_up_messages(queued_messages)
            await _dispatch_scheduled_messages(scheduled_messages)
            await record_worker_heartbeat()
        finally:
            await engine.dispose()
