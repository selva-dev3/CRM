from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.ai import CRMSearchPlan


class SearchToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: CRMSearchPlan


class RecordToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: str = Field(min_length=1, max_length=100)


class EmptyToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AIToolRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str | None = None


class AIToolResult(BaseModel):
    records: list[AIToolRecord] = Field(default_factory=list)
    result_count: int = Field(ge=0)

    def dictionaries(self) -> list[dict[str, Any]]:
        return [record.model_dump(exclude_none=True) for record in self.records]
