from datetime import datetime

from pydantic import BaseModel


class ActivityResponse(BaseModel):
    id: str
    module: str
    action: str
    description: str | None = None
    entity_type: str
    entity_id: str
    actor_id: str | None = None
    occurred_at: datetime
    href: str
