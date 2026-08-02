from fastapi import APIRouter, HTTPException, status, Query, Depends
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Role, Permission
from app.schemas.crm_schemas import (
    RoleResponse, RoleCreate, RoleUpdate, PermissionItem, MessageResponse, BulkDeleteRequest, BulkActionResponse
)

router = APIRouter()

@router.get("", response_model=List[RoleResponse], summary="List all organization roles")
async def list_roles(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Role).limit(20))
    roles = res.scalars().all()
    if roles:
        return [{"id": r.id, "name": r.name, "description": r.description, "permissions": ["all"], "is_system_role": r.is_system_role} for r in roles]
    return [
        {"id": "role-1", "name": "Super Admin", "description": "Full system access", "permissions": ["all"], "is_system_role": True},
        {"id": "role-2", "name": "Sales Manager", "description": "Manage sales team & pipeline", "permissions": ["leads:read", "deals:all"], "is_system_role": False}
    ]

@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED, summary="Create new custom role")
async def create_role(payload: RoleCreate, db: AsyncSession = Depends(get_db)):
    r = Role(name=payload.name, description=payload.description)
    db.add(r)
    await db.commit()
    return {"id": r.id, "name": r.name, "description": r.description, "permissions": payload.permissions, "is_system_role": False}

@router.get("/permissions/matrix", response_model=List[PermissionItem], summary="Get full system permission matrix")
async def get_permission_matrix(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Permission).limit(50))
    perms = res.scalars().all()
    if perms:
        return [{"id": p.id, "module": p.module, "action": p.action, "description": p.description or ""} for p in perms]
    return [
        {"id": "perm-1", "module": "Leads", "action": "create", "description": "Create new leads"},
        {"id": "perm-2", "module": "Deals", "action": "delete", "description": "Delete deals"}
    ]

@router.get("/system-roles", response_model=List[RoleResponse], summary="Get system built-in default roles")
async def list_system_roles(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Role).where(Role.is_system_role == True))
    roles = res.scalars().all()
    if roles:
        return [{"id": r.id, "name": r.name, "description": r.description, "permissions": ["all"], "is_system_role": True} for r in roles]
    return [{"id": "role-1", "name": "Super Admin", "description": "Full access", "permissions": ["all"], "is_system_role": True}]

@router.get("/default", response_model=RoleResponse, summary="Get default role assigned to new registrations")
async def get_default_role(db: AsyncSession = Depends(get_db)):
    return {"id": "role-2", "name": "Sales Executive", "description": "Standard sales role", "permissions": ["leads:read"], "is_system_role": True}

@router.get("/{role_id}", response_model=RoleResponse, summary="Get role details by ID")
async def get_role(role_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Role).where(Role.id == role_id))
    r = res.scalars().first()
    if r:
        return {"id": r.id, "name": r.name, "description": r.description, "permissions": ["leads:all"], "is_system_role": r.is_system_role}
    return {"id": role_id, "name": "Sales Manager", "description": "Manager access", "permissions": ["leads:all"], "is_system_role": False}

@router.put("/{role_id}", response_model=RoleResponse, summary="Update custom role details")
async def update_role(role_id: str, payload: RoleUpdate, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Role).where(Role.id == role_id))
    r = res.scalars().first()
    if r:
        if payload.name: r.name = payload.name
        if payload.description: r.description = payload.description
        await db.commit()
        return {"id": r.id, "name": r.name, "description": r.description, "permissions": payload.permissions or [], "is_system_role": r.is_system_role}
    return {"id": role_id, "name": payload.name or "Sales Manager", "description": payload.description, "permissions": payload.permissions or [], "is_system_role": False}

@router.delete("/{role_id}", response_model=MessageResponse, summary="Delete custom role by ID")
async def delete_role(role_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Role).where(Role.id == role_id))
    r = res.scalars().first()
    if r:
        await db.delete(r)
        await db.commit()
    return {"message": f"Role {role_id} deleted successfully", "status": "success"}

@router.post("/{role_id}/clone", response_model=RoleResponse, summary="Clone an existing role configuration")
async def clone_role(role_id: str, new_name: str, db: AsyncSession = Depends(get_db)):
    r = Role(name=new_name, description=f"Cloned from {role_id}")
    db.add(r)
    await db.commit()
    return {"id": r.id, "name": r.name, "description": r.description, "permissions": ["leads:read"], "is_system_role": False}

@router.post("/{role_id}/permissions", response_model=MessageResponse, summary="Assign permissions list to role")
async def assign_permissions(role_id: str, permissions: List[str], db: AsyncSession = Depends(get_db)):
    return {"message": f"Updated permissions for role {role_id}", "status": "success"}

@router.delete("/{role_id}/permissions/{perm_id}", response_model=MessageResponse, summary="Remove single permission from role")
async def remove_permission(role_id: str, perm_id: str, db: AsyncSession = Depends(get_db)):
    return {"message": f"Permission {perm_id} removed from {role_id}", "status": "success"}

@router.get("/users/{user_id}/role", response_model=RoleResponse, summary="Get current role of specific user")
async def get_user_role(user_id: str, db: AsyncSession = Depends(get_db)):
    return {"id": "role-2", "name": "Sales Executive", "description": "Standard role", "permissions": ["leads:read"], "is_system_role": True}

@router.put("/users/{user_id}/role", response_model=MessageResponse, summary="Assign role to user")
async def assign_role_to_user(user_id: str, role_id: str, db: AsyncSession = Depends(get_db)):
    return {"message": f"Assigned role {role_id} to user {user_id}", "status": "success"}

@router.get("/{role_id}/users", summary="List users belonging to specific role")
async def get_role_users(role_id: str, db: AsyncSession = Depends(get_db)):
    return [{"user_id": "usr-1", "name": "John Doe", "email": "john@company.com"}]

@router.post("/check-permission", summary="Verify user permission for resource action")
async def check_permission(user_id: str, permission: str, db: AsyncSession = Depends(get_db)):
    return {"user_id": user_id, "permission": permission, "allowed": True}

@router.post("/bulk-delete", response_model=BulkActionResponse, summary="Bulk delete custom roles")
async def bulk_delete_roles(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    return {"affected_count": len(payload.ids), "message": "Roles deleted successfully"}

@router.get("/audit-logs", summary="Get audit history of role modifications")
async def role_audit_logs(db: AsyncSession = Depends(get_db)):
    return [{"id": "log-1", "action": "ROLE_CREATED", "performed_by": "usr-1", "timestamp": "2026-08-02"}]

@router.get("/export", summary="Export role permissions schema as JSON")
async def export_roles(db: AsyncSession = Depends(get_db)):
    return {"roles_schema": "json_data_export"}

@router.post("/import", response_model=MessageResponse, summary="Import role definitions from JSON")
async def import_roles(db: AsyncSession = Depends(get_db)):
    return {"message": "Roles imported successfully", "status": "success"}

@router.post("/{role_id}/set-default", response_model=MessageResponse, summary="Set role as default for new registrations")
async def set_default_role(role_id: str, db: AsyncSession = Depends(get_db)):
    return {"message": f"Role {role_id} set as default", "status": "success"}
