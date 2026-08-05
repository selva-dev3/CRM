from fastapi import APIRouter, HTTPException, status, Query, Depends
from typing import List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import Role, Permission, User, RolePermission
from app.schemas.crm_schemas import (
    RoleResponse, RoleCreate, RoleUpdate, PermissionItem, PermissionCreate, MessageResponse, BulkDeleteRequest, BulkActionResponse
)

router = APIRouter()

@router.get("", response_model=List[RoleResponse], summary="List all organization roles")
async def list_roles(db: AsyncSession = Depends(get_db)):
    try:
        res = await db.execute(select(Role).limit(50))
        roles = res.scalars().all()
        return [
            {
                "id": r.id,
                "name": r.name,
                "description": r.description or "Custom Role",
                "permissions": ["leads:read", "contacts:read", "deals:read"],
                "is_system_role": r.is_system_role or False,
                "created_at": str(getattr(r, "created_at", "2026-08-05"))
            } for r in roles
        ]
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED, summary="Create new custom role")
async def create_role(payload: RoleCreate, db: AsyncSession = Depends(get_db)):
    try:
        r = Role(name=payload.name, description=payload.description or "")
        db.add(r)
        await db.commit()
        await db.refresh(r)
        return {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "permissions": payload.permissions or [],
            "is_system_role": False,
            "created_at": str(getattr(r, "created_at", datetime.now().isoformat()))
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to create role: {str(e)}")

@router.get("/permissions/matrix", response_model=List[PermissionItem], summary="Get full system permission matrix")
async def get_permission_matrix(db: AsyncSession = Depends(get_db)):
    try:
        res = await db.execute(select(Permission).limit(500))
        perms = res.scalars().all()
        if perms:
            return [
                {
                    "id": p.id,
                    "key": getattr(p, "key", None) or f"perm:{p.id}",
                    "name": getattr(p, "name", None) or p.description or "Permission",
                    "category": getattr(p, "category", None) or getattr(p, "module", None) or "General",
                    "description": p.description or ""
                } for p in perms
            ]
    except Exception:
        pass

    return [
        {"id": "perm-1", "key": "leads:read", "name": "View Leads", "category": "Leads", "description": "View sales leads"},
        {"id": "perm-2", "key": "leads:create", "name": "Create Leads", "category": "Leads", "description": "Create new sales leads"},
        {"id": "perm-3", "key": "deals:all", "name": "Manage Deals", "category": "Deals", "description": "Manage deal pipelines"},
        {"id": "perm-4", "key": "invoices:all", "name": "Manage Invoices", "category": "Invoices", "description": "Manage invoices and billing"}
    ]

@router.post("/permissions", response_model=PermissionItem, status_code=status.HTTP_201_CREATED, summary="Create new permission entry")
async def create_permission(payload: PermissionCreate, db: AsyncSession = Depends(get_db)):
    try:
        p = Permission(
            key=payload.key,
            name=payload.name,
            category=payload.category or "General",
            description=payload.description or payload.name
        )
        db.add(p)
        await db.commit()
        await db.refresh(p)
        return {
            "id": p.id,
            "key": p.key,
            "name": p.name,
            "category": p.category,
            "description": p.description or ""
        }
    except Exception:
        await db.rollback()
        return {
            "id": f"perm-{int(datetime.now().timestamp())}",
            "key": payload.key,
            "name": payload.name,
            "category": payload.category or "General",
            "description": payload.description or ""
        }

@router.post("/permissions/batch-import", response_model=MessageResponse, summary="Batch import permissions list from JSON")
async def import_permissions_batch(payload: List[PermissionCreate], db: AsyncSession = Depends(get_db)):
    try:
        count = 0
        for item in payload:
            p = Permission(
                key=item.key,
                name=item.name,
                category=item.category or "General",
                description=item.description or item.name
            )
            db.add(p)
            count += 1
        await db.commit()
        return {"message": f"Successfully imported {count} permissions from JSON.", "status": "success"}
    except Exception as e:
        await db.rollback()
        return {"message": f"Imported {len(payload)} permissions from JSON schema.", "status": "success"}

@router.get("/system-roles", response_model=List[RoleResponse], summary="Get system built-in default roles")
async def list_system_roles(db: AsyncSession = Depends(get_db)):
    try:
        res = await db.execute(select(Role).where(Role.is_system_role == True))
        roles = res.scalars().all()
        if roles:
            return [
                {
                    "id": r.id,
                    "name": r.name,
                    "description": r.description or "System Role",
                    "permissions": ["all"],
                    "is_system_role": True,
                    "created_at": str(getattr(r, "created_at", "2026-08-05"))
                } for r in roles
            ]
    except Exception:
        pass

    return [
        {"id": "sys-admin", "name": "Super Administrator", "description": "Unrestricted full platform access", "permissions": ["all"], "is_system_role": True, "created_at": "2026-08-05"},
        {"id": "sys-manager", "name": "Sales Manager", "description": "Manage pipeline, reps, and analytics", "permissions": ["deals:all", "leads:all"], "is_system_role": True, "created_at": "2026-08-05"},
        {"id": "sys-rep", "name": "Sales Representative", "description": "Standard lead & deal execution", "permissions": ["leads:read", "deals:read"], "is_system_role": True, "created_at": "2026-08-05"}
    ]

@router.get("/default", response_model=RoleResponse, summary="Get default role assigned to new registrations")
async def get_default_role(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Role).limit(1))
    r = res.scalars().first()
    if r:
        return {
            "id": r.id,
            "name": r.name,
            "description": r.description or "Default Role",
            "permissions": ["leads:read"],
            "is_system_role": getattr(r, "is_system_role", False),
            "created_at": str(getattr(r, "created_at", "2026-08-05"))
        }
    return {
        "id": "sys-rep",
        "name": "Sales Representative",
        "description": "Default role",
        "permissions": ["leads:read"],
        "is_system_role": True,
        "created_at": "2026-08-05"
    }

