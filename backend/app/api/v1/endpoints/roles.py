from fastapi import APIRouter
from typing import List
from app.schemas.crm_schemas import RoleResponse, RoleCreate

router = APIRouter()

@router.get("/", response_model=List[RoleResponse], summary="List custom & system roles")
async def list_roles():
    """Returns list of predefined RBAC roles and custom user roles."""
    return [
        {"id": "role-1", "name": "Super Admin", "description": "Full system access", "permissions": ["*"], "is_system_role": True},
        {"id": "role-2", "name": "Sales Executive", "description": "Access to assigned leads and deals", "permissions": ["leads:read", "deals:write"], "is_system_role": True},
    ]

@router.post("/", response_model=RoleResponse, summary="Create custom RBAC role")
async def create_role(payload: RoleCreate):
    """Creates a custom role with specified permission scopes."""
    return {"id": "role-3", "name": payload.name, "description": payload.description, "permissions": payload.permissions, "is_system_role": False}
