import asyncio
import json

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIException, NotFoundError
from app.core.logging import get_logger
from app.core.permissions import (
    effective_organization_id,
    ensure_can_assign_role,
    ensure_tenant_managed_user,
    is_super_admin_role,
    is_super_admin_user,
)
from app.core.security import generate_random_code, get_password_hash
from app.models import AuditLog, Role, User, UserRole
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository
from app.schemas.crm_schemas import (
    UserCreate,
    UserInviteRequest,
    UserProfileUpdate,
    UserUpdate,
)
from app.services.email_service import send_user_invite_email
from app.services.organization_storage_service import lock_organization_storage
from app.services.s3_service import s3_service

logger = get_logger(__name__)
ADMIN_ROLE_NAMES = {"admin", "organization admin"}


def user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "organization_id": user.organization_id or "",
        "is_active": user.is_active,
        "created_at": str(user.created_at),
    }


class UserService:
    """Business logic for the User/Invitation domain."""

    def __init__(self, repository: UserRepository | None = None) -> None:
        self.repository = repository or UserRepository()
        self.role_repository = RoleRepository()
        self.organization_repository = OrganizationRepository()

    async def _commit(self, db: AsyncSession, error_message: str) -> None:
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message=error_message
            ) from e

    async def require_user(self, db: AsyncSession, user_id: str) -> User:
        user = await self.repository.get_by_id(db, user_id)
        if not user:
            raise NotFoundError(message=f"User '{user_id}' not found")
        return user

    async def _resolve_current_org(self, db: AsyncSession, current_user: User) -> str:
        """Single source of truth for the current organization: derived exclusively
        from the authenticated user — never from a client-supplied organization_id."""
        org_id = effective_organization_id(current_user)
        if not org_id:
            raise APIException(
                status_code=status.HTTP_403_FORBIDDEN,
                message="Authenticated user has no current organization",
            )
        org = await self.organization_repository.get_by_id(db, org_id)
        if not org:
            raise APIException(
                status_code=status.HTTP_404_NOT_FOUND,
                message="Current organization not found",
            )
        organization_status = (getattr(org, "status", None) or "").strip().lower()
        if organization_status != "active":
            logger.warning(
                "Organization %s rejected for user operation because status is %r",
                org_id,
                getattr(org, "status", None),
            )
            raise APIException(
                status_code=status.HTTP_403_FORBIDDEN,
                message="Organization is inactive.",
            )
        if not getattr(org, "is_active", True):
            logger.warning(
                "Organization %s rejected for user operation because it is disabled",
                org_id,
            )
            raise APIException(
                status_code=status.HTTP_403_FORBIDDEN,
                message="Organization is disabled.",
            )
        return org_id

    async def _resolve_assignable_role(
        self, db: AsyncSession, org_id: str, role_value: str, *, current_user: User
    ) -> Role:
        """Resolve a role that may be assigned within the current organization.

        Enforced server-side regardless of any frontend filtering:
        1. Role must exist.
        2. Role must belong to the current organization.
        3. The global Super Admin role cannot be assigned through tenant APIs.
        Assignment is independent of role mutability: ``is_system_role`` protects
        built-in roles from editing/deletion, but does not make them unassignable.
        """
        role = await self.role_repository.get_role_by_id_or_name(db, role_value, organization_id=org_id)
        if not role:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=f"Invalid role: '{role_value}'",
            )
        if role.organization_id != org_id:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=f"Role '{role.name}' does not belong to the current organization",
            )
        if is_super_admin_role(role):
            ensure_can_assign_role(
                actor_is_super_admin=await is_super_admin_user(db, current_user),
                target_is_super_admin=True,
            )
        locked_role = await self.role_repository.get_role_for_update(db, role.id, org_id)
        if not locked_role:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=f"Invalid role: '{role_value}'",
            )
        return locked_role

    @staticmethod
    def _get_display_role(user: User, role_map: dict) -> str:
        role_val = user.role
        if user.is_platform_admin:
            return "Super Admin"
        if not role_val:
            return "User"
        if role_val in role_map:
            return role_map[role_val]
        if len(role_val) > 20 and "-" in role_val:
            return "Assigned Role"
        return role_val

    @staticmethod
    def _audit_role_assignment(
        db: AsyncSession,
        *,
        current_user: User,
        target_user: User,
        before_role_id: str | None,
        after_role: Role,
    ) -> None:
        db.add(
            AuditLog(
                organization_id=target_user.organization_id,
                user_id=current_user.id,
                action="ROLE_ASSIGNED_TO_USER",
                details=json.dumps(
                    {
                        "target_type": "user",
                        "target_id": target_user.id,
                        "before": {"role_id": before_role_id},
                        "after": {"role_id": after_role.id, "role_name": after_role.name},
                    },
                    sort_keys=True,
                ),
            )
        )

    async def list_users(
        self, db: AsyncSession, *, page: int, limit: int, search: str | None, current_user: User
    ) -> list[dict]:
        org_id = await self._resolve_current_org(db, current_user)
        users = await self.repository.list(
            db, page=page, limit=limit, search=search, organization_id=org_id
        )
        role_names = await self.repository.effective_role_names_for_users(db, users, org_id)
        return [
            {
                "id": u.id,
                "name": u.name,
                "email": u.email,
                "role": role_names.get(u.id) or "User",
                "organization_id": u.organization_id,
                "is_active": u.is_active,
                "created_at": str(u.created_at),
            }
            for u in users
        ]

    async def count_users(self, db: AsyncSession, *, search: str | None, current_user: User) -> int:
        org_id = await self._resolve_current_org(db, current_user)
        return await self.repository.count(db, search=search, organization_id=org_id)

    async def create_user(
        self, db: AsyncSession, payload: UserCreate, *, current_user: User
    ) -> dict:
        try:
            return await self._create_user(db, payload, current_user=current_user)
        except Exception:
            await db.rollback()
            raise

    async def _create_user(
        self, db: AsyncSession, payload: UserCreate, *, current_user: User
    ) -> dict:
        # The organization is derived exclusively from the authenticated user —
        # never from a client-supplied organization_id.
        org_id = await self._resolve_current_org(db, current_user)

        from app.repositories.organization_lifecycle_repository import (
            OrganizationLifecycleRepository,
        )

        lifecycle = OrganizationLifecycleRepository()
        email = payload.email.strip().lower()
        await lifecycle.lock_invitation_email(db, email)
        organization = await lifecycle.lock_invitation_organization(db, org_id)
        if not organization or not organization.is_active or organization.status.strip().lower() != "active":
            raise APIException(status_code=403, message="Organization is unavailable")
        if await lifecycle.email_in_use(db, email):
            raise APIException(status_code=409, message="This email already belongs to an account")
        member_count = await lifecycle.tenant_member_count(db, org_id)
        if member_count >= organization.max_users:
            raise APIException(status_code=409, code="ORGANIZATION_MEMBER_LIMIT", message="The organization has reached its member limit")
        subscription = await lifecycle.subscription_for_membership(db, org_id)
        if subscription is None:
            raise APIException(status_code=409, message="The organization subscription requires administrator reconciliation")

        role = await self._resolve_assignable_role(
            db, org_id, payload.role, current_user=current_user
        )
        user = await self.repository.create(
            db,
            data={
                "name": payload.name,
                "email": email,
                "hashed_password": get_password_hash(payload.password),
                "role": role.id,
                "organization_id": org_id,
            },
        )
        await db.flush()
        db.add(UserRole(user_id=user.id, role_id=role.id))
        subscription.current_users = member_count + 1
        self._audit_role_assignment(
            db,
            current_user=current_user,
            target_user=user,
            before_role_id=None,
            after_role=role,
        )
        await self._commit(db, "User creation failed")
        return user_to_dict(user)

    async def get_my_profile(self, db: AsyncSession, current_user: User) -> dict:
        user = await self.require_user(db, current_user.id)
        return user_to_dict(user)

    async def update_my_profile(
        self, db: AsyncSession, payload: UserProfileUpdate, current_user: User
    ) -> dict:
        user = await self.require_user(db, current_user.id)
        if payload.name:
            user.name = payload.name
        await self._commit(db, "Failed to update profile")
        return user_to_dict(user)

    async def upload_avatar(
        self,
        db: AsyncSession,
        *,
        file,
        filename: str,
        content_type: str | None,
        current_user: User,
    ) -> dict:
        user = await self.require_user(db, current_user.id)
        if user._organization_id:
            await lock_organization_storage(db, user._organization_id)
        try:
            object_name = f"avatars/{user.id}_{filename}"
            s3_key = await asyncio.to_thread(
                s3_service.upload_file, file, object_name=object_name, content_type=content_type
            )
            avatar_url = await asyncio.to_thread(s3_service.generate_presigned_url, s3_key)
            profile = await self.repository.get_or_create_profile(db, user.id)
            profile.avatar_url = avatar_url
            await db.commit()
            return {"message": "Avatar uploaded to MinIO S3 successfully", "status": "success"}
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=f"S3 Avatar upload failed: {str(e)}",
            ) from e

    async def invite_users(
        self, db: AsyncSession, payload: UserInviteRequest, *, current_user: User
    ) -> dict:
        # The organization is derived exclusively from the authenticated user —
        # the Invite Team Member form no longer accepts an organization field.
        org_id = await self._resolve_current_org(db, current_user)

        from app.repositories.organization_lifecycle_repository import (
            OrganizationLifecycleRepository,
        )

        lifecycle = OrganizationLifecycleRepository()
        targets = {
            item.email.strip().lower(): item.name or item.email.split("@")[0]
            for item in payload.users or []
        }
        if not targets:
            targets = {
                email.strip().lower(): payload.name or email.split("@")[0]
                for email in payload.emails or []
            }
        deliveries = []
        invitation_responses = []
        try:
            for email in sorted(targets):
                await lifecycle.lock_invitation_email(db, email)
            organization = await lifecycle.lock_invitation_organization(db, org_id)
            if not organization or not organization.is_active or organization.status.strip().lower() != "active":
                raise APIException(status_code=403, message="Organization is unavailable")
            member_count = await lifecycle.tenant_member_count(db, org_id)
            if member_count + len(targets) > organization.max_users:
                raise APIException(status_code=409, code="ORGANIZATION_MEMBER_LIMIT", message="The organization has reached its member limit")
            role = await self._resolve_assignable_role(
                db, org_id, payload.role, current_user=current_user
            )
            for email, name in targets.items():
                if await lifecycle.email_in_use(db, email):
                    raise APIException(status_code=409, message="This email already belongs to an account")
                if await lifecycle.pending_invitation_exists(db, email) or await lifecycle.pending_legacy_invitation_exists(db, email):
                    raise APIException(status_code=409, message="This email already has a pending invitation")
                token = generate_random_code(14)
                invitation = await self.repository.create_invitation(db, data={
                    "email": email, "token": token, "role": role.id,
                    "organization_id": org_id, "status": "pending",
                })
                await db.flush()
                db.add(AuditLog(
                    organization_id=org_id, user_id=current_user.id,
                    action="INVITATION_CREATED",
                    details=json.dumps({
                        "target_type": "invitation", "target_id": invitation.id,
                        "after": {"role_id": role.id},
                    }, sort_keys=True),
                ))
                deliveries.append((email, token))
                invitation_responses.append({
                    "name": name, "email": email, "role": role.id,
                    "role_name": role.name, "status": "pending",
                })
            await db.commit()
        except APIException:
            await db.rollback()
            raise
        except Exception as exc:
            await db.rollback()
            raise APIException(status_code=400, message="Unable to create invitations") from exc

        for email, token in deliveries:
            try:
                send_user_invite_email(
                    email_to=email, role=role.name,
                    invite_url=f"{settings.FRONTEND_URL}/accept-invite?token={token}",
                )
            except Exception as exc:
                logger.exception("Invitation delivery failed")
                raise APIException(status_code=503, message="Invitations were saved, but email delivery failed. Contact an administrator.") from exc
        return {
            "message": f"Invites sent to {len(invitation_responses)} users",
            "invitations": invitation_responses, "status": "success",
        }

    async def list_user_invitations(
        self, db: AsyncSession, *, token: str | None, status_filter: str | None, current_user: User
    ) -> list[dict]:
        org_id = await self._resolve_current_org(db, current_user)
        invitations = await self.repository.list_invitations(
            db, token=token, status_filter=status_filter, organization_id=org_id
        )
        role_map = await self.repository.role_name_map(
            db, {inv.role for inv in invitations if inv.role}
        )
        return [
            {
                "id": inv.id,
                "email": inv.email,
                "role": role_map.get(inv.role, inv.role),
                "status": inv.status,
                "organization_id": inv.organization_id,
                "created_at": str(inv.created_at) if inv.created_at else "",
            }
            for inv in invitations
        ]

    async def get_invitation_details(self, db: AsyncSession, token: str) -> dict:
        inv = await self.repository.get_invitation_by_token(db, token)
        if not inv:
            raise NotFoundError(message="Invitation not found or token invalid")
        accepted_any = await self.repository.get_invitation_by_email(
            db, inv.email, status="accepted"
        )
        if accepted_any:
            inv.status = "accepted"
        role_map = await self.repository.role_name_map(db, {inv.role} if inv.role else set())
        return {
            "id": inv.id,
            "email": inv.email,
            "role": role_map.get(inv.role, inv.role),
            "status": inv.status,
            "organization_id": inv.organization_id,
            "created_at": str(inv.created_at),
        }

    async def get_user(self, db: AsyncSession, user_id: str, *, current_user: User) -> dict:
        user = await self._require_same_org_user(db, user_id, current_user)
        role_names = await self.repository.effective_role_names_for_users(
            db, [user], effective_organization_id(current_user)
        )
        result = user_to_dict(user)
        result["role"] = role_names.get(user.id) or "User"
        return result

    async def update_user(
        self, db: AsyncSession, user_id: str, payload: UserUpdate, *, current_user: User
    ) -> dict:
        user = await self._require_same_org_user(db, user_id, current_user)
        ensure_tenant_managed_user(user)
        if not user.organization_id:
            raise NotFoundError(message="Organization user not found")
        if payload.name:
            user.name = payload.name
        if payload.role:
            role = await self._resolve_assignable_role(
                db, user.organization_id, payload.role, current_user=current_user
            )
            await self._ensure_not_last_admin(
                db, user, replacement_role_name=role.name
            )
            previous_mapping = await self.role_repository.get_user_role_mapping(db, user.id)
            previous_role = (
                previous_mapping.role_id
                if previous_mapping
                else (user.role or "").strip() or None
            )
            user.role = role.id
            await self.role_repository.replace_user_role(db, user.id, role.id)
            self._audit_role_assignment(
                db,
                current_user=current_user,
                target_user=user,
                before_role_id=previous_role,
                after_role=role,
            )
        await self._commit(db, "Failed to update user")
        return user_to_dict(user)

    async def delete_user(self, db: AsyncSession, user_id: str, *, current_user: User) -> dict:
        user = await self._require_same_org_user(db, user_id, current_user)
        ensure_tenant_managed_user(user)
        if user.id == current_user.id:
            raise APIException(
                status_code=status.HTTP_409_CONFLICT,
                code="SELF_DEACTIVATION_FORBIDDEN",
                message="You cannot deactivate your own account",
            )
        await self._ensure_not_last_admin(db, user)
        from app.repositories.auth_repository import AuthRepository

        await AuthRepository().revoke_all_user_sessions(db, user.id)
        user_name = user.name
        user_email = user.email
        user.is_active = False
        await self._commit(db, "Failed to deactivate user")
        return {
            "message": f"User '{user_name}' ({user_email}) deactivated successfully",
            "user_id": user_id,
            "name": user_name,
            "email": user_email,
            "status": "success",
        }

    async def activate_user(self, db: AsyncSession, user_id: str, *, current_user: User) -> dict:
        user = await self._require_same_org_user(db, user_id, current_user)
        user.is_active = True
        await self._commit(db, "Failed to activate user")
        return {
            "message": f"User '{user.name}' ({user.email}) activated successfully",
            "user_id": user.id,
            "name": user.name,
            "email": user.email,
            "is_active": user.is_active,
            "status": "success",
        }

    async def deactivate_user(self, db: AsyncSession, user_id: str, *, current_user: User) -> dict:
        user = await self._require_same_org_user(db, user_id, current_user)
        ensure_tenant_managed_user(user)
        if user.id == current_user.id:
            raise APIException(
                status_code=status.HTTP_409_CONFLICT,
                code="SELF_DEACTIVATION_FORBIDDEN",
                message="You cannot deactivate your own account",
            )
        await self._ensure_not_last_admin(db, user)
        from app.repositories.auth_repository import AuthRepository

        await AuthRepository().revoke_all_user_sessions(db, user.id)
        user.is_active = False
        await self._commit(db, "Failed to deactivate user")
        return {
            "message": f"User '{user.name}' ({user.email}) deactivated successfully",
            "user_id": user.id,
            "name": user.name,
            "email": user.email,
            "is_active": user.is_active,
            "status": "success",
        }

    async def get_user_activities(
        self, db: AsyncSession, user_id: str, *, current_user: User
    ) -> list:
        await self._require_same_org_user(db, user_id, current_user)
        raise APIException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            code="USER_ACTIVITY_UNAVAILABLE",
            message="User-level activity attribution is not available",
        )

    async def get_user_teams(self, db: AsyncSession, user_id: str, *, current_user: User) -> list:
        await self._require_same_org_user(db, user_id, current_user)
        raise APIException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            code="USER_TEAMS_UNAVAILABLE",
            message="Team membership management is not available",
        )

    async def assign_user_team(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        team_id: str,
        team_name: str | None,
        current_user: User,
    ) -> dict:
        await self._require_same_org_user(db, user_id, current_user)
        raise APIException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            code="USER_TEAMS_UNAVAILABLE",
            message="Team membership management is not available",
        )

    async def remove_user_team(
        self, db: AsyncSession, *, user_id: str, team_id: str, current_user: User
    ) -> dict:
        await self._require_same_org_user(db, user_id, current_user)
        raise APIException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            code="USER_TEAMS_UNAVAILABLE",
            message="Team membership management is not available",
        )

    async def bulk_delete_users(
        self, db: AsyncSession, ids: list[str], *, current_user: User
    ) -> dict:
        organization_id = effective_organization_id(current_user)
        if not organization_id:
            raise APIException(status_code=403, message="Select an organization first")
        # Tenant scope: only ids belonging to the caller's organization may be
        # deleted; foreign-org ids are ignored entirely (not an error, matching
        # idempotent bulk semantics).
        users = [
            item
            for item in await self.repository.list_by_ids(db, ids)
            if item.organization_id == organization_id
        ]
        candidates = [
            item
            for item in users
            if item.is_active
            and getattr(item, "is_platform_admin", False) is not True
            and item.id != current_user.id
        ]
        active_users = await self.repository.lock_active_by_org(
            db, organization_id
        )
        effective_roles = await self.repository.effective_role_names_for_users(
            db, active_users, organization_id
        )

        def is_admin(item: User) -> bool:
            role_name = effective_roles.get(item.id, "")
            return role_name.strip().lower() in ADMIN_ROLE_NAMES

        selected_ids = {item.id for item in candidates}
        remaining_admins = [
            item for item in active_users if is_admin(item) and item.id not in selected_ids
        ]
        if not remaining_admins:
            admin_to_keep = next((item for item in candidates if is_admin(item)), None)
            if admin_to_keep is not None:
                candidates.remove(admin_to_keep)

        deactivated_count = 0
        for item in candidates:
            item.is_active = False
            deactivated_count += 1
        if candidates:
            from app.repositories.auth_repository import AuthRepository

            auth_repository = AuthRepository()
            for item in candidates:
                await auth_repository.revoke_all_user_sessions(db, item.id)
        await self._commit(db, "Failed to bulk deactivate users")
        return {
            "affected_count": deactivated_count,
            "message": "Users deactivated successfully (protected users skipped)",
        }

    async def get_user_effective_permissions(
        self, db: AsyncSession, user_id: str, *, current_user: User
    ) -> dict:
        user = await self._require_same_org_user(db, user_id, current_user)
        from app.services.auth_service import auth_service

        permissions = await auth_service.get_user_permissions(db, user)
        return {"user_id": user_id, "permissions": permissions}

    async def admin_reset_user_password(
        self, db: AsyncSession, user_id: str, *, current_user: User
    ) -> dict:
        await self._require_same_org_user(db, user_id, current_user)
        raise APIException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            code="ADMIN_PASSWORD_RESET_UNAVAILABLE",
            message="Administrator password reset delivery is not configured",
        )

    async def _require_same_org_user(
        self, db: AsyncSession, user_id: str, current_user: User
    ) -> User:
        """Fetch a user and enforce that it belongs to the caller's organization.

        Returns 404 (not 403) for cross-org ids so callers cannot probe for
        the existence of users in other organizations.
        """
        user = await self.require_user(db, user_id)
        if not user.organization_id or effective_organization_id(current_user) != user.organization_id:
            raise NotFoundError(message=f"User '{user_id}' not found")
        return user

    async def get_user_quota(self, db: AsyncSession, user_id: str, *, current_user: User) -> dict:
        user = await self._require_same_org_user(db, user_id, current_user)
        quota = await self.repository.get_quota(db, user_id)
        target = float(quota.target_amount) if quota else None
        achieved = await self.repository.total_won_revenue(db, user_id)
        return {
            "user_id": user.id,
            "target_amount": target,
            "achieved_amount": round(achieved, 2),
        }

    async def set_user_quota(
        self, db: AsyncSession, *, user_id: str, target_amount: float, current_user: User
    ) -> dict:
        user = await self._require_same_org_user(db, user_id, current_user)
        if target_amount < 0:
            raise APIException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                message="Quota target must not be negative.",
            )
        if not user.organization_id:
            raise NotFoundError(message="Organization user not found")
        await self.repository.upsert_quota(
            db,
            user_id=user.id,
            organization_id=user.organization_id,
            target_amount=float(target_amount),
        )
        await self._commit(db, "Failed to assign quota")
        return {"message": f"Quota ${target_amount} assigned to {user_id}", "status": "success"}

    async def get_user_scorecard(
        self, db: AsyncSession, user_id: str, *, current_user: User
    ) -> dict:
        await self._require_same_org_user(db, user_id, current_user)
        raise APIException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            code="USER_SCORECARD_UNAVAILABLE",
            message="User scorecards are unavailable until all activities are attributed to users",
        )

    async def _ensure_not_last_admin(
        self,
        db: AsyncSession,
        user: User,
        *,
        replacement_role_name: str | None = None,
    ) -> None:
        if not user.organization_id:
            raise NotFoundError(message="Organization user not found")
        active_users = await self.repository.lock_active_by_org(db, user.organization_id)
        locked_user = next((item for item in active_users if item.id == user.id), None)
        if locked_user is None:
            return
        effective_roles = await self.repository.effective_role_names_for_users(
            db, active_users, user.organization_id
        )

        def is_admin(item: User) -> bool:
            role_name = effective_roles.get(item.id, "")
            return role_name.strip().lower() in ADMIN_ROLE_NAMES

        replacement_is_admin = (
            replacement_role_name is not None
            and replacement_role_name.strip().lower() in ADMIN_ROLE_NAMES
        )
        if (
            is_admin(locked_user)
            and not replacement_is_admin
            and sum(1 for item in active_users if is_admin(item)) <= 1
        ):
            raise APIException(
                status_code=status.HTTP_409_CONFLICT,
                code="LAST_ADMIN_DEACTIVATION_FORBIDDEN",
                message="The organization's last active administrator cannot be deactivated or demoted",
            )


user_service = UserService()
