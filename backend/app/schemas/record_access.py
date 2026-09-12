from typing import Literal

from pydantic import BaseModel, field_validator

RecordScope = Literal["all", "team", "assigned", "own", "none"]
RECORD_SCOPE_MODULES = (
    "leads",
    "contacts",
    "companies",
    "deals",
    "tasks",
    "projects",
    "tickets",
    "documents",
    "quotes",
    "orders",
    "invoices",
    "payments",
)


class RoleRecordScopeItem(BaseModel):
    module: Literal[
        "leads",
        "contacts",
        "companies",
        "deals",
        "tasks",
        "projects",
        "tickets",
        "documents",
        "quotes",
        "orders",
        "invoices",
        "payments",
    ]
    scope: RecordScope


class RoleRecordScopeUpdate(BaseModel):
    scopes: list[RoleRecordScopeItem]

    @field_validator("scopes")
    @classmethod
    def reject_duplicate_modules(
        cls, value: list[RoleRecordScopeItem]
    ) -> list[RoleRecordScopeItem]:
        modules = [item.module for item in value]
        if len(modules) != len(set(modules)):
            raise ValueError("Each record-scope module may appear only once")
        return value
