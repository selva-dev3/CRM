from typing import Literal

from pydantic import BaseModel, field_validator

from app.core.rbac_matrix import RECORD_SCOPE_MODULES as RECORD_SCOPE_MODULES

RecordScope = Literal["all", "team", "assigned", "own", "none"]


class RoleRecordScopeItem(BaseModel):
    module: Literal[
        "leads",
        "contacts",
        "companies",
        "deals",
        "tasks",
        "activities",
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
