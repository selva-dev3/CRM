from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.repositories.activity_repository import (
    ActivityRepository,
    activity_repository,
)
from app.services.auth_service import api_key_scope_allows, auth_service

MODULE_PERMISSIONS = {
    "leads": "leads:read",
    "deals": "deals:read",
    "tasks": "tasks:read",
    "meetings": "meetings:read",
    "calls": "calls:read",
    "emails": "emails:read",
    "notes": "notes:read",
    "calendar": "calendar:read",
}

ENTITY_HREFS = {
    "lead": "/leads/{id}",
    "contact": "/contacts/{id}",
    "company": "/companies/{id}",
    "deal": "/deals/{id}",
    "task": "/tasks/{id}",
    "meeting": "/meetings/{id}",
    "call": "/calls/{id}",
    "email": "/email",
    "calendar": "/calendar",
    "whatsapp_conversation": "/whatsapp",
}


class ActivityService:
    def __init__(self, repository: ActivityRepository | None = None) -> None:
        self.repository = repository or activity_repository

    async def allowed_modules(
        self, db: AsyncSession, current_user: User
    ) -> tuple[set[str], set[str]]:
        permissions = {
            permission
            for permission in await auth_service.get_user_permissions(db, current_user)
            if api_key_scope_allows(current_user, permission)
        }
        modules = {
            module for module, permission in MODULE_PERMISSIONS.items() if permission in permissions
        }
        whatsapp_permissions = permissions & {"whatsapp:read_assigned", "whatsapp:read_all"}
        if whatsapp_permissions:
            modules.add("whatsapp")
        return modules, whatsapp_permissions

    @staticmethod
    def serialize(row) -> dict:
        entity_type = row["entity_type"]
        entity_id = row["entity_id"]
        href_template = ENTITY_HREFS.get(entity_type, "/notes")
        return {
            "id": f"{row['module']}:{row['source_id']}",
            "module": row["module"],
            "action": row["action"],
            "description": row["description"],
            "entity_type": entity_type,
            "entity_id": entity_id,
            "actor_id": row["actor_id"],
            "occurred_at": row["occurred_at"],
            "href": href_template.format(id=entity_id),
        }

    async def list_activities(
        self,
        db: AsyncSession,
        current_user: User,
        *,
        organization_id: str,
        page: int,
        limit: int,
        module: str | None,
        search: str | None,
    ) -> tuple[list[dict], int]:
        modules, whatsapp_permissions = await self.allowed_modules(db, current_user)
        if module:
            modules &= {module}
        kwargs = {
            "organization_id": organization_id,
            "modules": modules,
            "user_id": current_user.id,
            "whatsapp_permissions": whatsapp_permissions,
            "search": search,
        }
        rows = await self.repository.list(db, page=page, limit=limit, **kwargs)
        total = await self.repository.count(db, **kwargs)
        return [self.serialize(row) for row in rows], total


activity_service = ActivityService()
