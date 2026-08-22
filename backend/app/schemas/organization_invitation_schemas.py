from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Any
from datetime import datetime

class SuperAdminOrgCreateRequest(BaseModel):
    organization_name: str = Field(..., example="Acme Corporation")
    domain: Optional[str] = Field(None, example="acme.crm.com")
    plan_slug: str = Field("enterprise", example="enterprise")
    admin_full_name: str = Field(..., example="John Doe")
    admin_email: EmailStr = Field(..., example="admin@acme.com")
    phone: Optional[str] = Field(None, example="+91 9876543210")
    industry: Optional[str] = Field(None, example="Technology")

class OrganizationInviteRequest(BaseModel):
    email: EmailStr = Field(..., example="user@company.com")
    full_name: Optional[str] = Field(None, example="Jane Smith")
    role: Optional[str] = Field("Admin", example="Admin")
    organization_id: Optional[str] = Field(None, example="org-1")

class CreateOrganizationInvitationRequest(BaseModel):
    """Invite Organization payload. The organization is created server-side with a
    backend-generated ID — a client-supplied organization_id is never accepted."""
    email: EmailStr = Field(..., example="admin@acme.com")
    full_name: str = Field(..., min_length=1, example="Jane Smith")
    role_id: Optional[str] = Field("Admin", example="Admin")

class InvitationResponse(BaseModel):
    id: str
    organization_id: Optional[str] = None
    organization_name: Optional[str] = None
    email: str
    full_name: Optional[str] = None
    role: Optional[str] = "Admin"
    subscription_id: Optional[str] = None
    token: str
    status: str
    expires_at: str
    accepted_at: Optional[str] = None
    created_at: str
    invite_url: Optional[str] = None

    class Config:
        from_attributes = True

class NewOrganizationInviteResponse(BaseModel):
    organization: dict
    invitation: InvitationResponse
    message: str

class AcceptInvitationRequest(BaseModel):
    password: str = Field(..., min_length=6, example="Password123!")
    full_name: Optional[str] = Field(None, example="Jane Smith")
    organization_name: Optional[str] = Field(None, example="Acme Corporation")
    domain: Optional[str] = Field(None, example="acme.crm.com")
    industry: Optional[str] = Field(None, example="Technology")
    country: Optional[str] = Field(None, example="India")
    city: Optional[str] = Field(None, example="Chennai")
    phone: Optional[str] = Field(None, example="+91 9876543210")

class InviteUserResponse(BaseModel):
    token: str
    invite_url: str
    message: str

class InvitationStatusResponse(BaseModel):
    organization: Optional[dict] = None
    email: str
    full_name: Optional[str] = None
    role: Optional[str] = "Admin"
    expires_at: str
    status: str
    is_valid: bool

class InvitationListResponse(BaseModel):
    total: int
    invitations: List[InvitationResponse]

class SuperAdminOrgResponse(BaseModel):
    organization: dict
    subscription: dict
    invitation: InvitationResponse
    message: str
