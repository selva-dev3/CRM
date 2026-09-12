from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field, model_validator


class WorkflowCondition(BaseModel):
    field: str = Field(min_length=1, max_length=100)
    operator: Literal["equals", "not_equals", "changed"] = "equals"
    value: str | int | float | bool | None = None


class AssignAction(BaseModel):
    type: Literal["assign"]
    user_id: str = Field(min_length=1)


class UpdateFieldAction(BaseModel):
    type: Literal["update_field"]
    field: str = Field(min_length=1, max_length=100)
    value: str | int | float | bool | None = None


class CreateTaskAction(BaseModel):
    type: Literal["create_task"]
    title: str = Field(default="Workflow follow-up", min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10000)
    priority: Literal["Low", "Medium", "High", "Urgent"] = "Medium"
    due_days: int = Field(default=1, ge=0, le=3650)
    assigned_to: str | None = None


class NotificationAction(BaseModel):
    type: Literal["notification"]
    user_id: str | None = None
    title: str = Field(default="Workflow notification", min_length=1, max_length=255)
    message: str | None = Field(default=None, max_length=10000)


class EmailAction(BaseModel):
    type: Literal["email"]
    to_email: EmailStr
    subject: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1, max_length=100000)


class WebhookAction(BaseModel):
    type: Literal["webhook"]
    integration_id: str = Field(min_length=1)


WorkflowAction = Annotated[
    AssignAction
    | UpdateFieldAction
    | CreateTaskAction
    | NotificationAction
    | EmailAction
    | WebhookAction,
    Field(discriminator="type"),
]


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=1000)
    module: Literal["leads", "deals", "tasks", "projects", "tickets"]
    trigger: Literal["record.created", "record.updated", "record.status_changed"]
    conditions: list[WorkflowCondition] = Field(default_factory=list, max_length=20)
    actions: list[WorkflowAction] = Field(min_length=1, max_length=20)
    is_active: bool = False


class WorkflowUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=1000)
    trigger: Literal["record.created", "record.updated", "record.status_changed"] | None = None
    conditions: list[WorkflowCondition] | None = Field(default=None, max_length=20)
    actions: list[WorkflowAction] | None = Field(default=None, min_length=1, max_length=20)
    is_active: bool | None = None

    @model_validator(mode="after")
    def reject_null_required_fields(self):
        for field in {"name", "trigger", "conditions", "actions", "is_active"}:
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class WorkflowResponse(BaseModel):
    id: str
    name: str
    description: str | None
    module: str
    trigger: str
    conditions: list[dict]
    actions: list[dict]
    is_active: bool
    created_by: str | None
    created_at: datetime
    updated_at: datetime


class WorkflowRunResponse(BaseModel):
    id: str
    status: str
    action_results: list[dict]
    error: str | None
    started_at: datetime
    finished_at: datetime | None
