from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class DashboardLayoutCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    is_shared: bool = False
    widgets: list[dict] = Field(default_factory=list, max_length=30)
    filters: dict = Field(default_factory=dict)


class DashboardLayoutUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    is_shared: bool | None = None
    widgets: list[dict] | None = Field(default=None, max_length=30)
    filters: dict | None = None

    @model_validator(mode="after")
    def reject_null_required_fields(self):
        for field in {"name", "is_shared", "widgets", "filters"}:
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class DashboardLayoutResponse(BaseModel):
    id: str
    owner_id: str | None
    name: str
    description: str | None
    is_shared: bool
    widgets: list[dict]
    filters: dict
    created_at: datetime
    updated_at: datetime
