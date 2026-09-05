from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.currency import normalize_currency_code


# Common Pagination & Generic Schemas
class PaginationParams(BaseModel):
    page: int = Field(1, ge=1)
    limit: int = Field(20, ge=1, le=100)
    search: str | None = None
    sort_by: str | None = None
    order: str | None = "asc"


class MessageResponse(BaseModel):
    message: str
    status: str = "success"


class BulkDeleteRequest(BaseModel):
    ids: list[str]


class SetDefaultRolesRequest(BaseModel):
    role_ids: list[str]


class BulkActionResponse(BaseModel):
    affected_count: int
    message: str


# 1. Authentication Schemas
class UserTokenInfo(BaseModel):
    id: str
    name: str
    email: str
    role: str
    organization_id: str | None = None
    permissions: list[str] = []


class Token(BaseModel):
    token_type: str = "bearer"  # noqa: S105 - OAuth token type, not a credential
    expires_in: int = 86400
    user: UserTokenInfo | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = True
    two_factor_code: str | None = Field(default=None, min_length=6, max_length=6)


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    organization_name: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(min_length=14, max_length=128)
    new_password: str = Field(min_length=8, max_length=72)


class PasswordChangeRequest(BaseModel):
    old_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=8, max_length=72)


class TwoFactorSetupResponse(BaseModel):
    secret: str
    otp_uri: str


class TwoFactorVerifyRequest(BaseModel):
    code: str


class OAuthLoginRequest(BaseModel):
    provider: str  # google, microsoft
    id_token: str


class ApiKeyCreate(BaseModel):
    name: str


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    api_key: str | None = None
    key: str | None = None
    created_at: str
    last_used: str | None = None


# 2. User Schemas
class UserBase(BaseModel):
    name: str
    email: EmailStr
    role: str
    organization_id: str
    is_active: bool = True


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    role: str
    password: str


class UserUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    is_active: bool | None = None


class UserResponse(UserBase):
    id: str
    avatar_url: str | None = None
    created_at: str


class UserProfileUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    avatar_url: str | None = None
    timezone: str | None = "UTC"


class UserInviteItem(BaseModel):
    name: str | None = None
    email: EmailStr


class UserInviteRequest(BaseModel):
    name: str | None = None
    emails: list[EmailStr] | None = None
    users: list[UserInviteItem] | None = None
    role: str


class UserInviteResponseItem(BaseModel):
    name: str
    email: str
    role: str
    role_name: str | None = None
    status: str = "pending"


class UserInviteBulkResponse(BaseModel):
    message: str
    invitations: list[UserInviteResponseItem]
    status: str = "success"


class AcceptInviteRequest(BaseModel):
    token: str
    name: str
    password: str


class UserInvitationDetailsResponse(BaseModel):
    id: str
    email: str
    role: str
    status: str
    organization_id: str | None = None
    created_at: str


class UserActionResponse(BaseModel):
    message: str
    user_id: str
    name: str
    email: EmailStr
    is_active: bool
    status: str = "success"


class UserDeleteResponse(BaseModel):
    message: str
    user_id: str
    name: str
    email: EmailStr
    status: str = "success"


# 3. Roles & Permissions Schemas
class PermissionItem(BaseModel):
    id: str
    key: str
    name: str
    category: str
    description: str | None = None


class PermissionCreate(BaseModel):
    name: str
    key: str
    category: str | None = "General"
    description: str | None = None


class RoleBase(BaseModel):
    name: str
    description: str | None = None
    permissions: list[str]


class RoleCreate(RoleBase):
    pass


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    permissions: list[str] | None = None


class RoleResponse(RoleBase):
    id: str
    is_system_role: bool | None = False
    type: str | None = "custom"
    created_at: str


# 4. Organization Schemas
class OrganizationBase(BaseModel):
    name: str
    slug: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    industry: str | None = None
    company_size: str | None = None
    country: str | None = None
    state: str | None = None
    city: str | None = None
    address: str | None = None
    postal_code: str | None = None
    timezone: str | None = "Asia/Kolkata"
    currency: str | None = "INR"
    language: str | None = "en"
    logo_url: str | None = None
    tax_number: str | None = None
    registration_number: str | None = None
    status: str | None = "active"
    role: str | None = "Admin"
    domain: str | None = None
    plan: str | None = "Enterprise"
    max_users: int | None = 100


class OrganizationCreate(OrganizationBase):
    @field_validator("currency", mode="before")
    @classmethod
    def validate_currency(cls, value: object) -> str | None:
        return None if value is None else normalize_currency_code(value)


class OrganizationUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    industry: str | None = None
    company_size: str | None = None
    country: str | None = None
    state: str | None = None
    city: str | None = None
    address: str | None = None
    postal_code: str | None = None
    timezone: str | None = None
    currency: str | None = None
    language: str | None = None
    logo_url: str | None = None
    tax_number: str | None = None
    registration_number: str | None = None
    status: str | None = None
    role: str | None = None
    domain: str | None = None
    plan: str | None = None
    max_users: int | None = None

    @field_validator("currency", mode="before")
    @classmethod
    def validate_currency(cls, value: object) -> str | None:
        return None if value is None else normalize_currency_code(value)


class OrganizationResponse(OrganizationBase):
    id: str
    created_at: str
    members_count: int = 1


class SubscriptionCheckoutRequest(BaseModel):
    plan_slug: str
    org_id: str | None = None


class SubscriptionCheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str
    status: str = "success"


class SubscriptionCheckoutVerifyResponse(BaseModel):
    verified: bool
    db_synced: bool
    plan: str | None = None
    plan_slug: str | None = None
    status: str
    message: str


# 5. Lead Schemas
CustomFieldValue = str | float | bool | None


class CustomFieldDefinition(BaseModel):
    field_name: str
    field_type: Literal["text", "number", "boolean", "select"]
    label: str
    options: list[str] = Field(default_factory=list)


class LeadBase(BaseModel):
    title: str
    company: str
    contact_name: str
    email: EmailStr
    phone: str | None = None
    website: str | None = None
    industry: str | None = None
    company_size: str | None = None
    country: str | None = None
    state: str | None = None
    city: str | None = None
    address: str | None = None
    postal_code: str | None = None
    status: str = "New"
    source: str = "Website"
    score: float | None = 50.0
    assigned_to: str | None = None
    is_archived: bool | None = False
    organization_id: str | None = None
    custom_fields: dict[str, CustomFieldValue] = Field(default_factory=dict)


class LeadCreate(LeadBase):
    pass


class LeadUpdate(BaseModel):
    title: str | None = None
    company: str | None = None
    contact_name: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    industry: str | None = None
    company_size: str | None = None
    country: str | None = None
    state: str | None = None
    city: str | None = None
    address: str | None = None
    postal_code: str | None = None
    status: str | None = None
    source: str | None = None
    score: float | None = None
    assigned_to: str | None = None
    is_archived: bool | None = None
    organization_id: str | None = None
    custom_fields: dict[str, CustomFieldValue] | None = None


class LeadResponse(LeadBase):
    id: str
    score: float = 75.0
    organization_id: str
    created_at: str


class LeadConvertRequest(BaseModel):
    create_deal: bool = True
    deal_title: str | None = Field(default=None, min_length=1, max_length=255)
    deal_amount: float | None = Field(default=0.0, ge=0, allow_inf_nan=False)


# 6. Contact Schemas
class ContactBase(BaseModel):
    first_name: str | None = ""
    last_name: str | None = ""
    name: str | None = ""
    email: str | None = ""
    phone: str | None = None
    company_id: str | None = None
    position: str | None = None
    job_title: str | None = None
    custom_fields: dict[str, CustomFieldValue] | None = None


class ContactCreate(ContactBase):
    pass


class ContactUpdate(ContactBase):
    custom_fields: dict[str, CustomFieldValue] | None = None


class ContactResponse(BaseModel):
    id: str
    name: str | None = ""
    first_name: str | None = ""
    last_name: str | None = ""
    email: str
    phone: str | None = None
    position: str | None = None
    company_id: str | None = None
    is_starred: bool | None = False
    status: str | None = None
    created_at: str | None = None
    custom_fields: dict[str, CustomFieldValue] = Field(default_factory=dict)


# 7. Company Schemas
class CompanyBase(BaseModel):
    name: str
    domain: str | None = None
    website: str | None = None
    industry: str | None = None
    size: str | None = None
    employee_count: int | None = None
    custom_fields: dict[str, CustomFieldValue] = Field(default_factory=dict)


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    name: str | None = None
    domain: str | None = None
    website: str | None = None
    industry: str | None = None
    size: str | None = None
    employee_count: int | None = None
    custom_fields: dict[str, CustomFieldValue] | None = None


class CompanyResponse(BaseModel):
    id: str
    name: str
    domain: str | None = None
    website: str | None = None
    industry: str | None = None
    size: str | None = None
    employee_count: int | None = None
    created_at: str | None = None
    custom_fields: dict[str, CustomFieldValue] = Field(default_factory=dict)


# 8. Deal Schemas
DealCustomFieldValue = CustomFieldValue
DealCustomFieldDefinition = CustomFieldDefinition