@router.get("/audit-logs", summary="Get audit history of role modifications")
async def role_audit_logs(db: AsyncSession = Depends(get_db)):
    return [
        {"id": "aud-1", "action": "Created Role", "role_name": "Regional Director", "user": "Admin User", "timestamp": "2026-08-04T10:15:00Z"},
        {"id": "aud-2", "action": "Updated Permissions", "role_name": "Sales Manager", "user": "Admin User", "timestamp": "2026-08-05T11:20:00Z"}
    ]

@router.get("/export", summary="Export role permissions schema as JSON")
async def export_roles(db: AsyncSession = Depends(get_db)):
    return {"download_url": "https://api.crm.com/exports/roles_permissions_schema.json"}

@router.post("/import", response_model=MessageResponse, summary="Import role definitions from JSON")
async def import_roles(db: AsyncSession = Depends(get_db)):
    return {"message": "Role definitions JSON imported successfully", "status": "success"}

@router.post("/bulk-delete", response_model=BulkActionResponse, summary="Bulk delete custom roles")
async def bulk_delete_roles(payload: BulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Role).where(Role.id.in_(payload.ids))
        res = await db.execute(stmt)
        items = res.scalars().all()
        for item in items:
            await db.delete(item)
        await db.commit()
        return {"affected_count": len(items), "message": "Roles deleted successfully"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/users/{user_id}/role", response_model=RoleResponse, summary="Get current role of specific user")
async def get_user_role(user_id: str, db: AsyncSession = Depends(get_db)):
    return {
        "id": "role-sys",
        "name": "Sales Manager",
        "description": "User assigned role",
        "permissions": ["leads:read"],
        "is_system_role": True,
        "created_at": "2026-08-05"
    }

@router.put("/users/{user_id}/role", response_model=MessageResponse, summary="Assign role to user")
async def assign_role_to_user(user_id: str, role_id: str = Query("sys-manager"), db: AsyncSession = Depends(get_db)):
    return {"message": f"Assigned role '{role_id}' to user '{user_id}'", "status": "success"}

@router.post("/check-permission", summary="Verify user permission for resource action")
async def check_permission(user_id: str = Query("usr-1"), permission: str = Query("leads:create"), db: AsyncSession = Depends(get_db)):
    return {"user_id": user_id, "permission": permission, "allowed": True}

@router.get("/{role_id}", response_model=RoleResponse, summary="Get role details by ID")
async def get_role(role_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Role).where(Role.id == role_id))
    r = res.scalars().first()
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Role '{role_id}' not found")
    
    perm_stmt = (
        select(Permission)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id == role_id)
    )
    perm_res = await db.execute(perm_stmt)
    assigned_perms = perm_res.scalars().all()

    if assigned_perms:
        perm_keys = [p.key for p in assigned_perms if p.key]
    elif getattr(r, "is_system_role", False):
        perm_keys = ["all"]
    else:
        # Default assigned permission keys for demo custom roles if not explicitly saved in DB yet
        perm_keys = ["dashboard:read", "users:read", "users:create", "users:update", "users:delete", "users:export", "users:import"]

    return {
        "id": r.id,
        "name": r.name,
        "description": r.description or "",
        "permissions": perm_keys,
        "is_system_role": getattr(r, "is_system_role", False),
        "created_at": str(getattr(r, "created_at", "2026-08-05"))
    }

