from pydantic import BaseModel, Field


class ProjectBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    status: str = Field(default="Planning", max_length=50)
    priority: str = Field(default="Medium", max_length=50)
    owner_id: str | None = None
    start_date: str | None = None
    due_date: str | None = None
    budget: float | None = Field(default=None, ge=0)
    completion_percentage: int = Field(default=0, ge=0, le=100)


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = Field(default=None, max_length=50)
    priority: str | None = Field(default=None, max_length=50)
    owner_id: str | None = None
    start_date: str | None = None
    due_date: str | None = None
    budget: float | None = Field(default=None, ge=0)
    completion_percentage: int | None = Field(default=None, ge=0, le=100)


class ProjectResponse(ProjectBase):
    id: str
    organization_id: str
    created_at: str | None = None
    updated_at: str | None = None