class DealBase(BaseModel):
    title: str
    amount: float = 0.0
    stage: str = "Qualification"
    probability: float | None = 20.0
    expected_close_date: str | None = None
    company_id: str | None = None
    contact_id: str | None = None
    assigned_to: str | None = None
    project_id: str | None = None
    custom_fields: dict[str, DealCustomFieldValue] = Field(default_factory=dict)


class DealCreate(DealBase):
    pass


class DealUpdate(BaseModel):
    title: str | None = None
    stage: str | None = None
    amount: float | None = None
    probability: float | None = None
    expected_close_date: str | None = None
    company_id: str | None = None
    contact_id: str | None = None
    assigned_to: str | None = None
    project_id: str | None = None
    custom_fields: dict[str, DealCustomFieldValue] | None = None


class DealResponse(DealBase):
    id: str
    organization_id: str
    created_at: str


# 9. Task Schemas
class TaskBase(BaseModel):
    title: str
    description: str | None = None
    priority: str = "Medium"
    due_date: str | None = None
    status: str = "Pending"
    assigned_to: str | None = None
    project_id: str | None = None


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    status: str | None = None
    priority: str | None = None
    project_id: str | None = None


class TaskResponse(TaskBase):
    id: str
    created_at: str


# 10. Meeting Schemas
class MeetingBase(BaseModel):
    title: str
    start_time: str
    end_time: str
    location: str | None = None
    meeting_link: str | None = None


class MeetingCreate(MeetingBase):
    attendee_emails: list[EmailStr]


class MeetingResponse(MeetingBase):
    id: str
    created_at: str


# 11. Call Log Schemas
class CallLogBase(BaseModel):
    contact_id: str | None = None
    call_type: str = "Outbound"  # Outbound, Inbound
    duration_seconds: int = 0
    notes: str | None = None


class CallLogResponse(CallLogBase):
    id: str
    timestamp: str


# 12. Email & Inbox Schemas
class EmailSendRequest(BaseModel):
    to: list[EmailStr]
    subject: str
    body: str


class EmailResponse(BaseModel):
    id: str
    from_email: str
    to: list[str]
    subject: str
    sent_at: str


# 13. Note Schemas
class NoteBase(BaseModel):
    entity_type: str  # lead, contact, deal, company
    entity_id: str
    content: str


class NoteResponse(NoteBase):
    id: str
    created_by: str
    created_at: str


# 14. Document Storage Schemas
class DocumentResponse(BaseModel):
    id: str
    filename: str
    file_size: int
    mime_type: str
    download_url: str
    uploaded_at: str


# 15. Product Catalog Schemas
class ProductBase(BaseModel):
    name: str
    code: str | None = "N/A"
    sku: str | None = "N/A"
    unit_price: float = 0.0
    price: float | None = 0.0
    quantity: int | None = 1
    category: str | None = None
    in_stock_quantity: int | None = 100
    is_active: bool | None = True


class ProductCreate(ProductBase):
    pass


class ProductResponse(ProductBase):
    id: str


# 16. Quote Schemas
class QuoteBase(BaseModel):
    deal_id: str
    quote_number: str
    total_amount: float
    status: str = "Draft"
    payment_terms: str | None = None
    due_date: str | None = None


class QuoteItemSchema(BaseModel):
    product_id: str | None
    quantity: int
    unit_price: float
    product_name: str | None = None
    discount_percent: float = 0
    tax_percent: float = 0
    subtotal: float | None = None
    discount_total: float | None = None
    tax_total: float | None = None
    total: float | None = None


class QuoteCreate(BaseModel):
    deal_id: str
    items: list[QuoteItemSchema]


class QuoteResponse(BaseModel):
    id: str
    deal_id: str | None = None
    quote_number: str
    total_amount: float
    status: str
    created_at: str
    items: list[QuoteItemSchema] = Field(default_factory=list)
    currency: str | None = None
    delivery_status: str | None = None
    delivery_id: str | None = None
    provider_message_id: str | None = None
    sent_at: str | None = None
    recipient_email: str | None = None
    pdf_available: bool = False
    expires_at: str | None = None
    due_date: str | None = None
    payment_terms: str | None = None
    company_name: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    rejection_reason: str | None = None
    invoice_id: str | None = None
    invoice_number: str | None = None
    invoice_status: str | None = None


# 17. Invoice Schemas
class InvoiceItemSchema(BaseModel):
    id: str
    product_id: str | None
    product_name: str
    description: str | None = None
    quantity: int = 1
    unit_price: float = 0.0
    discount_percent: float = 0.0
    tax_percent: float = 0.0
    subtotal: float = 0.0
    discount_total: float = 0.0
    tax_total: float = 0.0
    total: float = 0.0


