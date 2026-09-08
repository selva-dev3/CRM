from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.crm_schemas import OrganizationResponse


class InitialAdminInvitation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=255)
    email: EmailStr


class PlatformOrganizationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=255)
    initial_admin: InitialAdminInvitation | None = None

    @field_validator("name")
    @classmethod
    def require_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Organization name is required")
        return value.strip()


class ProvisionedInvitation(BaseModel):
    id: str
    delivery_status: Literal["sent", "failed"]


class OrganizationCreateResponse(BaseModel):
    organization: OrganizationResponse
    invitation: ProvisionedInvitation | None = None


class OrganizationDeletionResponse(BaseModel):
    message: str
    status: Literal["success"] = "success"
    operation_id: str
    cleanup_status: Literal["pending", "complete", "failed"]


class OrganizationDeletionStatus(BaseModel):
    id: str
    organization_id: str
    organization_name: str
    cleanup_status: Literal["pending", "complete", "failed"]
    pending_files: int
    failed_files: int
    completed_files: int
    created_at: datetime
