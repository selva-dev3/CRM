import json
from collections.abc import Sequence

from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException
from app.core.logging import get_logger
from app.core.rbac_matrix import (
    ADMIN_PERMISSIONS,
    APPROVED_PERMISSION_KEYS,
    SYSTEM_ROLE_NAMES,
    SYSTEM_ROLE_PERMISSIONS,
)
from app.models import (
    OrganizationInvitation,
    Permission,
    Role,
    RolePermission,
    SystemSetting,
    User,
    UserInvitation,
    UserRole,
)

logger = get_logger(__name__)


class RoleRepository:
    """Query layer for the Role/Permission domain — no business logic."""

    # --- SystemSetting helpers ---
    async def get_setting(self, db: AsyncSession, key: str) -> SystemSetting | None:
        res = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
        return res.scalars().first()

    async def upsert_setting(
        self, db: AsyncSession, key: str, value: str, description: str
    ) -> None:
        setting = await self.get_setting(db, key)
        if setting:
            setting.value = value
        else:
            db.add(SystemSetting(key=key, value=value, description=description))

    async def lock_default_roles(self, db: AsyncSession, organization_id: str) -> None:
        await db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
            {"lock_key": f"rbac-default-roles:{organization_id}"},
        )

    # --- Role ---
    async def list_roles(
        self,
        db: AsyncSession,
        search: str | None = None,
        org_id: str | None = None,
    ) -> Sequence[Role]:
        """List roles restricted to one organization when a scope is supplied."""
        stmt = select(Role)
        cleaned = search.strip() if search and isinstance(search, str) and search.strip() else None
        if cleaned:
            pattern = f"%{cleaned}%"
            stmt = stmt.where(Role.name.ilike(pattern) | Role.description.ilike(pattern))
        if org_id:
            stmt = stmt.where(Role.organization_id == org_id)
        res = await db.execute(stmt.limit(50))
        return res.scalars().all()

    async def get_role(self, db: AsyncSession, role_id: str) -> Role | None:
        res = await db.execute(select(Role).where(Role.id == role_id))
        return res.scalars().first()

    async def get_role_for_update(
        self, db: AsyncSession, role_id: str, organization_id: str
    ) -> Role | None:
        """Lock a tenant role so assignment/default/delete operations serialize."""
        return await db.scalar(
            select(Role)
            .where(Role.id == role_id, Role.organization_id == organization_id)
            .with_for_update()
        )

    async def get_role_by_id_or_name(
        self, db: AsyncSession, value: str, *, organization_id: str | None = None
    ) -> Role | None:
        normalized = value.strip()
        identity_filter = (Role.id == normalized) | (
            func.lower(func.btrim(Role.name)) == normalized.lower()
        )
        if not organization_id:
            return await db.scalar(select(Role).where(identity_filter).limit(1))

        return await db.scalar(
            select(Role).where(Role.organization_id == organization_id, identity_filter).limit(1)
        )

    async def get_global_role_by_names(self, db: AsyncSession, names: Sequence[str]) -> Role | None:
        normalized_names = [name.strip().lower() for name in names if name.strip()]
        if not normalized_names:
            return None
        res = await db.execute(
            select(Role)
            .where(
                Role.organization_id.is_(None),
                func.lower(Role.name).in_(normalized_names),
            )
            .order_by(Role.created_at.asc())
            .limit(1)
        )
        return res.scalars().first()

    async def get_system_roles(self, db: AsyncSession, organization_id: str) -> Sequence[Role]:
        res = await db.execute(
            select(Role).where(
                Role.is_system_role.is_(True),
                Role.organization_id == organization_id,
            )
        )
        return res.scalars().all()

    async def get_first_role(self, db: AsyncSession) -> Role | None:
        res = await db.execute(select(Role).limit(1))
        return res.scalars().first()

    async def create_role(
        self,
        db: AsyncSession,
        *,
        name: str,
        description: str,
        organization_id: str | None = None,
        is_system_role: bool = False,
    ) -> Role:
        self.validate_custom_role_name(name, is_system_role=is_system_role)
        role = Role(
            name=name.strip(),
            description=description,
            organization_id=organization_id,
            is_system_role=is_system_role,
        )
        db.add(role)
        return role

    @staticmethod
    def validate_custom_role_name(name: str, *, is_system_role: bool = False) -> None:
        normalized = name.strip().lower().replace("_", " ")
        if not is_system_role and normalized in {n.lower() for n in SYSTEM_ROLE_NAMES}:
            raise APIException(status_code=409, message="This name is reserved for a system role")

    async def create_user_role_mapping(
        self, db: AsyncSession, *, user_id: str, role_id: str
    ) -> UserRole:
        mapping = UserRole(user_id=user_id, role_id=role_id)
        db.add(mapping)
        return mapping

    async def delete_role(self, db: AsyncSession, role: Role) -> None:
        await db.delete(role)

    # --- Permission ---
    async def get_permission_keys(self, db: AsyncSession) -> list[str]:
        p_res = await db.execute(
            select(Permission.key).where(Permission.key.in_(APPROVED_PERMISSION_KEYS))
        )
        return sorted(set(p_res.scalars().all()))

    async def get_permissions_by_keys_or_ids(
        self, db: AsyncSession, values: list[str]
    ) -> Sequence[Permission]:
        p_stmt = select(Permission).where(
            (Permission.key.in_(values)) | (Permission.id.in_(values))
        )
        res = await db.execute(p_stmt)
        return res.scalars().all()

    async def get_permission_matrix(self, db: AsyncSession) -> Sequence[Permission]:
        from sqlalchemy import func as sa_func

        res = await db.execute(
            select(Permission)
            .where(
                Permission.key.in_(ADMIN_PERMISSIONS),
                sa_func.lower(Permission.category) != "all",
                Permission.name != "All Permission",
                Permission.id != "all",
            )
            .order_by(Permission.category, Permission.name)
            .limit(2000)
        )
        return res.scalars().all()

    async def create_permission(self, db: AsyncSession, *, data: dict) -> Permission:
        permission = Permission(**(data | {"key": data["key"].strip().lower()}))
        db.add(permission)
        return permission

    async def seed_permissions(
        self, db: AsyncSession, items: list[dict], *, commit: bool = True
    ) -> None:
        from sqlalchemy.exc import IntegrityError, SQLAlchemyError

        p_res = await db.execute(select(Permission.key))
        existing_keys = {str(k).strip() for k in p_res.scalars().all() if k}

        for item in items:
            key_str = item.get("key")
            if key_str in APPROVED_PERMISSION_KEYS and key_str not in existing_keys:
                try:
                    async with db.begin_nested():
                        db.add(
                            Permission(
                                key=key_str,
                                name=item.get("name", key_str),
                                category=item.get("category", "General"),
                                description=item.get("description", ""),
                            )
                        )
                        await db.flush()
                        existing_keys.add(key_str)
                except IntegrityError:
                    existing_keys.add(key_str)

        if commit:
            try:
                await db.commit()
            except IntegrityError as e:
                logger.warning(
                    "IntegrityError during seed_permissions commit, rolling back: %s",
                    e,
                    exc_info=True,
                )
                await db.rollback()
                raise
            except SQLAlchemyError as e:
                logger.exception("Database error occurred during seed_permissions commit: %s", e)
                await db.rollback()
                raise

    async def synchronize_system_roles(self, db: AsyncSession) -> None:
        """Serialize initialization and reconcile registered grants without touching custom roles.

        The sole global role is Super Admin. Existing organization-scoped system
        roles are reconciled in place; missing tenant roles remain the
        organization provisioner's responsibility. The caller owns the transaction.
        """
        await db.execute(text("SELECT pg_advisory_xact_lock(7242310907)"))
        roles = list(
            (await db.execute(select(Role).where(Role.is_system_role.is_(True)))).scalars()
        )
        permissions = {
            p.key: p.id
            for p in (await db.execute(select(Permission))).scalars()
            if p.key in APPROVED_PERMISSION_KEYS
        }

        def normalized(value: str) -> str:
            return value.strip().lower().replace("_", " ")

        scoped_super_admins = [
            role
            for role in roles
            if normalized(role.name) == "super admin" and role.organization_id is not None
        ]
        if scoped_super_admins:
            raise APIException(
                status_code=409, message="Scoped Super Admin requires an audited migration"
            )
        global_super_admins = [
            role
            for role in roles
            if normalized(role.name) == "super admin" and role.organization_id is None
        ]
        if not global_super_admins:
            collision = (
                await db.execute(
                    select(Role.id).where(
                        Role.organization_id.is_(None),
                        func.lower(func.replace(func.btrim(Role.name), "_", " ")) == "super admin",
                    )
                )
            ).scalar_one_or_none()
            if collision:
                raise APIException(
                    status_code=409, message="Super Admin role conflicts with a custom role"
                )
            global_super_admins = [
                await self.create_role(
                    db,
                    name="Super Admin",
                    description="Global platform Super Admin role",
                    is_system_role=True,
                )
            ]
            roles.extend(global_super_admins)
            await db.flush()

        canonical_names = {normalized(name): name for name in SYSTEM_ROLE_NAMES}
        for role in roles:
            canonical_name = canonical_names.get(normalized(role.name))
            if not canonical_name:
                continue
            if canonical_name == "Super Admin":
                keys = set(APPROVED_PERMISSION_KEYS)
            else:
                if role.organization_id is None:
                    raise APIException(
                        status_code=409,
                        message="Global tenant roles require the RBAC integrity migration",
                    )
                keys = set(SYSTEM_ROLE_PERMISSIONS[canonical_name])
            if not keys.issubset(permissions):
                raise APIException(
                    status_code=409, message="Approved permission catalog is incomplete"
                )
            desired = {permissions[key] for key in keys}
            await db.execute(
                delete(RolePermission).where(
                    RolePermission.role_id == role.id,
                    RolePermission.permission_id.not_in(desired),
                )
            )
            existing = set(
                (
                    await db.execute(
                        select(RolePermission.permission_id).where(
                            RolePermission.role_id == role.id
                        )
                    )
                ).scalars()
            )
            for permission_id in sorted(desired - existing):
                await self.add_role_permission(db, role.id, permission_id)
            await db.flush()

    # --- RolePermission mapping ---
    async def get_role_permissions(self, db: AsyncSession, role_id: str) -> Sequence[Permission]:
        stmt = (
            select(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role_id)
        )
        res = await db.execute(stmt)
        return res.scalars().all()

    async def get_permission_keys_by_role_ids(
        self, db: AsyncSession, role_ids: list[str]
    ) -> dict[str, list[str]]:
        if not role_ids:
            return {}
        rows = (
            await db.execute(
                select(RolePermission.role_id, Permission.key)
                .join(Permission, Permission.id == RolePermission.permission_id)
                .where(
                    RolePermission.role_id.in_(role_ids),
                    Permission.key.in_(APPROVED_PERMISSION_KEYS),
                )
            )
        ).all()
        result: dict[str, list[str]] = {role_id: [] for role_id in role_ids}
        for role_id, key in rows:
            result[role_id].append(key)
        return result

    async def get_role_permission_ids(
        self, db: AsyncSession, role_id: str
    ) -> Sequence[RolePermission]:
        res = await db.execute(select(RolePermission).where(RolePermission.role_id == role_id))
        return res.scalars().all()

    async def add_role_permission(self, db: AsyncSession, role_id: str, permission_id: str) -> None:
        db.add(RolePermission(role_id=role_id, permission_id=permission_id))

    async def delete_role_permission(self, db: AsyncSession, rp: RolePermission) -> None:
        await db.delete(rp)

    async def remove_permission_from_role(
        self, db: AsyncSession, role_id: str, permission_id: str
    ) -> bool:
        rp_stmt = select(RolePermission).where(
            (RolePermission.role_id == role_id) & (RolePermission.permission_id == permission_id)
        )
        rp_items = (await db.execute(rp_stmt)).scalars().all()
        for rp in rp_items:
            await db.delete(rp)
        return bool(rp_items)

    # --- User / UserRole ---
    async def get_user_by_id_or_email(self, db: AsyncSession, value: str) -> User | None:
        res = await db.execute(select(User).where((User.id == value) | (User.email == value)))
        return res.scalars().first()

    async def get_user_role_mapping(self, db: AsyncSession, user_id: str) -> UserRole | None:
        res = await db.execute(select(UserRole).where(UserRole.user_id == user_id))
        return res.scalars().first()

    async def replace_user_role(self, db: AsyncSession, user_id: str, role_id: str) -> UserRole:
        await db.execute(delete(UserRole).where(UserRole.user_id == user_id))
        mapping = UserRole(user_id=user_id, role_id=role_id)
        db.add(mapping)
        return mapping

    async def get_users_by_role(
        self, db: AsyncSession, value: str, role_name: str | None = None
    ) -> Sequence[User]:
        values = [value]
        if role_name:
            values.append(role_name)
        res = await db.execute(select(User).where(User.role.in_(values)))
        return res.scalars().all()

    async def get_users_by_user_role_id(self, db: AsyncSession, role_id: str) -> Sequence[User]:
        res = await db.execute(
            select(User)
            .join(UserRole, UserRole.user_id == User.id)
            .where(UserRole.role_id == role_id)
        )
        return res.scalars().all()

    async def get_effective_users_by_role(
        self,
        db: AsyncSession,
        *,
        role_id: str,
        role_name: str,
        organization_id: str,
    ) -> Sequence[User]:
        """List users whose authoritative mapping, or unmapped legacy value, matches."""
        result = await db.execute(
            select(User)
            .outerjoin(UserRole, UserRole.user_id == User.id)
            .where(
                User.organization_id == organization_id,
                or_(
                    UserRole.role_id == role_id,
                    (
                        UserRole.id.is_(None)
                        & or_(
                            User.role == role_id,
                            func.lower(func.btrim(User.role)) == role_name.strip().lower(),
                        )
                    ),
                ),
            )
        )
        return result.scalars().all()

    async def get_role_reference_kinds(self, db: AsyncSession, role: Role) -> list[str]:
        """Return durable references that make a custom role unsafe to delete."""
        references: list[str] = []
        if await db.scalar(
            select(User.id).where(
                User.organization_id == role.organization_id,
                or_(
                    func.btrim(User.role) == role.id,
                    func.lower(func.btrim(User.role)) == role.name.strip().lower(),
                ),
            ).limit(1)
        ):
            references.append("users")
        if await db.scalar(
            select(UserRole.id).where(UserRole.role_id == role.id).limit(1)
        ):
            references.append("user role mappings")
        if await db.scalar(
            select(UserInvitation.id).where(
                UserInvitation.organization_id == role.organization_id,
                func.lower(UserInvitation.status) == "pending",
                or_(
                    func.btrim(UserInvitation.role) == role.id,
                    func.lower(func.btrim(UserInvitation.role)) == role.name.strip().lower(),
                ),
            ).limit(1)
        ):
            references.append("user invitations")
        if await db.scalar(
            select(OrganizationInvitation.id).where(
                OrganizationInvitation.organization_id == role.organization_id,
                func.lower(OrganizationInvitation.status) == "pending",
                or_(
                    func.btrim(OrganizationInvitation.role_id) == role.id,
                    func.lower(func.btrim(OrganizationInvitation.role_id))
                    == role.name.strip().lower(),
                ),
            ).limit(1)
        ):
            references.append("organization invitations")
        setting_keys = (
            f"default_registration_role:{role.organization_id}",
            f"default_registration_roles:{role.organization_id}",
        )
        settings = list(
            (
                await db.execute(select(SystemSetting).where(SystemSetting.key.in_(setting_keys)))
            ).scalars()
        )
        role_references = {role.id, role.name.strip().lower()}
        for setting in settings:
            value = (setting.value or "").strip()
            values: list[str]
            if setting.key.startswith("default_registration_roles:"):
                try:
                    parsed = json.loads(value)
                except (TypeError, json.JSONDecodeError):
                    parsed = value
                values = parsed if isinstance(parsed, list) else [str(parsed)]
            else:
                values = [value]
            normalized = {str(item).strip().lower() for item in values}
            if role_references & normalized:
                references.append("default role settings")
                break
        return references

    async def get_permission_by_id_or_key(self, db: AsyncSession, value: str) -> Permission | None:
        res = await db.execute(
            select(Permission).where((Permission.id == value) | (Permission.key == value))
        )
        return res.scalars().first()

    async def get_permission_by_key(self, db: AsyncSession, key: str) -> Permission | None:
        res = await db.execute(select(Permission).where(Permission.key == key))
        return res.scalars().first()