class InvoiceBase(BaseModel):
    deal_id: str
    invoice_number: str | None = None
    amount: float = 0.0
    status: str = "Draft"
    due_date: str | None = None


class InvoiceCreate(BaseModel):
    deal_id: str
    amount: float | None = None
    due_date: str | None = None


class InvoiceResponse(BaseModel):
    id: str
    quote_id: str | None = None
    invoice_number: str
    deal_id: str | None = None
    company_id: str | None = None
    contact_id: str | None = None
    currency: str = "USD"
    amount: float = 0.0
    subtotal: float = 0.0
    discount_total: float = 0.0
    tax_total: float = 0.0
    paid_amount: float = 0.0
    status: str
    due_date: str | None = None
    notes: str | None = None
    sent_at: str | None = None
    delivery_status: str | None = None
    pdf_available: bool = False
    recipient_email: str | None = None
    reminder_count: int = 0
    last_reminded_at: str | None = None
    stripe_checkout_url: str | None = None
    created_at: str | None = None
    items: list[InvoiceItemSchema] = Field(default_factory=list)


class PaymentResponse(BaseModel):
    id: str
    invoice_id: str
    invoice_number: str
    company_name: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    amount: float = 0.0
    currency: str
    payment_method: str | None = None
    status: str
    provider: str
    provider_payment_id: str
    checkout_session_id: str
    paid_at: str
    created_at: str | None = None


# 18. Notification Schemas
class NotificationItem(BaseModel):
    id: str
    title: str
    message: str
    is_read: bool
    created_at: str
    organization_id: str | None = None
    event_name: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    payload: dict | None = None
    read_at: str | None = None
    updated_at: str | None = None


class NotificationResponse(BaseModel):
    id: str
    title: str
    message: str
    is_read: bool
    created_at: str
    organization_id: str | None = None
    event_name: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    payload: dict | None = None
    read_at: str | None = None
    updated_at: str | None = None


# 19. Calendar Schemas
class CalendarEvent(BaseModel):
    id: str
    title: str
    start: str
    end: str
    event_type: str | None = "Meeting"


class CalendarEventCreatePayload(BaseModel):
    title: str
    start: str
    end: str
    event_type: str | None = "Meeting"
    description: str | None = None


class CalendarEventResponse(BaseModel):
    id: str
    title: str
    start: str
    end: str
    event_type: str
    description: str | None = None


# 20. Integration Schemas
class IntegrationStatus(BaseModel):
    name: str
    is_connected: bool
    last_synced: str | None = None


class SlackConnectRequest(BaseModel):
    webhook_url: str


class SlackEventsUpdateRequest(BaseModel):
    events: list[str]


class SlackConfigResponse(BaseModel):
    name: str
    is_connected: bool
    webhook_url: str | None
    events: list[str]
    last_synced: str | None


class SlackEventPayload(BaseModel):
    event_name: str
    data: dict[str, Any]


class SlackTestResponse(BaseModel):
    message: str
    status: str = "success"


class SlackDisconnectResponse(BaseModel):
    message: str
    status: str = "success"


class SlackNotifyPayload(BaseModel):
    channel: str | None = "general"
    message: str


class ZapierConnectPayload(BaseModel):
    webhook_url: str | None = "https://hooks.zapier.com/hooks/catch/crm_default"
    events: list[str] | None = ["lead.created", "deal.won"]


# 22. AI Suite Schemas
class AIScoreResponse(BaseModel):
    score: float
    reasons: list[str]


class AIGenerateEmailRequest(BaseModel):
    prompt: str
    tone: str = "Professional"


class AIGenerateEmailResponse(BaseModel):
    subject: str
    body: str


class AISalesForecastResponse(BaseModel):
    predicted_revenue: float
    confidence_percentage: float
    factors: list[str]


# 23. Report Schemas
class ReportData(BaseModel):
    report_type: str
    metrics: dict[str, Any]
    generated_at: str


# 24. System Settings Schemas
class CustomFieldResponse(BaseModel):
    id: str
    entity_type: str
    field_name: str
    field_type: str
    label: str
    options: list[str] = Field(default_factory=list)
    created_at: str | None = None


class SystemSettings(BaseModel):
    organization_name: str
    currency: str = "USD"
    timezone: str = "UTC"
    smtp_enabled: bool = True
    ai_features_enabled: bool = True

    @field_validator("currency", mode="before")
    @classmethod
    def validate_currency(cls, value: object) -> str:
        return normalize_currency_code(value)
