from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

MilestoneStatus = Literal["Pending", "In Progress", "Completed", "Cancelled"]


def validate_date_value(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            date.fromisoformat(value)
        except ValueError as error:
            raise ValueError("Due date must be a valid ISO date or datetime") from error
    return value


class MilestoneBase(BaseModel):
    project_id: str
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    status: MilestoneStatus = "Pending"
    due_date: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Milestone name is required")
        return value.strip()

    @field_validator("due_date")
    @classmethod
    def validate_due_date(cls, value: str | None) -> str | None:
        return validate_date_value(value)


class MilestoneCreate(MilestoneBase):
    pass


class MilestoneUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    status: MilestoneStatus | None = None
    due_date: str | None = None

    @field_validator("name", "status", mode="before")
    @classmethod
    def reject_null_required_fields(cls, value: object) -> object:
        if value is None:
            raise ValueError("Field cannot be null")
        return value

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Milestone name is required")
        return value.strip() if value else value

    @field_validator("due_date")
    @classmethod
    def validate_due_date(cls, value: str | None) -> str | None:
        return validate_date_value(value)

    @model_validator(mode="after")
    def reject_empty_update(self):
        if not self.model_fields_set:
            raise ValueError("At least one milestone field is required")
        return self


class MilestoneResponse(MilestoneBase):
    id: str
    completed_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
