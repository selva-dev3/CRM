from datetime import datetime

from pydantic import BaseModel, Field


class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    manager_id: str | None = None


class TeamUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    manager_id: str | None = None
    is_active: bool | None = None


class TeamMemberUpdate(BaseModel):
    user_id: str
    is_primary: bool = False


class TeamMemberResponse(BaseModel):
    user_id: str
    name: str
    email: str
    is_primary: bool


class TeamResponse(BaseModel):
    id: str
    name: str
    description: str | None
    manager_id: str | None
    is_active: bool
    member_count: int = 0
    created_at: datetime


class TeamDetailResponse(TeamResponse):
    members: list[TeamMemberResponse] = []
