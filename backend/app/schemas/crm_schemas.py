from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# Common Pagination & Generic Schemas
class PaginationParams(BaseModel):
    page: int = Field(1, ge=1)
    limit: int = Field(20, ge=1, le=100)
    search: Optional[str] = None
    sort_by: Optional[str] = None
    order: Optional[str] = "asc"

class MessageResponse(BaseModel):
    message: str
    status: str = "success"

class BulkDeleteRequest(BaseModel):
    ids: List[str]

class BulkActionResponse(BaseModel):
    affected_count: int
    message: str

# 1. Authentication Schemas
class Token(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int = 86400

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    organization_name: str

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str

class TwoFactorSetupResponse(BaseModel):
    secret: str
    qr_code_url: str

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
    api_key: Optional[str] = None
    key: Optional[str] = None
    created_at: str
    last_used: Optional[str] = None

# 2. User Schemas
class UserBase(BaseModel):
    name: str
    email: EmailStr
    role: str
    organization_id: str
    is_active: bool = True

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

class UserResponse(UserBase):
    id: str
    avatar_url: Optional[str] = None
    created_at: str

class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    timezone: Optional[str] = "UTC"

class UserInviteItem(BaseModel):
    name: Optional[str] = None
    email: EmailStr

class UserInviteRequest(BaseModel):
    name: Optional[str] = None
    emails: Optional[List[EmailStr]] = None
    users: Optional[List[UserInviteItem]] = None
    role: str = "Sales Executive"

class UserInviteResponseItem(BaseModel):
    name: str
    email: str
    token: str
    role: str
    status: str = "pending"

class UserInviteBulkResponse(BaseModel):
    message: str
    invitations: List[UserInviteResponseItem]
    status: str = "success"

class AcceptInviteRequest(BaseModel):
    token: str
    name: str
    password: str

class UserInvitationDetailsResponse(BaseModel):
    id: str
    email: str
    token: str
    role: str
    status: str
    organization_id: str
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
    description: Optional[str] = None

class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None
    permissions: List[str]

class RoleCreate(RoleBase):
    pass

class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[List[str]] = None

class RoleResponse(RoleBase):
    id: str
    created_at: str

# 4. Organization Schemas
class OrganizationBase(BaseModel):
    name: str
    slug: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    country: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    postal_code: Optional[str] = None
    timezone: Optional[str] = "Asia/Kolkata"
    currency: Optional[str] = "INR"
    language: Optional[str] = "en"
    logo_url: Optional[str] = None
    tax_number: Optional[str] = None
    registration_number: Optional[str] = None
    status: Optional[str] = "active"
    domain: Optional[str] = None
    plan: Optional[str] = "Enterprise"
    max_users: Optional[int] = 100

class OrganizationCreate(OrganizationBase):
    pass

class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    country: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    postal_code: Optional[str] = None
    timezone: Optional[str] = None
    currency: Optional[str] = None
    language: Optional[str] = None
    logo_url: Optional[str] = None
    tax_number: Optional[str] = None
    registration_number: Optional[str] = None
    status: Optional[str] = None
    domain: Optional[str] = None
    plan: Optional[str] = None
    max_users: Optional[int] = None

class OrganizationResponse(OrganizationBase):
    id: str
    created_at: str
    members_count: int = 1

# 5. Lead Schemas
class LeadBase(BaseModel):
    title: str
    company: str
    contact_name: str
    email: EmailStr
    phone: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    country: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    postal_code: Optional[str] = None
    status: str = "New"
    source: str = "Website"
    score: Optional[float] = 50.0
    assigned_to: Optional[str] = None
    is_archived: Optional[bool] = False
    organization_id: Optional[str] = "org-1"

class LeadCreate(LeadBase):
    pass

class LeadUpdate(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    country: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    postal_code: Optional[str] = None
    status: Optional[str] = None
    source: Optional[str] = None
    score: Optional[float] = None
    assigned_to: Optional[str] = None
    is_archived: Optional[bool] = None
    organization_id: Optional[str] = None

class LeadResponse(LeadBase):
    id: str
    score: float = 75.0
    organization_id: str
    created_at: str

class LeadConvertRequest(BaseModel):
    create_deal: bool = True
    deal_title: Optional[str] = None
    deal_amount: Optional[float] = 0.0

# 6. Contact Schemas
class ContactBase(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: Optional[str] = None
    company_id: Optional[str] = None
    job_title: Optional[str] = None

class ContactCreate(ContactBase):
    pass

class ContactUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

class ContactResponse(ContactBase):
    id: str
    organization_id: str
    created_at: str

# 7. Company Schemas
class CompanyBase(BaseModel):
    name: str
    domain: Optional[str] = None
    industry: Optional[str] = None
    size: Optional[str] = None

class CompanyCreate(CompanyBase):
    pass

class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    industry: Optional[str] = None

class CompanyResponse(CompanyBase):
    id: str
    organization_id: str
    created_at: str

# 8. Deal Schemas
class DealBase(BaseModel):
    title: str
    amount: float
    stage: str = "Qualification"
    probability: float = 20.0
    expected_close_date: Optional[str] = None
    company_id: Optional[str] = None
    contact_id: Optional[str] = None

class DealCreate(DealBase):
    pass

class DealUpdate(BaseModel):
    stage: Optional[str] = None
    amount: Optional[float] = None
    probability: Optional[float] = None

class DealResponse(DealBase):
    id: str
    organization_id: str
    created_at: str

# 9. Task Schemas
class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "Medium"
    due_date: Optional[str] = None
    status: str = "Pending"
    assigned_to: Optional[str] = None

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None

class TaskResponse(TaskBase):
    id: str
    created_at: str

# 10. Meeting Schemas
class MeetingBase(BaseModel):
    title: str
    start_time: str
    end_time: str
    location: Optional[str] = None
    meeting_link: Optional[str] = None

class MeetingCreate(MeetingBase):
    attendee_emails: List[EmailStr]

class MeetingResponse(MeetingBase):
    id: str
    created_at: str

# 11. Call Log Schemas
class CallLogBase(BaseModel):
    contact_id: str
    call_type: str = "Outbound"  # Outbound, Inbound
    duration_seconds: int = 0
    notes: Optional[str] = None

class CallLogResponse(CallLogBase):
    id: str
    timestamp: str

# 12. Email & Inbox Schemas
class EmailSendRequest(BaseModel):
    to: List[EmailStr]
    subject: str
    body: str

class EmailResponse(BaseModel):
    id: str
    from_email: str
    to: List[str]
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
    code: str
    unit_price: float
    category: Optional[str] = None

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

class QuoteItemSchema(BaseModel):
    product_id: str
    quantity: int
    unit_price: float

class QuoteCreate(BaseModel):
    deal_id: str
    items: List[QuoteItemSchema]

class QuoteResponse(BaseModel):
    id: str
    quote_number: str
    total_amount: float
    status: str
    created_at: str

# 17. Invoice Schemas
class InvoiceBase(BaseModel):
    deal_id: str
    invoice_number: str
    amount: float
    status: str = "Unpaid"
    due_date: str

class InvoiceCreate(BaseModel):
    deal_id: str
    amount: float
    due_date: str

class InvoiceResponse(BaseModel):
    id: str
    invoice_number: str
    amount: float
    status: str
    due_date: str

# 18. Notification Schemas
class NotificationItem(BaseModel):
    id: str
    title: str
    message: str
    is_read: bool
    created_at: str

class NotificationResponse(BaseModel):
    id: str
    title: str
    message: str
    is_read: bool
    created_at: str

# 19. Calendar Schemas
class CalendarEvent(BaseModel):
    id: str
    title: str
    start: str
    end: str
    event_type: Optional[str] = "Meeting"

# 20. Dashboard KPI Schemas
class DashboardKPIs(BaseModel):
    total_leads: int
    deals_won_amount: float
    win_rate_percentage: float
    ai_lead_score_avg: float
    recent_activity: List[Dict[str, Any]]

# 21. Integration Schemas
class IntegrationStatus(BaseModel):
    name: str
    is_connected: bool
    last_synced: Optional[str] = None

# 22. AI Suite Schemas
class AIScoreResponse(BaseModel):
    score: float
    reasons: List[str]

class AIGenerateEmailRequest(BaseModel):
    prompt: str
    tone: str = "Professional"

class AIGenerateEmailResponse(BaseModel):
    subject: str
    body: str

class AISalesForecastResponse(BaseModel):
    predicted_revenue: float
    confidence_percentage: float
    factors: List[str]

# 23. Report Schemas
class ReportData(BaseModel):
    report_type: str
    metrics: Dict[str, Any]
    generated_at: str

# 24. System Settings Schemas
class SystemSettings(BaseModel):
    organization_name: str
    currency: str = "USD"
    timezone: str = "UTC"
    smtp_enabled: bool = True
    ai_features_enabled: bool = True
