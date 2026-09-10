"""Authenticated WhatsApp operations, reusing CRM identity, RBAC and audit models."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIException, ConflictError, ForbiddenError, NotFoundError
from app.core.phone import normalize_phone
from app.core.whatsapp_security import enforce_rate_limit, service_window_open, worker_heartbeat
from app.models import Integration, User
from app.models.whatsapp import (
    WhatsAppConversation,
    WhatsAppIntegration,
    WhatsAppMessage,
)
from app.repositories.whatsapp_repository import WhatsAppRepository
from app.schemas.whatsapp import (
    ConversationWrite,
    IdentityResolve,
    IntegrationRead,
    IntegrationWrite,
    MessageWrite,
    TemplateMessageWrite,
    WebhookIngestResult,
    WebhookPayload,
)
from app.services.auth_service import auth_service
from app.services.integration_service import IntegrationService
from app.services.whatsapp_provider_service import WhatsAppProviderService


class WhatsAppService:
    PHONE_NUMBER_UNIQUE_CONSTRAINT = "whatsapp_integrations_phone_number_id_key"

    def __init__(self) -> None:
        self.repository = WhatsAppRepository()

    @staticmethod
    def available() -> None:
        if not settings.WHATSAPP_ENABLED:
            raise APIException(
                message="WhatsApp is disabled for this deployment.",
                code="WHATSAPP_DISABLED",
                status_code=503,
            )

    async def ingest_webhook(
        self, db: AsyncSession, payload: WebhookPayload, correlation_id: str
    ) -> WebhookIngestResult:
        return await self.repository.ingest(db, payload, correlation_id)

    @staticmethod
    async def commit(db: AsyncSession) -> None:
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise

    @staticmethod
    async def permissions(db: AsyncSession, user: User, required: str | None = None) -> set[str]:
        if not user.organization_id or not user.is_active:
            raise ForbiddenError(message="Select an active organization.")
        permissions = set(await auth_service.get_user_permissions(db, user))
        if required and required not in permissions:
            raise ForbiddenError(message="You do not have permission for this operation.")
        return permissions

    @staticmethod
    def account_revision(
        config: WhatsAppIntegration, catalog: Integration
    ) -> tuple[object, ...]:
        """Fields that make a provider response safe to apply to this account."""
        return (
            config.business_account_id,
            config.phone_number_id,
            config.api_version,
            config.enabled,
            config.default_assignee_id,
            config.ai_user_id,
            config.catalog_integration_id,
            getattr(config, "updated_at", None),
            getattr(catalog, "access_token", None),
            getattr(catalog, "updated_at", None),
        )

    async def lock_account_revision(
        self,
        db: AsyncSession,
        organization_id: str,
        expected: tuple[object, ...],
    ) -> tuple[WhatsAppIntegration, Integration]:
        config = await self.repository.configuration(db, organization_id, lock=True)
        if config is None:
            raise ConflictError(
                message="WhatsApp configuration changed during the operation. Try again.",
                code="WHATSAPP_CONFIGURATION_CHANGED",
            )
        catalog = await self.repository.catalog(db, config, lock=True)
        if self.account_revision(config, catalog) != expected:
            await db.rollback()
            raise ConflictError(
                message="WhatsApp configuration changed during the operation. Try again.",
                code="WHATSAPP_CONFIGURATION_CHANGED",
            )
        return config, catalog

    @classmethod
    def is_phone_number_collision(cls, exc: IntegrityError) -> bool:
        orig = exc.orig
        cause = getattr(orig, "__cause__", None)
        constraint_name = getattr(orig, "constraint_name", None) or getattr(
            cause, "constraint_name", None
        )
        return constraint_name == cls.PHONE_NUMBER_UNIQUE_CONSTRAINT

    def audit(
        self,
        db: AsyncSession,
        organization_id: str,
        action: str,
        entity_id: str,
        user_id: str | None = None,
    ) -> None:
        self.repository.add_audit(db, organization_id, action, entity_id, user_id)

    async def status(self, db: AsyncSession, user: User) -> IntegrationRead:
        permissions = await self.permissions(db, user)
        if not {"integrations:read", "integrations:manage"} & permissions:
            raise ForbiddenError(message="Integration access is not permitted.")
        config = await self.repository.configuration(db, user.organization_id)
        if not config:
            return IntegrationRead()
        catalog = await self.repository.catalog(db, config)
        worker_status, worker_last_seen_at = await worker_heartbeat()
        oldest_pending_at = await self.repository.oldest_pending_at(db, user.organization_id)
        backlog_age_seconds = (
            max(0, int((datetime.now(UTC) - oldest_pending_at).total_seconds()))
            if oldest_pending_at else 0
        )
        if config.last_webhook_at is None:
            webhook_status = "NOT_OBSERVED"
        elif datetime.now(UTC) - config.last_webhook_at > timedelta(hours=24):
            webhook_status = "STALE"
        else:
            webhook_status = "OBSERVED"
        ai_status = "NOT_CONFIGURED"
        if config.ai_user_id:
            ai_user = await self.repository.user(db, config.organization_id, config.ai_user_id)
            if ai_user is None:
                ai_status = "USER_INVALID"
            else:
                ai_permissions = set(await auth_service.get_user_permissions(db, ai_user))
                if not {"ai:generate", "whatsapp:send", "whatsapp:read_all"}.issubset(ai_permissions):
                    ai_status = "PERMISSION_MISSING"
                else:
                    from app.services.ai_runtime_service import ai_runtime_service

                    ai_status = await ai_runtime_service.configuration_readiness(
                        db, config.organization_id
                    )
        masked_phone_number = None
        if config.display_phone_number:
            digits = "".join(character for character in config.display_phone_number if character.isdigit())
            masked_phone_number = "••••" + digits[-4:] if len(digits) >= 4 else "••••"
        ready = bool(
            config.enabled
            and catalog.status == "connected"
            and config.phone_index_ready
            and webhook_status == "OBSERVED"
            and worker_status == "HEALTHY"
            and backlog_age_seconds < 300
            and ai_status == "READY"
        )
        return IntegrationRead(
            configured=True,
            enabled=config.enabled,
            phone_index_ready=config.phone_index_ready,
            status=catalog.status,
            masked_phone_number=masked_phone_number,
            webhook_status=webhook_status,
            worker_status=worker_status,
            worker_last_seen_at=worker_last_seen_at,
            backlog_age_seconds=backlog_age_seconds,
            ai_status=ai_status,
            ready=ready,
            **{
                k: getattr(config, k)
                for k in (
                    "business_account_id",
                    "phone_number_id",
                    "display_phone_number",
                    "verified_name",
                    "api_version",
                    "default_phone_region",
                    "last_webhook_at",
                    "last_successful_message_at",
                    "ai_user_id",
                    "default_assignee_id",
                )
            },
        )

    async def configure(
        self, db: AsyncSession, user: User, payload: IntegrationWrite
    ) -> IntegrationRead:
        self.available()
        await self.permissions(db, user, "integrations:manage")
        await enforce_rate_limit("configure:" + user.organization_id, 10)
        if settings.WHATSAPP_API_VERSION and payload.api_version != settings.WHATSAPP_API_VERSION:
            raise ConflictError(
                message="The API version must match the WhatsApp version configured for this deployment."
            )
        for user_id in (payload.ai_user_id, payload.default_assignee_id):
            if user_id and not await self.repository.user(db, user.organization_id, user_id):
                raise NotFoundError(message="User not found.")
        if payload.default_phone_region:
            import phonenumbers

            if payload.default_phone_region not in phonenumbers.SUPPORTED_REGIONS:
                raise APIException(message="Invalid ISO phone region.")
        config = await self.repository.configuration(db, user.organization_id, lock=True)
        created = config is None
        if config:
            if (
                config.phone_number_id != payload.phone_number_id
                or config.business_account_id != payload.business_account_id
            ):
                # The configuration row is locked above; webhook routing takes the
                # same lock before accepting events for this business identity.
                if (
                    config.enabled
                    or config.last_webhook_at is not None
                    or config.last_successful_message_at is not None
                    or await self.repository.has_account_records(db, config)
                ):
                    raise ConflictError(
                        message="Business identity cannot be changed for an active or previously used integration. An account migration is required."
                    )
                config.business_account_id = payload.business_account_id
                config.phone_number_id = payload.phone_number_id
                config.display_phone_number = None
                config.verified_name = None
                config.phone_index_ready = False
                config.phone_backfill_stage = "contacts"
                config.phone_backfill_cursor = None
                try:
                    await db.flush()
                except IntegrityError as exc:
                    await db.rollback()
                    if self.is_phone_number_collision(exc):
                        raise ConflictError(
                            message="This WhatsApp phone number is already connected to another organization.",
                            code="WHATSAPP_PHONE_ALREADY_CONNECTED",
                        ) from exc
                    raise
            catalog = await self.repository.catalog(db, config)
        else:
            try:
                catalog, config = await self.repository.create_configuration(
                    db,
                    user.organization_id,
                    payload.business_account_id,
                    payload.phone_number_id,
                    payload.api_version,
                )
            except IntegrityError as exc:
                await db.rollback()
                if self.is_phone_number_collision(exc):
                    raise ConflictError(
                        message="This WhatsApp phone number is already connected to another organization.",
                        code="WHATSAPP_PHONE_ALREADY_CONNECTED",
                    ) from exc
                raise
        catalog.access_token = IntegrationService._encrypt_secret(
            payload.access_token.get_secret_value()
        )
        catalog.is_connected = False
        catalog.status = "unverified"
        config.enabled = False  # Verification, not a checkbox, establishes connectivity.
        config.api_version = payload.api_version
        if config.default_phone_region != payload.default_phone_region:
            config.phone_index_ready = False
            config.phone_backfill_stage = "contacts"
            config.phone_backfill_cursor = None
        config.default_phone_region = payload.default_phone_region
        config.ai_user_id = payload.ai_user_id
        config.default_assignee_id = payload.default_assignee_id
        self.audit(
            db,
            user.organization_id,
            "integration_created" if created else "integration_updated",
            config.id,
            user.id,
        )
        try:
            await self.commit(db)
        except IntegrityError as exc:
            if self.is_phone_number_collision(exc):
                raise ConflictError(
                    message="This WhatsApp phone number is already connected to another organization.",
                    code="WHATSAPP_PHONE_ALREADY_CONNECTED",
                ) from exc
            raise
        if payload.enabled:
            await self.verify(db, user)
        return await self.status(db, user)

    async def provider(
        self, db: AsyncSession, config: WhatsAppIntegration
    ) -> WhatsAppProviderService:
        catalog = await self.repository.catalog(db, config)
        if not catalog.access_token or not catalog.access_token.startswith("enc:v1:"):
            raise APIException(
                message="WhatsApp credentials must be configured securely.",
                code="WHATSAPP_CREDENTIALS_INVALID",
            )
        token = IntegrationService._decrypt_secret(catalog.access_token)
        if not token:
            raise APIException(
                message="WhatsApp credentials are unavailable.", code="WHATSAPP_CREDENTIALS_INVALID"
            )
        return WhatsAppProviderService(token, config.api_version)

    async def verify(self, db: AsyncSession, user: User) -> IntegrationRead:
        self.available()
        await self.permissions(db, user, "integrations:manage")
        await enforce_rate_limit("verify:" + user.organization_id, 10)
        config = await self.repository.configuration(db, user.organization_id)
        if config is None:
            raise NotFoundError(message="WhatsApp integration not found.")
        catalog = await self.repository.catalog(db, config)
        account_revision = self.account_revision(config, catalog)
        default_assignee = await self.repository.user(
            db, user.organization_id, config.default_assignee_id
        )
        if not config.default_assignee_id or default_assignee is None:
            raise ConflictError(
                message="Select an active default assignee before enabling WhatsApp."
            )
        default_permissions = await self.permissions(db, default_assignee)
        if not {"whatsapp:read_assigned", "whatsapp:read_all"} & default_permissions:
            raise ConflictError(
                message="The default assignee must be permitted to read WhatsApp conversations."
            )
        if config.ai_user_id:
            ai_user = await self.repository.user(db, user.organization_id, config.ai_user_id)
            if ai_user is None:
                raise ConflictError(message="Select an active AI service user.")
            ai_permissions = await self.permissions(db, ai_user)
            required = {"ai:generate", "whatsapp:read_all", "whatsapp:send"}
            if not required.issubset(ai_permissions):
                raise ConflictError(
                    message="The AI service user requires AI generation plus organization-wide WhatsApp read and send permissions."
                )
        client = await self.provider(db, config)
        data = await client.request(
            "GET",
            f"{config.business_account_id}/phone_numbers",
            params={"fields": "id,display_phone_number,verified_name", "limit": 100},
        )
        numbers = data.get("data", [])
        number = next(
            (n for n in numbers if isinstance(n, dict) and n.get("id") == config.phone_number_id),
            None,
        )
        if not number:
            raise APIException(
                message="The configured phone does not belong to this business account.",
                code="WHATSAPP_PHONE_NOT_VERIFIED",
            )
        subscriptions = await client.request(
            "GET",
            f"{config.business_account_id}/subscribed_apps",
            params={"limit": 100},
        )
        subscribed_apps = subscriptions.get("data")
        if not isinstance(subscribed_apps, list):
            raise APIException(
                message="Invalid webhook subscription response from WhatsApp.",
                code="WHATSAPP_SUBSCRIPTION_INVALID",
                status_code=502,
            )
        app_subscribed = any(
            isinstance(item, dict)
            and (
                item.get("id") == settings.WHATSAPP_APP_ID
                or (
                    isinstance(item.get("whatsapp_business_api_data"), dict)
                    and item["whatsapp_business_api_data"].get("id")
                    == settings.WHATSAPP_APP_ID
                )
            )
            for item in subscribed_apps
        )
        if not app_subscribed:
            raise ConflictError(
                message="The configured Meta app is not subscribed to this WhatsApp business account.",
                code="WHATSAPP_WEBHOOK_NOT_SUBSCRIBED",
            )
        config, catalog = await self.lock_account_revision(
            db, config.organization_id, account_revision
        )
        config.display_phone_number = normalize_phone(number.get("display_phone_number", ""))
        config.verified_name = str(number.get("verified_name", ""))[:255]
        config.enabled = True
        catalog.status = "connected"
        catalog.is_connected = True
        self.audit(db, user.organization_id, "integration_verified", config.id, user.id)
        await self.commit(db)
        return await self.status(db, user)

    async def disconnect(self, db: AsyncSession, user: User) -> None:
        await self.permissions(db, user, "integrations:manage")
        config = await self.repository.configuration(db, user.organization_id, lock=True)
        if config is None:
            return
        catalog = await self.repository.catalog(db, config)
        catalog.access_token = None
        catalog.status = "disconnected"
        catalog.is_connected = False
        config.enabled = False
        self.audit(db, user.organization_id, "integration_disconnected", config.id, user.id)
        await self.commit(db)

    async def sync_templates(self, db: AsyncSession, user: User):
        self.available()
        await self.permissions(db, user, "integrations:manage")
        config = await self.repository.configuration(db, user.organization_id)
        if config is None or not config.enabled:
            raise ConflictError(message="Verify WhatsApp before syncing templates.")
        catalog = await self.repository.catalog(db, config)
        account_revision = self.account_revision(config, catalog)
        client = await self.provider(db, config)
        records: list[dict] = []
        after: str | None = None
        for _ in range(20):
            params = {
                "fields": "id,name,language,category,status,components",
                "limit": 250,
            }
            if after:
                params["after"] = after
            data = await client.request(
                "GET", f"{config.business_account_id}/message_templates", params=params
            )
            page = data.get("data")
            if not isinstance(page, list) or not all(isinstance(item, dict) for item in page):
                raise APIException(
                    message="Invalid template response from WhatsApp.", status_code=502
                )
            records.extend(page)
            paging = data.get("paging")
            cursors = paging.get("cursors") if isinstance(paging, dict) else None
            next_after = cursors.get("after") if isinstance(cursors, dict) else None
            has_next = isinstance(paging, dict) and isinstance(paging.get("next"), str)
            if not has_next:
                break
            if not isinstance(next_after, str) or not 1 <= len(next_after) <= 512:
                raise APIException(
                    message="Invalid template pagination response from WhatsApp.", status_code=502
                )
            after = next_after
        else:
            raise APIException(
                message="WhatsApp template synchronization exceeded the safe page limit.",
                status_code=502,
            )
        config, _ = await self.lock_account_revision(db, config.organization_id, account_revision)
        await self.repository.replace_templates(db, config, records)
        self.audit(db, user.organization_id, "templates_synced", config.id, user.id)
        await self.commit(db)
        return await self.repository.templates(db, user.organization_id)

    async def eligible_assignee(
        self, db: AsyncSession, organization_id: str, user_id: str | None
    ) -> User | None:
        candidate = await self.repository.user(db, organization_id, user_id)
        if candidate is None:
            return None
        permissions = await self.permissions(db, candidate)
        if not {"whatsapp:read_assigned", "whatsapp:read_all"} & permissions:
            return None
        return candidate

    async def ensure_eligible_assignee(
        self,
        db: AsyncSession,
        conversation: WhatsAppConversation,
        config: WhatsAppIntegration,
    ) -> User | None:
        assignee = await self.eligible_assignee(
            db, conversation.organization_id, conversation.assigned_user_id
        )
        if assignee is None:
            assignee = await self.eligible_assignee(
                db, conversation.organization_id, config.default_assignee_id
            )
            conversation.assigned_user_id = assignee.id if assignee else None
        return assignee

    async def assignees(self, db: AsyncSession, user: User) -> list[User]:
        await self.permissions(db, user, "whatsapp:assign")
        candidates = await self.repository.assignees(db, user.organization_id)
        permissions = await auth_service.get_users_permissions(db, candidates, user.organization_id)
        return [
            candidate
            for candidate in candidates
            if {"whatsapp:read_assigned", "whatsapp:read_all"} & permissions[candidate.id]
        ]

    async def templates(self, db: AsyncSession, user: User):
        await self.permissions(db, user, "whatsapp:send")
        return await self.repository.templates(db, user.organization_id)

    async def conversations(
        self, db: AsyncSession, user: User, search: str, offset: int, limit: int
    ) -> list[dict]:
        permissions = await self.permissions(db, user)
        if not {"whatsapp:read_all", "whatsapp:read_assigned"} & permissions:
            raise ForbiddenError(message="Conversation access is not permitted.")
        return await self.repository.list_conversations(
            db, user.organization_id, user.id, permissions, search, offset, limit
        )

    async def conversation_payload(
        self, db: AsyncSession, user: User, conversation_id: str
    ) -> dict:
        conversation = await self.conversation(db, user, conversation_id)
        identity = await self.repository.identity(db, conversation)
        return self.repository.conversation_dict(conversation, identity)

    async def message_history(
        self,
        db: AsyncSession,
        user: User,
        conversation_id: str,
        offset: int,
        limit: int,
    ) -> list[WhatsAppMessage]:
        conversation = await self.conversation(db, user, conversation_id)
        return await self.repository.messages(db, conversation, offset, limit)

    async def conversation(
        self,
        db: AsyncSession,
        user: User,
        conversation_id: str,
        *,
        required: str | None = None,
        lock: bool = False,
    ) -> WhatsAppConversation:
        permissions = await self.permissions(db, user, required)
        return await self.repository.conversation(
            db, user.organization_id, conversation_id, user.id, permissions, lock=lock
        )

    async def send(
        self, db: AsyncSession, user: User, conversation_id: str, payload: MessageWrite
    ) -> WhatsAppMessage:
        self.available()
        conversation = await self.conversation(
            db, user, conversation_id, required="whatsapp:send", lock=True
        )
        prior = await self.repository.message_by_idempotency(
            db, user.organization_id, conversation.integration_id, payload.idempotency_key
        )
        if prior:
            if (
                prior.conversation_id != conversation.id
                or prior.actor_user_id != user.id
                or prior.body != payload.body
            ):
                raise ConflictError(message="Idempotency key was already used for another request.")
            return prior
        config = await self.repository.configuration(db, user.organization_id)
        identity = await self.repository.identity(db, conversation)
        if config is None or not config.enabled:
            raise APIException(message="Connect WhatsApp before sending messages.")
        if identity.consent == "OPTED_OUT":
            raise ForbiddenError(message="This customer has opted out of WhatsApp communication.")
        if not service_window_open(conversation.last_customer_message_at):
            raise ConflictError(
                message="The customer-service window is closed. An approved template is required.",
                code="WHATSAPP_TEMPLATE_REQUIRED",
            )
        if not payload.body.strip():
            raise APIException(message="Message cannot be empty.")
        await enforce_rate_limit(
            "manual:" + user.organization_id, settings.WHATSAPP_SEND_RATE_PER_MINUTE
        )
        message = self.repository.create_message(
            db,
            id=str(uuid4()),
            organization_id=user.organization_id,
            integration_id=config.id,
            conversation_id=conversation.id,
            idempotency_key=payload.idempotency_key,
            direction="OUTBOUND",
            source="HUMAN",
            message_type="text",
            body=payload.body,
            sender_phone=config.display_phone_number or config.phone_number_id,
            recipient_phone=identity.normalized_phone_number,
            actor_user_id=user.id,
            status="PENDING",
            work_status="PENDING",
        )
        # Human messaging constitutes takeover; no simultaneous automatic reply.
        conversation.ai_enabled = False
        conversation.status = "HUMAN_HANDOFF"
        conversation.last_message_at = datetime.now(UTC)
        self.audit(db, user.organization_id, "outbound_queued", message.id, user.id)
        await self.commit(db)
        return message

    async def send_template(
        self, db: AsyncSession, user: User, conversation_id: str, payload: TemplateMessageWrite
    ) -> WhatsAppMessage:
        self.available()
        conversation = await self.conversation(
            db, user, conversation_id, required="whatsapp:send", lock=True
        )
        prior = await self.repository.message_by_idempotency(
            db, user.organization_id, conversation.integration_id, payload.idempotency_key
        )
        requested = {"template_id": payload.template_id, "parameters": payload.parameters}
        if prior:
            if prior.conversation_id != conversation.id or prior.template_payload != requested:
                raise ConflictError(message="Idempotency key was already used for another request.")
            return prior
        config = await self.repository.configuration(db, user.organization_id)
        identity = await self.repository.identity(db, conversation)
        template = await self.repository.template(db, user.organization_id, payload.template_id)
        if config is None or not config.enabled or template.integration_id != config.id:
            raise ConflictError(message="WhatsApp is not connected.")
        if template.status != "APPROVED":
            raise ConflictError(message="Only an approved WhatsApp template may be sent.")
        if len(payload.parameters) != template.body_parameter_count or any(
            not value.strip() or len(value) > 1024 for value in payload.parameters
        ):
            raise APIException(message="Template parameters do not match the approved template.")
        if identity.consent == "OPTED_OUT" or (
            template.category == "MARKETING" and identity.consent != "OPTED_IN"
        ):
            raise ForbiddenError(
                message="Customer communication preferences prohibit this template."
            )
        await enforce_rate_limit(
            "manual:" + user.organization_id, settings.WHATSAPP_SEND_RATE_PER_MINUTE
        )
        message = self.repository.create_message(
            db,
            id=str(uuid4()),
            organization_id=user.organization_id,
            integration_id=config.id,
            conversation_id=conversation.id,
            idempotency_key=payload.idempotency_key,
            direction="OUTBOUND",
            source="HUMAN",
            message_type="template",
            template_payload=requested,
            sender_phone=config.display_phone_number or config.phone_number_id,
            recipient_phone=identity.normalized_phone_number,
            actor_user_id=user.id,
            status="PENDING",
            work_status="PENDING",
        )
        conversation.ai_enabled = False
        conversation.status = "HUMAN_HANDOFF"
        self.audit(db, user.organization_id, "template_queued", message.id, user.id)
        await self.commit(db)
        return message

    async def retry_failed_message(
        self, db: AsyncSession, user: User, conversation_id: str, message_id: str
    ) -> WhatsAppMessage:
        self.available()
        conversation = await self.conversation(
            db, user, conversation_id, required="whatsapp:send", lock=True
        )
        message = await self.repository.message(
            db, user.organization_id, conversation.id, message_id
        )
        if message is None or message.direction != "OUTBOUND":
            raise NotFoundError(message="Message not found.")
        if message.status == "UNKNOWN":
            raise ConflictError(
                message="An unknown provider outcome must be reconciled from a signed status webhook; resending is unsafe.",
                code="WHATSAPP_UNKNOWN_RETRY_PROHIBITED",
            )
        if not message.retryable:
            raise ConflictError(
                message="This message is not eligible for a safe retry.",
                code="WHATSAPP_MESSAGE_NOT_RETRYABLE",
            )
        config = await self.repository.configuration(db, user.organization_id)
        identity = await self.repository.identity(db, conversation)
        if config is None or not config.enabled or identity.consent == "OPTED_OUT":
            raise ConflictError(message="WhatsApp sending is not currently available.")
        message.status = "PENDING"
        message.work_status = "PENDING"
        message.attempts = 0
        message.next_attempt_at = datetime.now(UTC)
        message.claimed_at = None
        message.error_code = None
        message.error_message = None
        message.failed_at = None
        self.audit(db, user.organization_id, "outbound_retry_queued", message.id, user.id)
        await self.commit(db)
        return message

    async def notify(
        self, db: AsyncSession, conversation: WhatsAppConversation, reason: str
    ) -> None:
        recipient = await self.repository.user(
            db, conversation.organization_id, conversation.assigned_user_id
        )
        if recipient:
            permissions = await self.permissions(db, recipient)
            if not {"whatsapp:read_assigned", "whatsapp:read_all"} & permissions:
                return
            self.repository.add_notification(db, conversation, recipient.id, reason)

    async def update(
        self, db: AsyncSession, user: User, conversation_id: str, payload: ConversationWrite
    ) -> WhatsAppConversation:
        conversation = await self.conversation(db, user, conversation_id, lock=True)
        permissions = await self.permissions(db, user)
        if "assigned_user_id" in payload.model_fields_set:
            if "whatsapp:assign" not in permissions:
                raise ForbiddenError(message="Assignment permission required.")
            if payload.assigned_user_id and not await self.eligible_assignee(
                db, user.organization_id, payload.assigned_user_id
            ):
                raise NotFoundError(message="User not found.")
            conversation.assigned_user_id = payload.assigned_user_id
            self.audit(db, user.organization_id, "conversation_assigned", conversation.id, user.id)
        if payload.ai_enabled is not None:
            if "whatsapp:manage_ai" not in permissions:
                raise ForbiddenError(message="AI management permission required.")
            identity = await self.repository.identity(db, conversation)
            if payload.ai_enabled and (
                not identity.state.startswith("MATCHED") or identity.consent == "OPTED_OUT"
            ):
                raise ConflictError(
                    message="Resolve and verify the customer identity before enabling AI."
                )
            conversation.ai_enabled = payload.ai_enabled
            if payload.ai_enabled:
                conversation.status = "OPEN"
            self.audit(
                db,
                user.organization_id,
                "ai_enabled" if payload.ai_enabled else "ai_disabled",
                conversation.id,
                user.id,
            )
        if payload.status is not None:
            if "whatsapp:takeover" not in permissions:
                raise ForbiddenError(message="Conversation management permission required.")
            conversation.status = payload.status
            if payload.status != "OPEN":
                conversation.ai_enabled = False
            self.audit(db, user.organization_id, "status_changed", conversation.id, user.id)
        await self.commit(db)
        return conversation

    async def takeover(
        self, db: AsyncSession, user: User, conversation_id: str
    ) -> WhatsAppConversation:
        conversation = await self.conversation(
            db, user, conversation_id, required="whatsapp:takeover", lock=True
        )
        conversation.ai_enabled = False
        conversation.status = "HUMAN_HANDOFF"
        if not conversation.assigned_user_id and not user.is_platform_admin:
            conversation.assigned_user_id = user.id
        self.audit(db, user.organization_id, "human_takeover", conversation.id, user.id)
        await self.notify(db, conversation, "A human agent has taken over this conversation.")
        await self.commit(db)
        return conversation

    async def mark_read(
        self, db: AsyncSession, user: User, conversation_id: str, message_id: str
    ) -> None:
        conversation = await self.conversation(db, user, conversation_id)
        message = await self.repository.message(
            db,
            user.organization_id,
            conversation.id,
            message_id,
            inbound_only=True,
        )
        if message is None:
            raise NotFoundError(message="Message not found.")
        read_through = message.created_at
        await self.repository.mark_read(db, conversation, user.id, read_through)
        await self.commit(db)

    async def resolve(
        self, db: AsyncSession, user: User, identity_id: str, payload: IdentityResolve
    ) -> None:
        await self.permissions(db, user, "integrations:manage")
        await self.permissions(
            db, user, "contacts:update" if payload.entity_type == "contact" else "leads:update"
        )
        await self.repository.lock_phone_guard(db, user.organization_id)
        identity = await self.repository.identity_by_id(
            db, user.organization_id, identity_id, lock=True
        )
        if identity is None:
            raise NotFoundError(message="Identity not found.")
        config = await self.repository.configuration(db, user.organization_id)
        record = await self.repository.crm_record(
            db, user.organization_id, payload.entity_type, payload.entity_id, lock=True
        )
        if record is None or config is None:
            raise NotFoundError(message="CRM record not found.")
        if not config.phone_index_ready:
            raise ConflictError(
                message="Complete organization phone normalization before resolving identities."
            )
        try:
            phone = normalize_phone(record.phone or "", config.default_phone_region)
        except ValueError as exc:
            raise ConflictError(
                message="CRM record requires a valid international phone number."
            ) from exc
        if phone != identity.normalized_phone_number:
            raise ConflictError(
                message="The CRM mobile does not match the provider-verified sender."
            )
        await self.repository.prepare_crm_phone(db, user.organization_id, record)
        record.whatsapp_phone_verified_at = datetime.now(UTC)
        await self.repository.flush(db)
        state, contact_id, lead_id = await self.repository.match(db, config, phone)
        if state not in {"MATCHED_CONTACT", "MATCHED_LEAD"}:
            raise ConflictError(
                message="Phone identity remains ambiguous; resolve duplicate CRM records first."
            )
        identity.state, identity.contact_id, identity.lead_id = state, contact_id, lead_id
        self.audit(db, user.organization_id, "identity_verified", identity.id, user.id)
        await self.commit(db)

    async def set_consent(
        self, db: AsyncSession, user: User, identity_id: str, consent: str
    ) -> None:
        await self.permissions(db, user, "integrations:manage")
        identity = await self.repository.identity_by_id(
            db, user.organization_id, identity_id, lock=True
        )
        if identity is None:
            raise NotFoundError(message="Identity not found.")
        identity.consent = consent
        identity.consent_updated_at = datetime.now(UTC)
        if consent == "OPTED_OUT":
            conversations = await self.repository.conversations_for_identity(
                db, user.organization_id, identity.id, lock=True
            )
            for conversation in conversations:
                conversation.ai_enabled = False
        self.audit(db, user.organization_id, "consent_updated", identity.id, user.id)
        await self.commit(db)

    async def media_url(
        self, db: AsyncSession, user: User, conversation_id: str, message_id: str
    ) -> str:
        conversation = await self.conversation(db, user, conversation_id)
        message = await self.repository.message(
            db, user.organization_id, conversation.id, message_id
        )
        if message is None or not message.media_s3_key:
            raise NotFoundError(message="WhatsApp media not found.")
        import asyncio

        from app.services.s3_service import s3_service

        return await asyncio.to_thread(s3_service.generate_presigned_url, message.media_s3_key, 60)

    async def backfill(self, db: AsyncSession, user: User) -> IntegrationRead:
        await self.permissions(db, user, "integrations:manage")
        config = await self.repository.configuration(db, user.organization_id, lock=True)
        if config is None:
            raise NotFoundError(message="WhatsApp integration not found.")
        await self.repository.backfill_phone_batch(db, config)
        await self.commit(db)
        return await self.status(db, user)


whatsapp_service = WhatsAppService()
