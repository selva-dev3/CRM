import json
from typing import Any, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Permission,
    Role,
    RolePermission,
    SystemSetting,
    User,
    UserRole,
)


class RoleRepository:
    """Query layer for the Role/Permission domain — no business logic."""

    # --- SystemSetting helpers ---
    async def get_setting(self, db: AsyncSession, key: str) -> Optional[SystemSetting]:
        res = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
        return res.scalars().first()

    async def upsert_setting(self, db: AsyncSession, key: str, value: str, description: str) -> None:
        setting = await self.get_setting(db, key)
        if setting:
            setting.value = value
        else:
            db.add(SystemSetting(key=key, value=value, description=description))

    # --- Role ---
    async def list_roles(
        self,
        db: AsyncSession,
        search: Optional[str] = None,
        org_id: Optional[str] = None,
    ) -> Sequence[Role]:
        """List roles, optionally filtered by search term and restricted to the
        current organization plus global/system roles (``organization_id IS NULL``)."""
        stmt = select(Role)
        cleaned = search.strip() if search and isinstance(search, str) and search.strip() else None
        if cleaned:
            pattern = f"%{cleaned}%"
            stmt = stmt.where(Role.name.ilike(pattern) | Role.description.ilike(pattern))
        if org_id:
            stmt = stmt.where(
                (Role.organization_id == org_id) | (Role.organization_id.is_(None))
            )
        res = await db.execute(stmt.limit(50))
        return res.scalars().all()

    async def get_role(self, db: AsyncSession, role_id: str) -> Optional[Role]:
        res = await db.execute(select(Role).where(Role.id == role_id))
        return res.scalars().first()

    async def get_role_by_id_or_name(self, db: AsyncSession, value: str) -> Optional[Role]:
        res = await db.execute(select(Role).where((Role.id == value) | (Role.name == value)))
        return res.scalars().first()

    async def get_system_roles(self, db: AsyncSession) -> Sequence[Role]:
        res = await db.execute(select(Role).where(Role.is_system_role == True))  # noqa: E712
        return res.scalars().all()

    async def get_first_role(self, db: AsyncSession) -> Optional[Role]:
        res = await db.execute(select(Role).limit(1))
        return res.scalars().first()

    async def create_role(self, db: AsyncSession, *, name: str, description: str) -> Role:
        role = Role(name=name, description=description)
        db.add(role)
        return role

    async def delete_role(self, db: AsyncSession, role: Role) -> None:
        await db.delete(role)

    # --- Permission ---
    async def get_permission_keys(self, db: AsyncSession) -> list[str]:
        p_res = await db.execute(select(Permission.key).where(Permission.key != "all"))
        return sorted({k for k in p_res.scalars().all() if k and k != "all"})

    async def get_permissions_by_keys_or_ids(self, db: AsyncSession, values: list[str]) -> Sequence[Permission]:
        p_stmt = select(Permission).where((Permission.key.in_(values)) | (Permission.id.in_(values)))
        res = await db.execute(p_stmt)
        return res.scalars().all()

    async def get_permission_matrix(self, db: AsyncSession) -> Sequence[Permission]:
        from sqlalchemy import func as sa_func

        res = await db.execute(
            select(Permission)
            .where(
                Permission.key != "all",
                sa_func.lower(Permission.category) != "all",
                Permission.name != "All Permission",
                Permission.id != "all",
            )
            .order_by(Permission.category, Permission.name)
            .limit(2000)
        )
        return res.scalars().all()

    async def create_permission(self, db: AsyncSession, *, data: dict) -> Permission:
        permission = Permission(**data)
        db.add(permission)
        return permission

    async def seed_permissions(self, db: AsyncSession, items: list[dict]) -> None:
        from sqlalchemy import func
        from sqlalchemy.exc import IntegrityError

        p_res = await db.execute(select(Permission.key))
        existing_keys = {str(k).strip() for k in p_res.scalars().all() if k}
        new_count = 0
        for item in items:
            key_str = item.get("key")
            if key_str and key_str != "all" and key_str not in existing_keys:
                db.add(
                    Permission(
                        key=key_str,
                        name=item.get("name", key_str),
                        category=item.get("category", "General"),
                        description=item.get("description", ""),
                    )
                )
                existing_keys.add(key_str)
                new_count += 1
        if new_count > 0:
            try:
                await db.flush()
            except IntegrityError:
                await db.rollback()
                p_res = await db.execute(select(Permission.key))
                existing_keys = {str(k).strip() for k in p_res.scalars().all() if k}
                new_count = 0

        # Ensure ONLY the global system Admin role has standard permissions attached
        admin_role_res = await db.execute(
            select(Role)
            .where(
                func.lower(Role.name) == "admin",
                Role.is_system_role.is_(True),
                Role.organization_id.is_(None),
            )
            .order_by(Role.created_at.asc())
            .limit(1)
        )
        admin_role = admin_role_res.scalars().first()
        if admin_role:
            standard_keys = [
                item["key"]
                for item in items
                if item.get("key")
                and item["key"] != "all"
                and item["key"] != "super_admin:manage"
            ]
            all_perms_res = await db.execute(
                select(Permission).where(Permission.key.in_(standard_keys))
            )
            all_perms = all_perms_res.scalars().all()
            existing_rp_res = await db.execute(
                select(RolePermission.permission_id).where(
                    RolePermission.role_id == admin_role.id
                )
            )
            existing_pids = set(existing_rp_res.scalars().all())
            for p in all_perms:
                if p.id not in existing_pids:
                    db.add(RolePermission(role_id=admin_role.id, permission_id=p.id))
                    existing_pids.add(p.id)
                    new_count += 1

        if new_count > 0:
            try:
                await db.commit()
            except IntegrityError:
                await db.rollback()

    # --- RolePermission mapping ---
    async def get_role_permissions(self, db: AsyncSession, role_id: str) -> Sequence[Permission]:
        stmt = (
            select(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role_id)
        )
        res = await db.execute(stmt)
        return res.scalars().all()

    async def get_role_permission_ids(self, db: AsyncSession, role_id: str) -> Sequence[RolePermission]:
        res = await db.execute(select(RolePermission).where(RolePermission.role_id == role_id))
        return res.scalars().all()

    async def add_role_permission(self, db: AsyncSession, role_id: str, permission_id: str) -> None:
        db.add(RolePermission(role_id=role_id, permission_id=permission_id))

    async def delete_role_permission(self, db: AsyncSession, rp: RolePermission) -> None:
        await db.delete(rp)

    async def remove_permission_from_role(self, db: AsyncSession, role_id: str, permission_id: str) -> None:
        rp_stmt = select(RolePermission).where(
            (RolePermission.role_id == role_id) & (RolePermission.permission_id == permission_id)
        )
        rp_items = (await db.execute(rp_stmt)).scalars().all()
        for rp in rp_items:
            await db.delete(rp)

    # --- User / UserRole ---
    async def get_user_by_id_or_email(self, db: AsyncSession, value: str) -> Optional[User]:
        res = await db.execute(select(User).where((User.id == value) | (User.email == value)))
        return res.scalars().first()

    async def get_user_role_mapping(self, db: AsyncSession, user_id: str) -> Optional[UserRole]:
        res = await db.execute(select(UserRole).where(UserRole.user_id == user_id))
        return res.scalars().first()

    async def get_users_by_role(self, db: AsyncSession, value: str) -> Sequence[User]:
        res = await db.execute(select(User).where((User.role == value)))
        return res.scalars().all()

    async def get_users_by_user_role_id(self, db: AsyncSession, role_id: str) -> Sequence[User]:
        res = await db.execute(
            select(User).join(UserRole, UserRole.user_id == User.id).where(UserRole.role_id == role_id)
        )
        return res.scalars().all()

    async def get_permission_by_id_or_key(self, db: AsyncSession, value: str) -> Optional[Permission]:
        res = await db.execute(select(Permission).where((Permission.id == value) | (Permission.key == value)))
        return res.scalars().first()

    async def get_permission_by_key(self, db: AsyncSession, key: str) -> Optional[Permission]:
        res = await db.execute(select(Permission).where(Permission.key == key))
        return res.scalars().first()