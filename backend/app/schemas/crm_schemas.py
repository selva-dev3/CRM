from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

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

# 2. Users Schemas
class UserBase(BaseModel):
    name: str
    email: EmailStr
    role: str = "Sales Executive"
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

    class Config:
        from_attributes = True

# 3. Roles & Permissions Schemas
class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None
    permissions: List[str]

class RoleCreate(RoleBase):
    pass

class RoleResponse(RoleBase):
    id: str
    is_system_role: bool = False

# 4. Organizations Schemas
class OrganizationBase(BaseModel):
    name: str
    domain: Optional[str] = None
    plan: str = "Enterprise"
    max_users: int = 50

class OrganizationResponse(OrganizationBase):
    id: str
    created_at: str

# 5. Dashboard & KPIs Schemas
class DashboardKPIs(BaseModel):
    total_leads: int
    deals_won_amount: float
    win_rate_percentage: float
    ai_lead_score_avg: float
    recent_activity: List[Dict[str, Any]]

# 6. Lead Schemas
class LeadBase(BaseModel):
    title: str
    company: str
    contact_name: str
    email: EmailStr
    phone: Optional[str] = None
    status: str = "New"
    source: Optional[str] = "Website"

class LeadCreate(LeadBase):
    pass

class LeadResponse(LeadBase):
    id: str
    score: float
    assigned_to: Optional[str] = None
    organization_id: str
    created_at: str

# 7. Contact Schemas
class ContactBase(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    position: Optional[str] = None
    company_id: Optional[str] = None

class ContactCreate(ContactBase):
    pass

class ContactResponse(ContactBase):
    id: str
    created_at: str

# 8. Company Schemas
class CompanyBase(BaseModel):
    name: str
    industry: Optional[str] = None
    website: Optional[str] = None
    employee_count: Optional[int] = None

class CompanyCreate(CompanyBase):
    pass

class CompanyResponse(CompanyBase):
    id: str
    created_at: str

# 9. Deal Schemas
class DealBase(BaseModel):
    title: str
    amount: float
    stage: str = "Prospecting"
    probability: float = 50.0
    expected_close_date: Optional[str] = None

class DealCreate(DealBase):
    assigned_to: str
    contact_id: Optional[str] = None
    company_id: Optional[str] = None

class DealResponse(DealBase):
    id: str
    assigned_to: str
    organization_id: str
    created_at: str

# 10. Task Schemas
class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "Medium"
    due_date: str
    status: str = "Pending"

class TaskCreate(TaskBase):
    assigned_to: str

class TaskResponse(TaskBase):
    id: str
    assigned_to: str
    created_at: str

# 11. Meeting Schemas
class MeetingBase(BaseModel):
    title: str
    start_time: str
    end_time: str
    attendees: List[str]
    meeting_link: Optional[str] = None

class MeetingCreate(MeetingBase):
    pass

class MeetingResponse(MeetingBase):
    id: str
    ai_summary: Optional[str] = None

# 12. Call Log Schemas
class CallLogBase(BaseModel):
    contact_id: str
    call_type: str = "Outbound"
    duration_seconds: int
    notes: Optional[str] = None

class CallLogResponse(CallLogBase):
    id: str
    timestamp: str

# 13. Calendar Schemas
class CalendarEvent(BaseModel):
    id: str
    title: str
    start: str
    end: str
    event_type: str = "Meeting"

# 14. Email Schemas
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

# 15. Note Schemas
class NoteBase(BaseModel):
    entity_type: str
    entity_id: str
    content: str

class NoteResponse(NoteBase):
    id: str
    created_by: str
    created_at: str

# 16. Document Schemas
class DocumentResponse(BaseModel):
    id: str
    filename: str
    file_size: int
    mime_type: str
    download_url: str
    uploaded_at: str

# 17. Product Schemas
class ProductBase(BaseModel):
    name: str
    sku: str
    price: float
    category: str

class ProductResponse(ProductBase):
    id: str

# 18. Quote Schemas
class QuoteItem(BaseModel):
    product_id: str
    quantity: int
    unit_price: float

class QuoteBase(BaseModel):
    quote_number: str
    items: List[QuoteItem]
    total_amount: float
    status: str = "Draft"

class QuoteResponse(QuoteBase):
    id: str
    created_at: str

# 19. Invoice Schemas
class InvoiceBase(BaseModel):
    invoice_number: str
    amount: float
    status: str = "Draft"
    due_date: str

class InvoiceResponse(InvoiceBase):
    id: str
    stripe_checkout_url: Optional[str] = None
    created_at: str

# 20. Notification Schemas
class NotificationItem(BaseModel):
    id: str
    title: str
    message: str
    is_read: bool
    created_at: str

# 21. Report Schemas
class ReportData(BaseModel):
    report_type: str
    metrics: Dict[str, Any]
    generated_at: str

# 22. Settings Schemas
class SystemSettings(BaseModel):
    organization_name: str
    currency: str = "USD"
    timezone: str = "UTC"
    smtp_enabled: bool = True
    ai_features_enabled: bool = True

# 23. Integration Schemas
class IntegrationStatus(BaseModel):
    name: str
    is_connected: bool
    last_synced: Optional[str] = None

# 24. AI Features Schemas
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
