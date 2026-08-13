from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.crm_schemas import (
    BulkActionResponse,
    BulkDeleteRequest,
    MessageResponse,
    PermissionCreate,
    PermissionItem,
    RoleCreate,
    RoleResponse,
    RoleUpdate,
    SetDefaultRolesRequest,
)
from app.services.role_service import role_service

router = APIRouter()


@router.get("", response_model=List[RoleResponse], summary="List all organization roles")
async def list_roles(search: Optional[str] = Query(None), db: AsyncSession = Depends(get_db)):
    return await role_service.list_roles(db, search)


@router.post(
    "", response_model=RoleResponse, status_code=status.HTTP_201_CREATED, summary="Create new custom role"
)
async def create_role(payload: RoleCreate, db: AsyncSession = Depends(get_db)):
    return await role_service.create_role(db, payload)


@router.get(
    "/permissions/matrix",
    response_model=List[PermissionItem],
    summary="Get full system permission matrix directly from DB",
)
async def get_permission_matrix(db: AsyncSession = Depends(get_db)):
    return await role_service.get_permission_matrix(db)


@router.post(
    "/permissions",
    response_model=PermissionItem,
    status_code=status.HTTP_201_CREATED,
    summary="Create new permission entry",
)
async def create_permission(payload: PermissionCreate, db: AsyncSession = Depends(get_db)):
    return await role_service.create_permission(db, payload)


@router.post(
    "/permissions/batch-import",
    response_model=MessageResponse,
    summary="Batch import permissions list from JSON",
)
async def import_permissions_batch(payload: List[PermissionCreate], db: AsyncSession = Depends(get_db)):
    return await role_service.import_permissions_batch(db, payload)


@router.get("/system-roles", response_model=List[RoleResponse], summary="Get system built-in default roles")
async def list_system_roles(db: AsyncSession = Depends(get_db)):
    return await role_service.list_system_roles(db)


@router.post("/set-defaults", response_model=MessageResponse, summary="Set multiple roles as default for new registrations")
async def set_multiple_default_roles(payload: SetDefaultRolesRequest, db: AsyncSession = Depends(get_db)):
    return await role_service.set_multiple_default_roles(db, payload.role_ids)


@router.get("/default", response_model=RoleResponse, summary="Get default role assigned to new registrations")
async def get_default_role(db: AsyncSession = Depends(get_db)):
    return await role_service.get_default_role(db)


@router.get("/audit-logs", summary="Get audit history of role modifications")
async def role_audit_logs(db: AsyncSession = Depends(get_db)):
    return await role_service.role_audit_logs()


@router.get("/export", summary="Export role permissions schema as JSON")
async def export_roles(db: AsyncSession = Depends(get_db)):
    return await role_service.export_roles()


@router.post("/import", response_model=MessageResponse, summary="Import role definitions from JSON")
async def import_roles(db: AsyncSession = Depends(get_db)):
    return await role_service.import_roles()


@router.post("/bulk-delete", response_model=BulkActionResponse, summary="Bulk delete custom roles")
async def bulk_delete_roles(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    return await role_service.bulk_delete_roles(db, payload.ids)


@router.get("/users/{user_id}/role", response_model=RoleResponse, summary="Get current role of specific user")
async def get_user_role(user_id: str, db: AsyncSession = Depends(get_db)):
    return await role_service.get_user_role(db, user_id)


@router.put("/users/{user_id}/role", response_model=MessageResponse, summary="Assign role to user")
async def assign_role_to_user(
    user_id: str, role_id: str = Query("sys-manager"), db: AsyncSession = Depends(get_db)
):
    return await role_service.assign_role_to_user(db, user_id, role_id)


@router.post("/check-permission", summary="Verify user permission for resource action")
async def check_permission(
    user_id: str = Query("usr-1"),
    permission: str = Query("leads:create"),
    db: AsyncSession = Depends(get_db),
):
    return await role_service.check_permission(db, user_id, permission)


@router.get("/{role_id}", response_model=RoleResponse, summary="Get role details by ID")
async def get_role(role_id: str, db: AsyncSession = Depends(get_db)):
    return await role_service.get_role(db, role_id)


@router.put("/{role_id}", response_model=RoleResponse, summary="Update custom role details")
async def update_role(role_id: str, payload: RoleUpdate, db: AsyncSession = Depends(get_db)):
    return await role_service.update_role(db, role_id, payload)


@router.delete("/{role_id}", response_model=MessageResponse, summary="Delete custom role by ID")
async def delete_role(role_id: str, db: AsyncSession = Depends(get_db)):
    return await role_service.delete_role(db, role_id)


@router.post("/{role_id}/clone", response_model=RoleResponse, summary="Clone an existing role configuration")
async def clone_role(role_id: str, new_name: str = Query("Cloned Role"), db: AsyncSession = Depends(get_db)):
    return await role_service.clone_role(db, role_id, new_name)


@router.post("/{role_id}/permissions", response_model=MessageResponse, summary="Assign permissions list to role")
async def assign_permissions(role_id: str, permissions: List[str], db: AsyncSession = Depends(get_db)):
    return await role_service.assign_permissions(db, role_id, permissions)


@router.delete("/{role_id}/permissions/{perm_id}", response_model=MessageResponse, summary="Remove single permission from role")
async def remove_permission(role_id: str, perm_id: str, db: AsyncSession = Depends(get_db)):
    return await role_service.remove_permission(db, role_id, perm_id)


@router.get("/{role_id}/users", summary="List users belonging to specific role")
async def get_role_users(role_id: str, db: AsyncSession = Depends(get_db)):
    return await role_service.get_role_users(db, role_id)


@router.post("/{role_id}/set-default", response_model=MessageResponse, summary="Toggle role as default for new registrations")
async def set_default_role(role_id: str, db: AsyncSession = Depends(get_db)):
    return await role_service.set_default_role(db, role_id)