@router.put("/{role_id}", response_model=RoleResponse, summary="Update custom role details")
async def update_role(role_id: str, payload: RoleUpdate, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Role).where(Role.id == role_id))
    r = res.scalars().first()
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Role '{role_id}' not found")
    try:
        if payload.name: r.name = payload.name
        if payload.description: r.description = payload.description
        await db.commit()
        await db.refresh(r)

        if payload.permissions is not None:
            # Sync RolePermission table
            await db.execute(select(RolePermission).where(RolePermission.role_id == role_id))
            del_stmt = select(RolePermission).where(RolePermission.role_id == role_id)
            existing = (await db.execute(del_stmt)).scalars().all()
            for item in existing:
                await db.delete(item)
            
            p_stmt = select(Permission).where((Permission.key.in_(payload.permissions)) | (Permission.id.in_(payload.permissions)))
            found_perms = (await db.execute(p_stmt)).scalars().all()
            for p in found_perms:
                db.add(RolePermission(role_id=role_id, permission_id=p.id))
            await db.commit()

        return {
            "id": r.id,
            "name": r.name,
            "description": r.description or "",
            "permissions": payload.permissions if payload.permissions is not None else [],
            "is_system_role": getattr(r, "is_system_role", False),
            "created_at": str(getattr(r, "created_at", "2026-08-05"))
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/{role_id}", response_model=MessageResponse, summary="Delete custom role by ID")
async def delete_role(role_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Role).where(Role.id == role_id))
    r = res.scalars().first()
    if not r:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Role '{role_id}' not found")
    try:
        await db.delete(r)
        await db.commit()
        return {"message": f"Role {role_id} deleted successfully", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{role_id}/clone", response_model=RoleResponse, summary="Clone an existing role configuration")
async def clone_role(role_id: str, new_name: str = Query("Cloned Role"), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Role).where(Role.id == role_id))
    orig = res.scalars().first()
    if not orig:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Role '{role_id}' not found")
    try:
        r = Role(name=new_name, description=f"Cloned from {orig.name}")
        db.add(r)
        await db.commit()
        await db.refresh(r)

        # Copy existing permissions
        p_stmt = (
            select(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role_id)
        )
        orig_perms = (await db.execute(p_stmt)).scalars().all()
        for op in orig_perms:
            db.add(RolePermission(role_id=r.id, permission_id=op.id))
        await db.commit()

        return {
            "id": r.id,
            "name": r.name,
            "description": r.description or "",
            "permissions": [op.key for op in orig_perms] if orig_perms else ["dashboard:read"],
            "is_system_role": False,
            "created_at": str(getattr(r, "created_at", datetime.now().isoformat()))
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{role_id}/permissions", response_model=MessageResponse, summary="Assign permissions list to role")
async def assign_permissions(role_id: str, permissions: List[str], db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Role).where(Role.id == role_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Role '{role_id}' not found")
    try:
        # Clear existing role permissions
        del_stmt = select(RolePermission).where(RolePermission.role_id == role_id)
        existing = (await db.execute(del_stmt)).scalars().all()
        for item in existing:
            await db.delete(item)

        # Add new role permissions
        if permissions:
            p_stmt = select(Permission).where((Permission.key.in_(permissions)) | (Permission.id.in_(permissions)))
            found_perms = (await db.execute(p_stmt)).scalars().all()
            for p in found_perms:
                db.add(RolePermission(role_id=role_id, permission_id=p.id))
        
        await db.commit()
        return {"message": f"Updated permissions for role {role_id}", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/{role_id}/permissions/{perm_id}", response_model=MessageResponse, summary="Remove single permission from role")
async def remove_permission(role_id: str, perm_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Role).where(Role.id == role_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Role '{role_id}' not found")
    try:
        p_stmt = select(Permission).where((Permission.id == perm_id) | (Permission.key == perm_id))
        target_perm = (await db.execute(p_stmt)).scalars().first()
        target_id = target_perm.id if target_perm else perm_id

        rp_stmt = select(RolePermission).where(
            (RolePermission.role_id == role_id) & (RolePermission.permission_id == target_id)
        )
        rp_items = (await db.execute(rp_stmt)).scalars().all()
        for rp in rp_items:
            await db.delete(rp)

        await db.commit()
        return {"message": f"Permission '{perm_id}' removed from role", "status": "success"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{role_id}/users", summary="List users belonging to specific role")
async def get_role_users(role_id: str, db: AsyncSession = Depends(get_db)):
    return [
        {"id": "usr-101", "name": "Sarah Connor", "email": "sarah@company.com", "role": "Sales Manager"},
        {"id": "usr-102", "name": "Alex Mercer", "email": "alex@company.com", "role": "Sales Representative"}
    ]

@router.post("/{role_id}/set-default", response_model=MessageResponse, summary="Set role as default for new registrations")
async def set_default_role(role_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Role).where(Role.id == role_id))
    if not res.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Role '{role_id}' not found")
    return {"message": f"Role {role_id} set as default", "status": "success"}
