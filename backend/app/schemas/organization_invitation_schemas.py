from pydantic import BaseModel, EmailStr, Field


class SuperAdminOrgCreateRequest(BaseModel):
    organization_name: str = Field(..., examples=["Acme Corporation"])
    domain: str | None = Field(None, examples=["acme.crm.com"])
    plan_slug: str = Field("enterprise", examples=["enterprise"])
    admin_full_name: str = Field(..., examples=["John Doe"])
    admin_email: EmailStr = Field(..., examples=["admin@acme.com"])
    phone: str | None = Field(None, examples=["+91 9876543210"])
    industry: str | None = Field(None, examples=["Technology"])


class OrganizationInviteRequest(BaseModel):
    email: EmailStr = Field(..., examples=["user@company.com"])
    full_name: str | None = Field(None, examples=["Jane Smith"])
    role: str | None = Field("Admin", examples=["Admin"])


class CreateOrganizationInvitationRequest(BaseModel):
    """Invite Organization payload. The organization is created server-side with a
    backend-generated ID — a client-supplied organization_id is never accepted."""

    email: EmailStr = Field(..., examples=["admin@acme.com"])
    full_name: str = Field(..., min_length=1, examples=["Jane Smith"])
    role_id: str | None = Field("Admin", examples=["Admin"])


class InvitationResponse(BaseModel):
    id: str
    organization_id: str | None = None
    organization_name: str | None = None
    email: str
    full_name: str | None = None
    role: str | None = "Admin"
    subscription_id: str | None = None
    token: str
    status: str
    expires_at: str
    accepted_at: str | None = None
    created_at: str
    invite_url: str | None = None

    class Config:
        from_attributes = True


class NewOrganizationInviteResponse(BaseModel):
    organization: dict
    invitation: InvitationResponse
    message: str


class AcceptInvitationRequest(BaseModel):
    password: str = Field(..., min_length=6, examples=["Password123!"])
    full_name: str | None = Field(None, examples=["Jane Smith"])
    organization_name: str | None = Field(None, examples=["Acme Corporation"])
    domain: str | None = Field(None, examples=["acme.crm.com"])
    industry: str | None = Field(None, examples=["Technology"])
    country: str | None = Field(None, examples=["India"])
    city: str | None = Field(None, examples=["Chennai"])
    phone: str | None = Field(None, examples=["+91 9876543210"])


class InviteUserResponse(BaseModel):
    token: str
    invite_url: str
    message: str


class InvitationStatusResponse(BaseModel):
    organization: dict | None = None
    email: str
    full_name: str | None = None
    role: str | None = "Admin"
    expires_at: str
    status: str
    is_valid: bool


class InvitationListResponse(BaseModel):
    total: int
    invitations: list[InvitationResponse]


class SuperAdminOrgResponse(BaseModel):
    organization: dict
    subscription: dict
    invitation: InvitationResponse
    message: str
