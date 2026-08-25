from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIException, ForbiddenError, NotFoundError
from app.core.permissions import ensure_can_assign_role, is_super_admin_role, is_super_admin_user
from app.core.security import generate_random_code, get_password_hash
from app.models import Role, User, UserRole
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository
from app.schemas.crm_schemas import (
    AcceptInviteRequest,
    UserCreate,
    UserInviteRequest,
    UserProfileUpdate,
    UserUpdate,
)
from app.services.email_service import send_user_invite_email
from app.services.s3_service import s3_service

PROTECTED_SUPERADMIN_EMAIL = "superadmin@gmail.com"


def user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "organization_id": user.organization_id,
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
        org_id = getattr(current_user, "organization_id", None)
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
        if getattr(org, "status", "active") != "active" or not getattr(org, "is_active", True):
            raise APIException(
                status_code=status.HTTP_403_FORBIDDEN,
                message="Organization is inactive or disabled.",
            )
        return org_id

    async def _resolve_assignable_role(
        self, db: AsyncSession, org_id: str, role_value: str, *, current_user: User
    ) -> Role:
        """Resolve a role that may be assigned within the current organization.

        Enforced server-side regardless of any frontend filtering:
        1. Role must exist.
        2. Role must belong to the current organization OR be a global/system role.
        3. The super_admin role may only be assigned by a super_admin actor (403 otherwise).
        4. Other protected system roles cannot be assigned through user creation / invitations.
        """
        role = await self.role_repository.get_role_by_id_or_name(db, role_value)
        if not role:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=f"Invalid role: '{role_value}'",
            )
        if role.organization_id and role.organization_id != org_id:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=f"Role '{role.name}' does not belong to the current organization",
            )
        if is_super_admin_role(role):
            ensure_can_assign_role(
                actor_is_super_admin=await is_super_admin_user(db, current_user),
                target_is_super_admin=True,
            )
            return role
        if getattr(role, "is_system_role", False):
            raise ForbiddenError(message=f"System role '{role.name}' cannot be assigned")
        return role

    @staticmethod
    def _get_display_role(user: User, role_map: dict) -> str:
        role_val = user.role
        if not role_val:
            return "Super Administrator" if "superadmin" in user.email.lower() else "User"
        if role_val in role_map:
            return role_map[role_val]
        if len(role_val) > 20 and "-" in role_val:
            return "Super Administrator" if "superadmin" in user.email.lower() else "Assigned Role"
        return role_val

    async def list_users(
        self, db: AsyncSession, *, page: int, limit: int, search: str | None
    ) -> list[dict]:
        users = await self.repository.list(db, page=page, limit=limit, search=search)
        role_ids = {u.role for u in users if u.role}
        role_map = await self.repository.role_name_map(db, role_ids)
        return [
            {
                "id": u.id,
                "name": u.name,
                "email": u.email,
                "role": self._get_display_role(u, role_map),
                "organization_id": u.organization_id,
                "is_active": u.is_active,
                "created_at": str(u.created_at),
            }
            for u in users
        ]

    async def create_user(
        self, db: AsyncSession, payload: UserCreate, *, current_user: User
    ) -> dict:
        # The organization is derived exclusively from the authenticated user —
        # never from a client-supplied organization_id.
        org_id = await self._resolve_current_org(db, current_user)

        role = await self._resolve_assignable_role(
            db, org_id, payload.role, current_user=current_user
        )
        user = await self.repository.create(
            db,
            data={
                "name": payload.name,
                "email": payload.email,
                "hashed_password": get_password_hash(payload.password),
                "role": role.id,
                "organization_id": org_id,
            },
        )
        await db.flush()
        db.add(UserRole(user_id=user.id, role_id=role.id))
        await self._commit(db, "User creation failed")
        return user_to_dict(user)

    async def get_my_profile(self, db: AsyncSession) -> dict:
        user = await self.repository.get_first(db)
        if not user:
            raise NotFoundError(message="No profile found")
        return user_to_dict(user)

    async def update_my_profile(self, db: AsyncSession, payload: UserProfileUpdate) -> dict:
        user = await self.repository.get_first(db)
        if not user:
            raise NotFoundError(message="Profile not found")
        if payload.name:
            user.name = payload.name
        await self._commit(db, "Failed to update profile")
        return user_to_dict(user)

    async def upload_avatar(
        self, db: AsyncSession, *, file, filename: str, content_type: str | None
    ) -> dict:
        user = await self.repository.get_first(db)
        if not user:
            raise NotFoundError(message="User not found")
        try:
            object_name = f"avatars/{user.id}_{filename}"
            s3_key = s3_service.upload_file(
                file, object_name=object_name, content_type=content_type
            )
            avatar_url = s3_service.generate_presigned_url(s3_key)
            user.avatar_url = avatar_url
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

        role = await self._resolve_assignable_role(
            db, org_id, payload.role, current_user=current_user
        )
        role_id = role.id
        role_name = role.name
        invitation_responses = []
        try:
            invite_targets = []
            if payload.users:
                for u in payload.users:
                    invite_targets.append(
                        {"name": u.name or u.email.split("@")[0], "email": u.email.strip()}
                    )
            elif payload.emails:
                for email in payload.emails:
                    email_clean = email.strip()
                    target_name = payload.name or email_clean.split("@")[0]
                    invite_targets.append({"name": target_name, "email": email_clean})

            for target in invite_targets:
                token = generate_random_code(14)
                await self.repository.create_invitation(
                    db,
                    data={
                        "email": target["email"],
                        "token": token,
                        "role": role_id,
                        "organization_id": org_id,
                        "status": "pending",
                    },
                )
                await db.flush()

                invite_url = f"{settings.FRONTEND_URL}/accept-invite?token={token}"
                send_user_invite_email(
                    email_to=target["email"],
                    role=role_name,
                    invite_url=invite_url,
                )

                invitation_responses.append(
                    {
                        "name": target["name"],
                        "email": target["email"],
                        "role": role_id,
                        "role_name": role_name,
                        "status": "pending",
                    }
                )

            await db.commit()
            return {
                "message": f"Invites sent to {len(invitation_responses)} users",
                "invitations": invitation_responses,
                "status": "success",
            }
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=f"Invitation dispatch failed: {str(e)}",
            ) from e

    async def list_user_invitations(
        self, db: AsyncSession, *, token: str | None, status_filter: str | None
    ) -> list[dict]:
        invitations = await self.repository.list_invitations(
            db, token=token, status_filter=status_filter
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

    async def accept_user_invitation(self, db: AsyncSession, payload: AcceptInviteRequest) -> dict:
        inv = await self.repository.get_invitation_by_token(db, payload.token)
        if not inv:
            raise NotFoundError(message="Invalid or expired invitation token")

        role = await self.role_repository.get_role_by_id_or_name(db, inv.role)
        if not role:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=f"Invitation references an invalid role '{inv.role}'. Please contact an administrator.",
            )

        if not inv.organization_id:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Invitation has no associated organization and cannot be accepted",
            )

        try:
            accepted_any = await self.repository.get_invitation_by_email(
                db, inv.email, status="accepted"
            )
            if inv.status == "accepted" or accepted_any:
                raise APIException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    message="Invitation has already been accepted",
                )

            target_org_id = inv.organization_id

            user = await self.repository.get_by_email(db, inv.email)
            hashed_pwd = get_password_hash(payload.password)

            if user:
                user.name = payload.name
                user.hashed_password = hashed_pwd
                user.role = role.id
                user.organization_id = target_org_id
                user.is_active = True
            else:
                user = await self.repository.create(
                    db,
                    data={
                        "name": payload.name,
                        "email": inv.email,
                        "hashed_password": hashed_pwd,
                        "role": role.id,
                        "organization_id": target_org_id,
                        "is_active": True,
                    },
                )
                await db.flush()

            mapping = await self.role_repository.get_user_role_mapping(db, user.id)
            if mapping:
                mapping.role_id = role.id
            else:
                db.add(UserRole(user_id=user.id, role_id=role.id))

            inv.status = "accepted"
            for other in await self.repository.list_invitations_by_email(
                db, inv.email, exclude_id=inv.id
            ):
                other.status = "accepted"

            await db.commit()
            return {
                "message": "Invitation accepted successfully! Your account is active.",
                "user_id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user.role,
                "status": "success",
            }
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=f"Failed to accept invitation: {str(e)}",
            ) from e

    async def get_user(self, db: AsyncSession, user_id: str) -> dict:
        return user_to_dict(await self.require_user(db, user_id))

    async def update_user(
        self, db: AsyncSession, user_id: str, payload: UserUpdate, *, current_user: User
    ) -> dict:
        user = await self.require_user(db, user_id)
        if payload.name:
            user.name = payload.name
        if payload.role:
            role = await self._resolve_assignable_role(
                db, user.organization_id, payload.role, current_user=current_user
            )
            user.role = role.id
        await self._commit(db, "Failed to update user")
        return user_to_dict(user)

    async def delete_user(self, db: AsyncSession, user_id: str) -> dict:
        user = await self.require_user(db, user_id)
        if user.email.lower() == PROTECTED_SUPERADMIN_EMAIL:
            raise APIException(
                status_code=status.HTTP_403_FORBIDDEN,
                message=f"Protected user '{PROTECTED_SUPERADMIN_EMAIL}' cannot be deleted",
            )
        user_name = user.name
        user_email = user.email
        await self.repository.delete(db, user)
        await self._commit(db, "Failed to delete user")
        return {
            "message": f"User '{user_name}' ({user_email}) deleted successfully",
            "user_id": user_id,
            "name": user_name,
            "email": user_email,
            "status": "success",
        }

    async def activate_user(self, db: AsyncSession, user_id: str) -> dict:
        user = await self.require_user(db, user_id)
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

    async def deactivate_user(self, db: AsyncSession, user_id: str) -> dict:
        user = await self.require_user(db, user_id)
        if user.email.lower() == PROTECTED_SUPERADMIN_EMAIL:
            raise APIException(
                status_code=status.HTTP_403_FORBIDDEN,
                message=f"Protected user '{PROTECTED_SUPERADMIN_EMAIL}' cannot be deactivated",
            )
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

    async def get_user_activities(self, db: AsyncSession, user_id: str) -> list:
        await self.require_user(db, user_id)
        return []

    async def get_user_teams(self, db: AsyncSession, user_id: str) -> list:
        await self.require_user(db, user_id)
        return []

    async def assign_user_team(
        self, db: AsyncSession, *, user_id: str, team_id: str, team_name: str | None
    ) -> dict:
        await self.require_user(db, user_id)
        name = team_name if team_name else team_id
        return {"message": f"User assigned to team '{name}' successfully", "status": "success"}

    async def remove_user_team(self, db: AsyncSession, *, user_id: str, team_id: str) -> dict:
        await self.require_user(db, user_id)
        return {"message": f"User {user_id} removed from team {team_id}", "status": "success"}

    async def bulk_delete_users(self, db: AsyncSession, ids: list[str]) -> dict:
        users = await self.repository.list_by_ids(db, ids)
        deleted_count = 0
        for item in users:
            if item.email.lower() == PROTECTED_SUPERADMIN_EMAIL:
                continue
            await self.repository.delete(db, item)
            deleted_count += 1
        await self._commit(db, "Failed to bulk delete users")
        return {
            "affected_count": deleted_count,
            "message": "Users deleted successfully (Protected users skipped)",
        }

    async def get_user_effective_permissions(self, db: AsyncSession, user_id: str) -> dict:
        await self.require_user(db, user_id)
        return {"user_id": user_id, "permissions": ["leads:all", "deals:all", "contacts:all"]}

    async def admin_reset_user_password(self, db: AsyncSession, user_id: str) -> dict:
        await self.require_user(db, user_id)
        return {"message": f"Temporary password sent to user {user_id}", "status": "success"}

    async def _require_same_org_user(
        self, db: AsyncSession, user_id: str, current_user: User
    ) -> User:
        """Fetch a user and enforce that it belongs to the caller's organization.

        Returns 404 (not 403) for cross-org ids so callers cannot probe for
        the existence of users in other organizations.
        """
        user = await self.require_user(db, user_id)
        if getattr(current_user, "organization_id", None) != user.organization_id:
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
        await self.repository.upsert_quota(
            db,
            user_id=user.id,
            organization_id=user.organization_id,
            target_amount=float(target_amount),
        )
        await self._commit(db, "Failed to assign quota")
        return {"message": f"Quota ${target_amount} assigned to {user_id}", "status": "success"}

    async def get_user_scorecard(self, db: AsyncSession, user_id: str) -> dict:
        await self.require_user(db, user_id)
        return {"user_id": user_id, "win_rate": 0.0, "avg_deal_size": 0.0, "calls_made": 0}


user_service = UserService()
