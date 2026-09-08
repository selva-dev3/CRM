import asyncio
import json
import logging
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import unquote, urlsplit

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import APIException, ConflictError, ForbiddenError, NotFoundError
from app.core.rbac_matrix import SYSTEM_ROLE_PERMISSIONS
from app.models import Organization, OrganizationInvitation, User
from app.repositories.organization_lifecycle_repository import OrganizationLifecycleRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.role_repository import RoleRepository
from app.schemas.organization_lifecycle import (
    OrganizationCreateResponse,
    PlatformOrganizationCreate,
)
from app.services.email_service import send_user_invite_email
from app.services.organization_service import org_to_dict
from app.services.s3_service import s3_service
from app.services.subscription_plan_service import FREE_PLAN_SLUG, free_subscription_data

logger = logging.getLogger(__name__)


def ensure_platform_actor(user: User) -> None:
    if (
        getattr(user, "is_platform_admin", False) is not True
        or getattr(user, "_api_key_scopes", None) is not None
    ):
        raise ForbiddenError(message="Platform Super Admin access is required")


def storage_key(value: str, kind: str) -> str | None:
    """Resolve only our configured bucket; never request a supplied URL."""
    if kind == "url":
        parsed, endpoint = urlsplit(value), urlsplit(settings.AWS_ENDPOINT_URL)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.netloc != endpoint.netloc
            or parsed.username
            or parsed.password
        ):
            return None
        prefix = f"/{settings.AWS_S3_BUCKET}/"
        if not parsed.path.startswith(prefix):
            return None
        value = unquote(parsed.path[len(prefix) :])
    if (
        not value
        or len(value) > 1024
        or value.startswith("/")
        or "\x00" in value
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        return None
    return value


def storage_prefixes(kind: str, identifier: str) -> list[str]:
    if storage_key(identifier, "key") != identifier or "/" in identifier or len(identifier) > 255:
        raise ConflictError(
            message="Legacy storage ownership requires review before deletion",
            code="ORGANIZATION_STORAGE_CONFLICT",
        )
    safe_org = re.sub(r"[^A-Za-z0-9_-]", "_", identifier)[:64]
    return {
        "organization": [
            f"documents/{safe_org}/",
            f"exports/{safe_org}/",
            f"branding/{identifier}_",
            f"{identifier}/quotes/",
            f"{identifier}/invoices/",
            f"{identifier}/receipts/",
        ],
        "user": [f"avatars/{identifier}_"],
        "lead": [f"leads/{identifier}/"],
        "schedule": [f"exports/scheduled/{identifier}/"],
    }[kind]


class OrganizationLifecycleService:
    def __init__(self, repository: OrganizationLifecycleRepository | None = None) -> None:
        self.repository = repository or OrganizationLifecycleRepository()
        self.organizations = OrganizationRepository()
        self.roles = RoleRepository()

    async def _rollback(self, db: AsyncSession) -> None:
        try:
            await db.rollback()
        except SQLAlchemyError:
            logger.error("Organization lifecycle rollback failed")

    async def _commit(self, db: AsyncSession) -> None:
        await db.commit()

    async def provision(
        self, db: AsyncSession, payload: PlatformOrganizationCreate, actor: User
    ) -> tuple[Organization, OrganizationInvitation | None]:
        """Stage a complete tenant; callers own commit and post-commit delivery."""
        ensure_platform_actor(actor)
        plan = await self.organizations.get_plan_by_slug(db, FREE_PLAN_SLUG)
        if not plan or not plan.is_active or plan.price_monthly != 0:
            raise APIException(
                message="The default subscription plan is not configured",
                code="FREE_SUBSCRIPTION_PLAN_UNAVAILABLE",
                status_code=503,
            )
        catalog = await self.repository.permission_catalog(db)
        if not set().union(*SYSTEM_ROLE_PERMISSIONS.values()).issubset(catalog):
            raise APIException(
                message="Approved permissions are not initialized",
                code="RBAC_NOT_INITIALIZED",
                status_code=503,
            )
        if payload.initial_admin:
            email = str(payload.initial_admin.email).lower()
            await self.repository.lock_invitation_email(db, email)
            if await self.repository.email_in_use(
                db, email
            ) or await self.repository.pending_invitation_exists(db, email):
                raise ConflictError(
                    message="This email already has an account or pending invitation",
                    code="ADMIN_EMAIL_CONFLICT",
                    fields={"initial_admin.email": "Choose an unused email address"},
                )
        organization = await self.organizations.create(
            db,
            data={
                "id": str(uuid.uuid4()),
                "name": payload.name,
                "slug": str(uuid.uuid4()),
                "status": "active",
                "is_active": True,
                "plan": plan.name,
                "max_users": plan.max_users,
                "timezone": "Asia/Kolkata",
                "currency": "INR",
                "language": "en",
            },
        )
        await db.flush()
        await self.organizations.create_setting(
            db,
            data={
                "organization_id": organization.id,
                "timezone": organization.timezone,
                "currency": organization.currency,
                "language": organization.language,
            },
        )
        subscription = await self.organizations.create_subscription(
            db,
            data=free_subscription_data(
                organization_id=organization.id,
                plan=plan,
                current_users=0,
            ),
        )
        role_ids = {}
        for name, permissions in SYSTEM_ROLE_PERMISSIONS.items():
            role = await self.roles.create_role(
                db,
                name=name,
                description=f"System {name} role",
                organization_id=organization.id,
                is_system_role=True,
            )
            await db.flush()
            role_ids[name] = role.id
            for key in sorted(permissions):
                await self.roles.add_role_permission(db, role.id, catalog[key])
        invitation = None
        if payload.initial_admin:
            await db.flush()
            invitation = await self.repository.create_invitation(
                db,
                organization_id=organization.id,
                subscription_id=subscription.id,
                email=str(payload.initial_admin.email).lower(),
                full_name=payload.initial_admin.name,
                role_id=role_ids["Admin"],
                token=secrets.token_urlsafe(32),
                status="Pending",
                expires_at=datetime.now(UTC) + timedelta(hours=24),
            )
        await self.repository.audit(
            db,
            actor_id=actor.id,
            action="CREATE_ORGANIZATION",
            details=json.dumps(
                {
                    "organization_id": organization.id,
                    "organization_name": organization.name,
                    "result": "success",
                }
            ),
        )
        await db.flush()
        return organization, invitation

    async def create(
        self, db: AsyncSession, payload: PlatformOrganizationCreate, actor: User
    ) -> OrganizationCreateResponse:
        ensure_platform_actor(actor)
        actor_id = actor.id
        try:
            organization, invitation = await self.provision(db, payload, actor)
            response = OrganizationCreateResponse(organization=org_to_dict(organization, 0))
            await self._commit(db)
        except IntegrityError as exc:
            await self._rollback(db)
            if "uq_organizations_normalized_name" in str(exc.orig):
                raise ConflictError(
                    message="An organization with this name already exists",
                    code="ORGANIZATION_NAME_CONFLICT",
                    fields={"name": "An organization with this name already exists"},
                ) from exc
            raise ConflictError(
                message="Organization provisioning conflicted with existing data",
                code="ORGANIZATION_PROVISIONING_CONFLICT",
            ) from exc
        except APIException:
            await self._rollback(db)
            raise
        except Exception as exc:
            await self._rollback(db)
            logger.error("Organization provisioning failed actor_id=%s", actor_id)
            raise APIException(
                message="Unable to provision organization; no organization was created",
                code="ORGANIZATION_PROVISIONING_FAILED",
                status_code=500,
            ) from exc
        if invitation:
            from app.schemas.organization_lifecycle import ProvisionedInvitation

            sent = False
            try:
                sent = await asyncio.to_thread(
                    send_user_invite_email,
                    email_to=invitation.email,
                    role="Admin",
                    invite_url=f"{settings.frontend_base_url}/accept-invite/organization/{invitation.token}",
                )
            except Exception:
                logger.warning(
                    "Initial Admin invitation delivery failed invitation_id=%s", invitation.id
                )
            response.invitation = ProvisionedInvitation(
                id=invitation.id, delivery_status="sent" if sent else "failed"
            )
        return response

    async def delete(self, db: AsyncSession, organization_id: str, actor: User) -> dict:
        ensure_platform_actor(actor)
        if not settings.ORGANIZATION_DELETION_ENABLED:
            raise APIException(
                message="Organization deletion awaits verified recovery and cleanup-worker readiness",
                code="ORGANIZATION_DELETION_NOT_ENABLED",
                status_code=503,
            )
        try:
            async with asyncio.timeout(60):
                await self.repository.set_lock_timeout(db)
                organization = await self.organizations.get_by_id_for_update(db, organization_id)
                if not organization:
                    raise NotFoundError(message="Organization not found")
                await self.repository.lock_tenant_records(db, organization_id)
                if await self.repository.protected_platform_member(db, organization_id):
                    raise ConflictError(
                        message="The platform identity must remain independent of organizations",
                        code="PLATFORM_IDENTITY_PROTECTED",
                    )
                if await self.repository.billing_blocked(db, organization_id):
                    raise ConflictError(
                        message="Organization has recorded payments or billing requiring reconciliation",
                        code="ORGANIZATION_BILLING_PROTECTED",
                    )
                if await self.repository.has_active_work(db, organization_id):
                    raise ConflictError(
                        message="Organization has active or unresolved delivery work; retry after reconciliation",
                        code="ORGANIZATION_BUSY",
                    )
                if await self.repository.cross_tenant_reference(db, organization_id):
                    raise ConflictError(
                        message="Cross-organization references require review before deletion",
                        code="ORGANIZATION_DEPENDENCY_CONFLICT",
                    )
                keys: set[str] = set()
                async for _, value, kind in self.repository.storage_references(
                    db, organization_id, owned_only=True
                ):
                    key = storage_key(value, kind)
                    if key is None:
                        raise ConflictError(
                            message="Stored file ownership requires review before deletion",
                            code="ORGANIZATION_STORAGE_CONFLICT",
                        )
                    keys.add(key)
                    if len(keys) > 10000:
                        raise ConflictError(
                            message="Tenant storage inventory exceeds online deletion limits",
                            code="ORGANIZATION_STORAGE_CONFLICT",
                        )
                owned_prefixes = set()
                async for kind, identifier in self.repository.storage_prefix_owners(
                    db, organization_id
                ):
                    owned_prefixes.update(storage_prefixes(kind, identifier))
                    if len(owned_prefixes) > 64:
                        raise ConflictError(message="Tenant storage prefix inventory exceeds online limits; use a reviewed maintenance deletion", code="ORGANIZATION_STORAGE_CONFLICT")
                # Collapse nested prefixes, then compare adjacent sorted entries to
                # detect sanitized-ID and legacy underscore-prefix collisions.
                prefixes: list[str] = []
                for prefix in sorted(owned_prefixes):
                    if not prefixes or not prefix.startswith(prefixes[-1]):
                        prefixes.append(prefix)
                if await self.repository.storage_prefix_conflict(db, organization_id, prefixes):
                    raise ConflictError(message="Storage owner prefixes overlap another organization; review before deletion", code="ORGANIZATION_STORAGE_CONFLICT")
                for prefix in prefixes:
                    try:
                        files = await asyncio.to_thread(
                            s3_service.list_file_keys,
                            prefix,
                            10000 - len(keys),
                            keys,
                        )
                    except ValueError as exc:
                        raise ConflictError(message="Tenant storage inventory exceeds online limits; use a reviewed maintenance deletion", code="ORGANIZATION_STORAGE_CONFLICT") from exc
                    if any(
                        not key.startswith(prefix) or storage_key(key, "key") != key for key in files
                    ):
                        raise ConflictError(
                            message="Stored object ownership requires review",
                            code="ORGANIZATION_STORAGE_CONFLICT",
                        )
                    keys.update(files)
                if keys:
                    async for _, value, kind in self.repository.storage_references(
                        db, organization_id, owned_only=False
                    ):
                        if storage_key(value, kind) in keys:
                            raise ConflictError(
                                message="Stored files are referenced outside this organization",
                                code="ORGANIZATION_STORAGE_CONFLICT",
                            )
                operation = await self.repository.create_deletion(
                    db, organization=organization, actor_id=actor.id
                )
                await self.repository.enqueue_files(
                    db,
                    operation.id,
                    keys,
                    endpoint=settings.AWS_ENDPOINT_URL,
                    bucket=settings.AWS_S3_BUCKET,
                )
                await self.repository.audit(
                    db,
                    actor_id=actor.id,
                    action="DELETE_ORGANIZATION",
                    details=json.dumps(
                        {
                            "organization_id": organization_id,
                            "organization_name": organization.name,
                            "operation_id": operation.id,
                            "result": "success",
                            "file_cleanup": "pending" if keys else "complete",
                        }
                    ),
                )
                await self.repository.delete_dependencies(db, organization_id)
                await self.organizations.delete(db, organization)
            await self._commit(db)
            return {
                "message": "Organization and tenant database records deleted",
                "status": "success",
                "operation_id": operation.id,
                "cleanup_status": "pending" if keys else "complete",
            }
        except APIException:
            await self._rollback(db)
            raise
        except TimeoutError as exc:
            await self._rollback(db)
            raise APIException(message="Deletion preparation timed out; no changes were committed. Retry during a maintenance window.", code="ORGANIZATION_DELETION_TIMEOUT", status_code=503) from exc
        except SQLAlchemyError as exc:
            await self._rollback(db)
            logger.error(
                "Organization deletion transaction failed organization_id=%s", organization_id
            )
            raise ConflictError(
                message="Organization deletion could not complete; no records were deleted. Retry or review dependencies.",
                code="ORGANIZATION_DELETION_CONFLICT",
            ) from exc
        except Exception as exc:
            await self._rollback(db)
            logger.error("Organization deletion failed organization_id=%s", organization_id)
            raise APIException(
                message="Organization deletion failed; no records were deleted", status_code=500
            ) from exc

    async def deletion_status(self, db: AsyncSession, operation_id: str, actor: User) -> dict:
        ensure_platform_actor(actor)
        operation = await self.repository.get_deletion(db, operation_id)
        if not operation:
            raise NotFoundError(message="Deletion operation not found")
        counts = await self.repository.cleanup_counts(db, operation_id)
        return {
            "id": operation.id,
            "organization_id": operation.organization_id,
            "organization_name": operation.organization_name,
            "created_at": operation.created_at,
            "cleanup_status": (
                "failed"
                if counts.get("failed")
                else "pending" if counts.get("pending") else "complete"
            ),
            "pending_files": counts.get("pending", 0),
            "failed_files": counts.get("failed", 0),
            "completed_files": counts.get("complete", 0),
        }

    async def retry_cleanup(self, db: AsyncSession, operation_id: str, actor: User) -> dict:
        await self.deletion_status(db, operation_id, actor)
        try:
            await self.repository.retry_cleanup(db, operation_id)
            await self._commit(db)
        except Exception:
            await self._rollback(db)
            raise
        return await self.deletion_status(db, operation_id, actor)


organization_lifecycle_service = OrganizationLifecycleService()
