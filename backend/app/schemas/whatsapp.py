from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class IntegrationWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    business_account_id: str = Field(pattern=r"^\d{1,100}$")
    phone_number_id: str = Field(pattern=r"^\d{1,100}$")
    access_token: SecretStr = Field(min_length=20, max_length=4096)
    api_version: str = Field(pattern=r"^v\d{2}\.0$")
    default_phone_region: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    ai_user_id: str | None = Field(default=None, max_length=36)
    default_assignee_id: str | None = Field(default=None, max_length=36)
    enabled: bool = False


class WhatsAppAck(BaseModel):
    message: str


class MediaRead(BaseModel):
    download_url: str


class IntegrationRead(BaseModel):
    configured: bool = False
    enabled: bool = False
    phone_index_ready: bool = False
    status: str = "disconnected"
    business_account_id: str | None = None
    phone_number_id: str | None = None
    display_phone_number: str | None = None
    verified_name: str | None = None
    api_version: str | None = None
    default_phone_region: str | None = None
    last_webhook_at: datetime | None = None
    last_successful_message_at: datetime | None = None
    ai_user_id: str | None = None
    default_assignee_id: str | None = None


class MessageWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=4096)
    idempotency_key: str = Field(min_length=16, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")


class TemplateMessageWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    template_id: str = Field(min_length=1, max_length=36)
    parameters: list[str] = Field(default_factory=list, max_length=20)
    idempotency_key: str = Field(min_length=16, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")


class TemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    language: str
    category: str
    status: str
    body_parameter_count: int


class AssigneeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str


class ConversationWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["OPEN", "HUMAN_HANDOFF", "CLOSED"] | None = None
    ai_enabled: bool | None = None
    assigned_user_id: str | None = Field(default=None, max_length=36)


class ConversationReadWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_id: str = Field(min_length=1, max_length=36)


class IdentityResolve(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity_type: Literal["contact", "lead"]
    entity_id: str = Field(min_length=1, max_length=36)
    ownership_verified: Literal[True]


class IdentityConsent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    consent: Literal["UNKNOWN", "OPTED_IN", "OPTED_OUT"]


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    direction: str
    source: str
    message_type: str
    body: str | None
    status: str
    error_code: str | None
    error_message: str | None
    media_available: bool = False
    created_at: datetime
    provider_timestamp: datetime | None
    sent_at: datetime | None
    delivered_at: datetime | None
    read_at: datetime | None


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    identity_id: str
    status: str
    ai_enabled: bool
    assigned_user_id: str | None
    last_customer_message_at: datetime | None
    last_message_at: datetime | None
    customer_phone: str
    identity_state: str
    consent: str
    contact_id: str | None
    lead_id: str | None
    unread_count: int = 0


class WebhookText(BaseModel):
    body: str = Field(max_length=4096)


class WebhookMedia(BaseModel):
    id: str = Field(min_length=1, max_length=255)
    mime_type: str | None = Field(default=None, max_length=100)
    sha256: str | None = Field(default=None, max_length=100)
    caption: str | None = Field(default=None, max_length=4096)


class InboundEvent(BaseModel):
    id: str = Field(min_length=1, max_length=255)
    sender: str = Field(alias="from", pattern=r"^\d{7,15}$")
    timestamp: str = Field(pattern=r"^\d{1,12}$")
    type: str = Field(max_length=30)
    text: WebhookText | None = None
    image: WebhookMedia | None = None
    audio: WebhookMedia | None = None
    video: WebhookMedia | None = None
    document: WebhookMedia | None = None


class ProviderError(BaseModel):
    code: int


class StatusEvent(BaseModel):
    id: str = Field(min_length=1, max_length=255)
    status: Literal["sent", "delivered", "read", "failed"]
    timestamp: str = Field(pattern=r"^\d{1,12}$")
    recipient_id: str = Field(pattern=r"^\d{7,15}$")
    biz_opaque_callback_data: str | None = Field(
        default=None, min_length=1, max_length=36, pattern=r"^[a-zA-Z0-9-]+$"
    )
    errors: list[ProviderError] = Field(default_factory=list, max_length=10)


class WebhookMetadata(BaseModel):
    phone_number_id: str = Field(pattern=r"^\d{1,100}$")


class WebhookValue(BaseModel):
    messaging_product: Literal["whatsapp"]
    metadata: WebhookMetadata
    messages: list[InboundEvent] = Field(default_factory=list, max_length=100)
    statuses: list[StatusEvent] = Field(default_factory=list, max_length=100)


class WebhookChange(BaseModel):
    field: Literal["messages"]
    value: WebhookValue


class WebhookEntry(BaseModel):
    id: str = Field(pattern=r"^\d{1,100}$")
    changes: list[WebhookChange] = Field(max_length=100)


class WebhookPayload(BaseModel):
    object: Literal["whatsapp_business_account"]
    entry: list[WebhookEntry] = Field(max_length=100)


class CustomerAIOutput(BaseModel):
    reply: str = Field(min_length=1, max_length=2000)
    handoff: bool = False


class CustomerAIPlan(BaseModel):
    topic: Literal[
        "greeting",
        "lead",
        "deal",
        "invoice",
        "payment",
        "quote",
        "meeting",
        "task",
        "account_owner",
        "human",
        "sensitive",
        "unknown",
    ]
