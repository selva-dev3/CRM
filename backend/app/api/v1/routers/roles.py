from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import (
    authorize_permission,
    get_current_user,
    require_permission,
    require_platform_admin,
)
from app.core.errors import ForbiddenError
from app.core.permissions import effective_organization_id
from app.db.session import get_db
from app.models import User
from app.schemas.crm_schemas import (
    BulkActionResponse,
    BulkDeleteRequest,
    MessageResponse,
    PermissionCreate,
    PermissionItem,
    RoleAuditLogResponse,
    RoleCreate,
    RoleResponse,
    RoleUpdate,
    SetDefaultRolesRequest,
)
from app.services.role_service import role_service

router = APIRouter()


def _current_organization_id(current_user: User) -> str:
    organization_id = effective_organization_id(current_user)
    if not organization_id:
        raise ForbiddenError(message="Authenticated user has no current organization")
    return organization_id


@router.get(
    "",
    response_model=list[RoleResponse],
    summary="List roles scoped to the current organization",
    dependencies=[Depends(require_permission("roles:read"))],
)
async def list_roles(
    response: Response,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Roles are derived from the authenticated user's current organization —
    # a client-supplied organization_id is never accepted for role search.
    org_id = _current_organization_id(current_user)
    roles = await role_service.list_roles(db, search, org_id=org_id, page=page, limit=limit)
    total = await role_service.count_roles(db, search, org_id=org_id)
    response.headers["X-Total-Count"] = str(total)
    return roles


@router.post(
    "",
    response_model=RoleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new custom role",
    dependencies=[Depends(require_permission("roles:create"))],
)
async def create_role(
    payload: RoleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.permissions:
        await authorize_permission(db, current_user, "roles:assign")
    return await role_service.create_role(db, payload, current_user)


@router.get(
    "/permissions/matrix",
    response_model=list[PermissionItem],
    summary="Get full system permission matrix directly from DB",
    dependencies=[Depends(require_permission("roles:read"))],
)
async def get_permission_matrix(db: AsyncSession = Depends(get_db)):
    return await role_service.get_permission_matrix(db)


@router.post(
    "/permissions",
    response_model=PermissionItem,
    status_code=status.HTTP_201_CREATED,
    summary="Create new permission entry",
    dependencies=[Depends(require_permission("roles:create")), Depends(require_platform_admin)],
)
async def create_permission(payload: PermissionCreate, db: AsyncSession = Depends(get_db)):
    return await role_service.create_permission(db, payload)


@router.post(
    "/permissions/batch-import",
    response_model=MessageResponse,
    summary="Batch import permissions list from JSON",
    dependencies=[Depends(require_permission("roles:create")), Depends(require_platform_admin)],
)
async def import_permissions_batch(
    payload: list[PermissionCreate], db: AsyncSession = Depends(get_db)
):
    return await role_service.import_permissions_batch(db, payload)


@router.get(
    "/system-roles",
    response_model=list[RoleResponse],
    summary="Get system built-in default roles",
    dependencies=[Depends(require_permission("roles:read"))],
)
async def list_system_roles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await role_service.list_system_roles(db, current_user)


@router.get(
    "/assignable",
    response_model=list[RoleResponse],
    summary="List roles that may be assigned to users (excludes super_admin)",
    dependencies=[Depends(require_permission("roles:read"))],
)
async def list_assignable_roles(
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = _current_organization_id(current_user)
    return await role_service.list_assignable_roles(db, search, org_id=org_id)


@router.post(
    "/set-defaults",
    response_model=MessageResponse,
    summary="Set multiple roles as default for new registrations",
    dependencies=[Depends(require_permission("roles:update"))],
)
async def set_multiple_default_roles(
    payload: SetDefaultRolesRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await role_service.set_multiple_default_roles(db, payload.role_ids, current_user)


@router.get(
    "/default",
    response_model=RoleResponse,
    summary="Get default role assigned to new registrations",
    dependencies=[Depends(require_permission("roles:read"))],
)
async def get_default_role(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await role_service.get_default_role(db, current_user)


@router.get(
    "/audit-logs",
    response_model=list[RoleAuditLogResponse],
    summary="Get audit history of role modifications",
    dependencies=[Depends(require_permission("roles:read"))],
)
async def role_audit_logs(
    response: Response,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    logs = await role_service.role_audit_logs(db, current_user, page=page, limit=limit)
    response.headers["X-Total-Count"] = str(
        await role_service.count_role_audit_logs(db, current_user)
    )
    return logs


@router.get(
    "/export",
    summary="Export role permissions schema as JSON",
    dependencies=[Depends(require_permission("roles:read"))],
)
async def export_roles(db: AsyncSession = Depends(get_db)):
    return await role_service.export_roles()


@router.post(
    "/import",
    response_model=MessageResponse,
    summary="Import role definitions from JSON",
    dependencies=[Depends(require_permission("roles:create"))],
)
async def import_roles(db: AsyncSession = Depends(get_db)):
    return await role_service.import_roles()


@router.post(
    "/bulk-delete",
    response_model=BulkActionResponse,
    summary="Bulk delete custom roles",
    dependencies=[Depends(require_permission("roles:delete"))],
)
async def bulk_delete_roles(
    payload: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await role_service.bulk_delete_roles(db, payload.ids, current_user)


@router.get(
    "/users/{user_id}/role",
    response_model=RoleResponse,
    summary="Get current role of specific user",
    dependencies=[
        Depends(require_permission("roles:read")),
        Depends(require_permission("users:roles")),
    ],
)
async def get_user_role(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await role_service.get_user_role(db, user_id, current_user)


@router.put(
    "/users/{user_id}/role",
    response_model=MessageResponse,
    summary="Assign role to user",
    dependencies=[Depends(require_permission("users:assign_roles"))],
)
async def assign_role_to_user(
    user_id: str,
    role_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await role_service.assign_role_to_user(db, user_id, role_id, current_user)


@router.post(
    "/check-permission",
    summary="Verify user permission for resource action",
    dependencies=[
        Depends(require_permission("roles:read")),
        Depends(require_permission("users:roles")),
    ],
)
async def check_permission(
    user_id: str = Query(...),
    permission: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await role_service.check_permission(db, user_id, permission, current_user)


@router.get(
    "/{role_id}",
    response_model=RoleResponse,
    summary="Get role details by ID",
    dependencies=[Depends(require_permission("roles:read"))],
)
async def get_role(
    role_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await role_service.get_role(db, role_id, current_user)


@router.put(
    "/{role_id}",
    response_model=RoleResponse,
    summary="Update custom role details",
    dependencies=[Depends(require_permission("roles:update"))],
)
async def update_role(
    role_id: str,
    payload: RoleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.permissions is not None:
        await authorize_permission(db, current_user, "roles:assign")
    return await role_service.update_role(db, role_id, payload, current_user)


@router.delete(
    "/{role_id}",
    response_model=MessageResponse,
    summary="Delete custom role by ID",
    dependencies=[Depends(require_permission("roles:delete"))],
)
async def delete_role(
    role_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await role_service.delete_role(db, role_id, current_user)


@router.post(
    "/{role_id}/clone",
    response_model=RoleResponse,
    summary="Clone an existing role configuration",
    dependencies=[
        Depends(require_permission("roles:create")),
        Depends(require_permission("roles:assign")),
    ],
)
async def clone_role(
    role_id: str,
    new_name: str = Query("Cloned Role"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await role_service.clone_role(db, role_id, new_name, current_user)


@router.post(
    "/{role_id}/permissions",
    response_model=MessageResponse,
    summary="Assign permissions list to role",
    dependencies=[Depends(require_permission("roles:assign"))],
)
async def assign_permissions(
    role_id: str,
    permissions: list[str],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await role_service.assign_permissions(db, role_id, permissions, current_user)


@router.delete(
    "/{role_id}/permissions/{perm_id}",
    response_model=MessageResponse,
    summary="Remove single permission from role",
    dependencies=[Depends(require_permission("roles:assign"))],
)
async def remove_permission(
    role_id: str,
    perm_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await role_service.remove_permission(db, role_id, perm_id, current_user)


@router.get(
    "/{role_id}/users",
    summary="List users belonging to specific role",
    dependencies=[
        Depends(require_permission("roles:read")),
        Depends(require_permission("users:read")),
    ],
)
async def get_role_users(
    role_id: str,
    response: Response,
    page: int = Query(1, ge=1),
    limit: int = Query(15, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    users = await role_service.get_role_users(db, role_id, current_user, page=page, limit=limit)
    response.headers["X-Total-Count"] = str(
        await role_service.count_role_users(db, role_id, current_user)
    )
    return users


@router.post(
    "/{role_id}/set-default",
    response_model=MessageResponse,
    summary="Toggle role as default for new registrations",
    dependencies=[Depends(require_permission("roles:update"))],
)
async def set_default_role(
    role_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await role_service.set_default_role(db, role_id, current_user)
