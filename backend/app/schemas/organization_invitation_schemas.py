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

class AcceptInvitationRequest(BaseModel):
    password: str = Field(..., min_length=6, example="Password123!")
    full_name: Optional[str] = Field(None, example="Jane Smith")

class InvitationResponse(BaseModel):
    id: str
    organization_id: str
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

class InvitationStatusResponse(BaseModel):
    organization: dict
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
