import json
from datetime import UTC, datetime

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.core.permissions import (
    effective_organization_id,
    ensure_can_assign_role,
    ensure_tenant_managed_user,
    is_global_super_admin_role,
    is_super_admin_role,
    is_super_admin_role_name,
    is_super_admin_user,
)
from app.core.rbac_matrix import (
    ADMIN_PERMISSIONS,
    APPROVED_PERMISSION_KEYS,
    validate_permission_keys,
)
from app.models import AuditLog, Role, User
from app.repositories.role_repository import RoleRepository
from app.schemas.crm_schemas import PermissionCreate, RoleCreate, RoleUpdate
from app.services.auth_service import AuthService

logger = get_logger(__name__)

ALL_STANDARD_PERMISSIONS = [
    {
        "key": "dashboard:read",
        "name": "View Dashboard",
        "category": "Dashboard",
        "description": "View CRM executive dashboard metrics",
    },
    {
        "key": "dashboard:customize",
        "name": "Customize Dashboard",
        "category": "Dashboard",
        "description": "Customize dashboard widgets and layout",
    },
    {
        "key": "dashboard:export",
        "name": "Export Dashboard",
        "category": "Dashboard",
        "description": "Export dashboard data to PDF or Excel",
    },
    {
        "key": "leads:read",
        "name": "View Leads",
        "category": "Leads",
        "description": "View sales leads and details",
    },
    {
        "key": "leads:create",
        "name": "Create Leads",
        "category": "Leads",
        "description": "Create new sales leads",
    },
    {
        "key": "leads:update",
        "name": "Update Leads",
        "category": "Leads",
        "description": "Edit existing lead details",
    },
    {
        "key": "leads:delete",
        "name": "Delete Leads",
        "category": "Leads",
        "description": "Delete lead records",
    },
    {
        "key": "leads:export",
        "name": "Export Leads",
        "category": "Leads",
        "description": "Export leads to CSV/Excel",
    },
    {
        "key": "leads:import",
        "name": "Import Leads",
        "category": "Leads",
        "description": "Import leads from CSV/Excel",
    },
    {
        "key": "leads:assign",
        "name": "Assign Leads",
        "category": "Leads",
        "description": "Assign leads to team members",
    },
    {
        "key": "leads:convert",
        "name": "Convert Leads",
        "category": "Leads",
        "description": "Convert leads into accounts and deals",
    },
    {
        "key": "leads:bulk_delete",
        "name": "Bulk Delete Leads",
        "category": "Leads",
        "description": "Perform bulk deletion on multiple leads",
    },
    {
        "key": "leads:bulk_update",
        "name": "Bulk Update Leads",
        "category": "Leads",
        "description": "Perform bulk updates on lead fields",
    },
    {
        "key": "contacts:read",
        "name": "View Contacts",
        "category": "Contacts",
        "description": "View contact records",
    },
    {
        "key": "contacts:create",
        "name": "Create Contacts",
        "category": "Contacts",
        "description": "Create new contact records",
    },
    {
        "key": "contacts:update",
        "name": "Update Contacts",
        "category": "Contacts",
        "description": "Edit existing contact information",
    },
    {
        "key": "contacts:delete",
        "name": "Delete Contacts",
        "category": "Contacts",
        "description": "Delete contact records",
    },
    {
        "key": "contacts:export",
        "name": "Export Contacts",
        "category": "Contacts",
        "description": "Export contact list",
    },
    {
        "key": "contacts:import",
        "name": "Import Contacts",
        "category": "Contacts",
        "description": "Import contact list",
    },
    {
        "key": "contacts:assign",
        "name": "Assign Contacts",
        "category": "Contacts",
        "description": "Assign contacts to owners",
    },
    {
        "key": "contacts:bulk_delete",
        "name": "Bulk Delete Contacts",
        "category": "Contacts",
        "description": "Bulk delete selected contacts",
    },
    {
        "key": "contacts:bulk_update",
        "name": "Bulk Update Contacts",
        "category": "Contacts",
        "description": "Bulk update contact fields",
    },
    {
        "key": "companies:read",
        "name": "View Companies",
        "category": "Companies",
        "description": "View company accounts",
    },
    {
        "key": "companies:create",
        "name": "Create Companies",
        "category": "Companies",
        "description": "Create new company accounts",
    },
    {
        "key": "companies:update",
        "name": "Update Companies",
        "category": "Companies",
        "description": "Update company account details",
    },
    {
        "key": "companies:delete",
        "name": "Delete Companies",
        "category": "Companies",
        "description": "Delete company accounts",
    },
    {
        "key": "companies:export",
        "name": "Export Companies",
        "category": "Companies",
        "description": "Export company account list",
    },
    {
        "key": "companies:import",
        "name": "Import Companies",
        "category": "Companies",
        "description": "Import company accounts",
    },
    {
        "key": "companies:bulk_delete",
        "name": "Bulk Delete Companies",
        "category": "Companies",
        "description": "Bulk delete company accounts",
    },
    {
        "key": "deals:read",
        "name": "View Deals",
        "category": "Deals",
        "description": "View sales deals and pipelines",
    },
    {
        "key": "deals:create",
        "name": "Create Deals",
        "category": "Deals",
        "description": "Create new deal opportunities",
    },
    {
        "key": "deals:update",
        "name": "Update Deals",
        "category": "Deals",
        "description": "Update deal stages and amounts",
    },
    {
        "key": "deals:delete",
        "name": "Delete Deals",
        "category": "Deals",
        "description": "Delete deal opportunities",
    },
    {
        "key": "deals:pipeline",
        "name": "Manage Pipelines",
        "category": "Deals",
        "description": "Configure deal pipeline stages",
    },
    {
        "key": "deals:export",
        "name": "Export Deals",
        "category": "Deals",
        "description": "Export sales deal data",
    },
    {
        "key": "deals:import",
        "name": "Import Deals",
        "category": "Deals",
        "description": "Import deal opportunities",
    },
    {
        "key": "deals:assign",
        "name": "Assign Deals",
        "category": "Deals",
        "description": "Reassign deal ownership",
    },
    {
        "key": "deals:bulk_delete",
        "name": "Bulk Delete Deals",
        "category": "Deals",
        "description": "Bulk delete selected deals",
    },
    {
        "key": "tasks:read",
        "name": "View Tasks",
        "category": "Tasks",
        "description": "View task lists and status",
    },
    {
        "key": "tasks:create",
        "name": "Create Tasks",
        "category": "Tasks",
        "description": "Create new task items",
    },
    {
        "key": "tasks:update",
        "name": "Update Tasks",
        "category": "Tasks",
        "description": "Update task progress and status",
    },
    {
        "key": "tasks:delete",
        "name": "Delete Tasks",
        "category": "Tasks",
        "description": "Delete task items",
    },
    {
        "key": "tasks:assign",
        "name": "Assign Tasks",
        "category": "Tasks",
        "description": "Assign tasks to team members",
    },
    {
        "key": "tasks:complete",
        "name": "Mark Tasks Complete",
        "category": "Tasks",
        "description": "Mark assigned tasks completed",
    },
    {
        "key": "projects:read",
        "name": "View Projects",
        "category": "Projects",
        "description": "View organization projects",
    },
    {
        "key": "projects:create",
        "name": "Create Projects",
        "category": "Projects",
        "description": "Create organization projects",
    },
    {
        "key": "projects:update",
        "name": "Update Projects",
        "category": "Projects",
        "description": "Edit organization projects",
    },
    {
        "key": "projects:delete",
        "name": "Delete Projects",
        "category": "Projects",
        "description": "Delete organization projects",
    },
    {
        "key": "projects:assign",
        "name": "Assign Projects",
        "category": "Projects",
        "description": "Assign projects to team members",
    },
    {
        "key": "meetings:read",
        "name": "View Meetings",
        "category": "Meetings",
        "description": "View scheduled meetings",
    },
    {
        "key": "meetings:create",
        "name": "Schedule Meetings",
        "category": "Meetings",
        "description": "Schedule new customer meetings",
    },
    {
        "key": "meetings:update",
        "name": "Update Meetings",
        "category": "Meetings",
        "description": "Reschedule or update meeting details",
    },
    {
        "key": "meetings:delete",
        "name": "Cancel Meetings",
        "category": "Meetings",
        "description": "Cancel or delete meetings",
    },
    {
        "key": "meetings:invite",
        "name": "Invite Meeting Attendees",
        "category": "Meetings",
        "description": "Send invitations to meeting attendees",
    },
    {
        "key": "calls:read",
        "name": "View Call Logs",
        "category": "Calls",
        "description": "View sales call logs and recordings",
    },
    {
        "key": "calls:create",
        "name": "Log Calls",
        "category": "Calls",
        "description": "Log new outbound or inbound calls",
    },
    {
        "key": "calls:update",
        "name": "Update Call Logs",
        "category": "Calls",
        "description": "Update call notes and outcomes",
    },
    {
        "key": "calls:delete",
        "name": "Delete Call Logs",
        "category": "Calls",
        "description": "Delete call log entries",
    },
    {
        "key": "calls:recording",
        "name": "Access Call Recordings",
        "category": "Calls",
        "description": "Listen to and download call recordings",
    },
    {
        "key": "emails:read",
        "name": "View Email Logs",
        "category": "Emails",
        "description": "View sent and received emails",
    },
    {
        "key": "emails:send",
        "name": "Send Emails",
        "category": "Emails",
        "description": "Send emails to leads and contacts",
    },
    {
        "key": "emails:templates",
        "name": "Manage Templates",
        "category": "Emails",
        "description": "Create and edit email templates",
    },
    {
        "key": "emails:delete",
        "name": "Delete Email Logs",
        "category": "Emails",
        "description": "Delete stored email conversation logs",
    },
    {
        "key": "notes:read",
        "name": "View Notes",
        "category": "Notes",
        "description": "View notes on CRM records",
    },
    {
        "key": "notes:create",
        "name": "Create Notes",
        "category": "Notes",
        "description": "Add new notes to leads, contacts, or deals",
    },
    {
        "key": "notes:update",
        "name": "Update Notes",
        "category": "Notes",
        "description": "Edit existing note content",
    },
    {
        "key": "notes:delete",
        "name": "Delete Notes",
        "category": "Notes",
        "description": "Delete notes from records",
    },
    {
        "key": "documents:read",
        "name": "View Documents",
        "category": "Documents",
        "description": "View attached documents and files",
    },
    {
        "key": "documents:upload",
        "name": "Upload Documents",
        "category": "Documents",
        "description": "Upload new files to MinIO S3 storage",
    },
    {
        "key": "documents:delete",
        "name": "Delete Documents",
        "category": "Documents",
        "description": "Delete uploaded documents",
    },
    {
        "key": "documents:share",
        "name": "Share Documents",
        "category": "Documents",
        "description": "Share document links externally",
    },
    {
        "key": "products:read",
        "name": "View Products",
        "category": "Products",
        "description": "View product catalog and price list",
    },
    {
        "key": "products:create",
        "name": "Create Products",
        "category": "Products",
        "description": "Add new products to catalog",
    },
    {
        "key": "products:update",
        "name": "Update Products",
        "category": "Products",
        "description": "Edit product pricing and details",
    },
    {
        "key": "products:delete",
        "name": "Delete Products",
        "category": "Products",
        "description": "Remove products from catalog",
    },
    {
        "key": "products:export",
        "name": "Export Products",
        "category": "Products",
        "description": "Export product catalog to CSV",
    },
    {
        "key": "products:import",
        "name": "Import Products",
        "category": "Products",
        "description": "Import product catalog",
    },
    {
        "key": "quotes:read",
        "name": "View Quotes",
        "category": "Quotes",
        "description": "View sales quotes and proposals",
    },
    {
        "key": "quotes:create",
        "name": "Create Quotes",
        "category": "Quotes",
        "description": "Generate new sales quotes",
    },
    {
        "key": "quotes:update",
        "name": "Update Quotes",
        "category": "Quotes",
        "description": "Edit sales quotes and line items",
    },
    {
        "key": "quotes:approve",
        "name": "Approve Quotes",
        "category": "Quotes",
        "description": "Approve high-value sales quotes",
    },
    {
        "key": "quotes:delete",
        "name": "Delete Quotes",
        "category": "Quotes",
        "description": "Delete sales quotes",
    },
    {
        "key": "quotes:send",
        "name": "Send Quotes to Client",
        "category": "Quotes",
        "description": "Send PDF quote proposals to client",
    },
    {
        "key": "invoices:read",
        "name": "View Invoices",
        "category": "Invoices",
        "description": "View customer invoices and payments",
    },
    {
        "key": "invoices:create",
        "name": "Create Invoices",
        "category": "Invoices",
        "description": "Create new billing invoices",
    },
    {
        "key": "invoices:update",
        "name": "Update Invoices",
        "category": "Invoices",
        "description": "Edit invoice details",
    },
    {
        "key": "invoices:send",
        "name": "Send Invoices",
        "category": "Invoices",
        "description": "Send invoices to customers",
    },
    {
        "key": "invoices:delete",
        "name": "Delete Invoices",
        "category": "Invoices",
        "description": "Delete invoice records",
    },
    {
        "key": "invoices:payment",
        "name": "Record Payments",
        "category": "Invoices",
        "description": "Record payment receipts on invoices",
    },
    {
        "key": "reports:read",
        "name": "View Analytics & Reports",
        "category": "Reports",
        "description": "View dashboard charts and reports",
    },
    {
        "key": "reports:create",
        "name": "Create Reports",
        "category": "Reports",
        "description": "Build custom analytics reports",
    },
    {
        "key": "reports:export",
        "name": "Export Reports",
        "category": "Reports",
        "description": "Export analytics data",
    },
    {
        "key": "reports:schedule",
        "name": "Schedule Automated Reports",
        "category": "Reports",
        "description": "Configure automated email report delivery",
    },
    {
        "key": "calendar:read",
        "name": "View Calendar",
        "category": "Calendar",
        "description": "View shared team calendar",
    },
    {
        "key": "calendar:write",
        "name": "Manage Calendar Events",
        "category": "Calendar",
        "description": "Create and edit team calendar events",
    },
    {
        "key": "calendar:sync",
        "name": "Sync External Calendar",
        "category": "Calendar",
        "description": "Sync Google and Outlook calendars",
    },
    {
        "key": "users:read",
        "name": "View Users",
        "category": "Users",
        "description": "View organization user list",
    },
    {
        "key": "users:create",
        "name": "Create Users",
        "category": "Users",
        "description": "Create new user accounts",
    },
    {
        "key": "users:invite",
        "name": "Invite Users",
        "category": "Users",
        "description": "Invite new users to organization",
    },
    {
        "key": "users:update",
        "name": "Update Users",
        "category": "Users",
        "description": "Update user profiles and status",
    },
    {
        "key": "users:delete",
        "name": "Delete Users",
        "category": "Users",
        "description": "Remove users from organization",
    },
    {
        "key": "users:export",
        "name": "Export User Directory",
        "category": "Users",
        "description": "Export team member directory",
    },
    {
        "key": "users:import",
        "name": "Import Users",
        "category": "Users",
        "description": "Import users in bulk",
    },
    {
        "key": "users:roles",
        "name": "Assign User Roles",
        "category": "Users",
        "description": "Change assigned RBAC roles for users",
    },
    {
        "key": "roles:read",
        "name": "View Roles & Permissions",
        "category": "Roles",
        "description": "View RBAC roles and permissions",
    },
    {
        "key": "roles:create",
        "name": "Create Custom Roles",
        "category": "Roles",
        "description": "Create new custom RBAC roles",
    },
    {
        "key": "roles:update",
        "name": "Update Roles",
        "category": "Roles",
        "description": "Edit role permissions",
    },
    {
        "key": "roles:delete",
        "name": "Delete Roles",
        "category": "Roles",
        "description": "Delete custom RBAC roles",
    },
    {
        "key": "roles:assign",
        "name": "Assign Role Permissions",
        "category": "Roles",
        "description": "Modify assigned action permissions",
    },
    {
        "key": "organization:read",
        "name": "View Organization Details",
        "category": "Organization",
        "description": "View organization profile",
    },
    {
        "key": "organization:update",
        "name": "Update Organization Profile",
        "category": "Organization",
        "description": "Edit organization settings",
    },
    {
        "key": "organization:billing",
        "name": "Manage Subscriptions",
        "category": "Organization",
        "description": "Manage subscription plans and billing",
    },
    {
        "key": "organization:domains",
        "name": "Manage Custom Domains",
        "category": "Organization",
        "description": "Configure custom domain verification",
    },
    {
        "key": "organization:branding",
        "name": "Update Organization Logo",
        "category": "Organization",
        "description": "Upload S3 logo and branding colors",
    },
    {
        "key": "organization:audit",
        "name": "View Audit Trail Logs",
        "category": "Organization",
        "description": "View organization audit logs",
    },
    {
        "key": "invitations:read",
        "name": "View Organization Invitations",
        "category": "Organization Invitations",
        "description": "View pending organization invites",
    },
    {
        "key": "invitations:create",
        "name": "Create Organization Invitation",
        "category": "Organization Invitations",
        "description": "Send new organization invitations",
    },
    {
        "key": "invitations:resend",
        "name": "Resend Invitation",
        "category": "Organization Invitations",
        "description": "Resend pending organization invitations",
    },
    {
        "key": "invitations:revoke",
        "name": "Revoke Invitation",
        "category": "Organization Invitations",
        "description": "Revoke pending organization invitations",
    },
    {
        "key": "integrations:read",
        "name": "View Integrations",
        "category": "Integrations",
        "description": "View connected third-party tools",
    },
    {
        "key": "integrations:manage",
        "name": "Manage Integrations",
        "category": "Integrations",
        "description": "Configure webhooks and integrations",
    },
    {
        "key": "integrations:apikeys",
        "name": "Manage API Keys",
        "category": "Integrations",
        "description": "Generate and revoke developer API keys",
    },
    {
        "key": "notifications:read",
        "name": "View Notifications",
        "category": "Notifications",
        "description": "View system notifications and alerts",
    },
    {
        "key": "notifications:manage",
        "name": "Manage Notification Rules",
        "category": "Notifications",
        "description": "Configure notification delivery preferences",
    },
    {
        "key": "notifications:send",
        "name": "Send Broadcast Notifications",
        "category": "Notifications",
        "description": "Send broadcast alerts to team",
    },
    {
        "key": "settings:read",
        "name": "View System Settings",
        "category": "Settings",
        "description": "View system-wide settings",
    },
    {
        "key": "settings:update",
        "name": "Update System Settings",
        "category": "Settings",
        "description": "Modify system configurations",
    },
    {
        "key": "settings:security",
        "name": "Manage Security & Auth Settings",
        "category": "Settings",
        "description": "Configure password policies and 2FA",
    },
    {
        "key": "activities:read",
        "name": "View Activity Trail",
        "category": "Activities",
        "description": "View activity logs across CRM",
    },
    {
        "key": "activities:create",
        "name": "Log Activity",
        "category": "Activities",
        "description": "Log new system activity",
    },
    {
        "key": "activities:export",
        "name": "Export Activity Trail",
        "category": "Activities",
        "description": "Export activity trail logs to CSV",
    },
    {
        "key": "ai:read",
        "name": "Access AI Sales Assistant",
        "category": "AI Assistant",
        "description": "Chat with AI sales assistant",
    },
    {
        "key": "ai:generate",
        "name": "Generate AI Content & Insights",
        "category": "AI Assistant",
        "description": "Generate AI email drafts and deal summaries",
    },
    {
        "key": "super_admin:manage",
        "name": "Super Admin Platform Management",
        "category": "Super Admin",
        "description": "Platform-level operations such as creating organizations",
    },
]


# Preserve registered display metadata and supply every approved key on new databases.
_registered_keys = {item["key"] for item in ALL_STANDARD_PERMISSIONS}
ALL_STANDARD_PERMISSIONS.extend(
    {
        "key": key,
        "name": key.replace(":", " ").replace("_", " ").title(),
        "category": key.split(":")[0].title(),
        "description": "Standard CRM permission",
    }
    for key in sorted(APPROVED_PERMISSION_KEYS - _registered_keys)
)
if {item["key"] for item in ALL_STANDARD_PERMISSIONS} != APPROVED_PERMISSION_KEYS:
    raise RuntimeError("Permission display metadata does not match the approved catalog")


def role_to_dict(role: Role, permissions: list, created_at: str = "2026-08-05") -> dict:
    return {
        "id": role.id,
        "name": role.name,
        "description": role.description or "Custom Role",
        "permissions": permissions,
        "is_system_role": getattr(role, "is_system_role", False),
        "created_at": created_at,
    }


class RoleService:
    """Business logic for the Role/Permission domain."""

    def __init__(
        self,
        repository: RoleRepository | None = None,
        authorization_service: AuthService | None = None,
    ) -> None:
        self.repository = repository or RoleRepository()
        self.authorization_service = authorization_service or AuthService()

    async def _commit(
        self, db: AsyncSession, error_message: str, status_code: int = status.HTTP_400_BAD_REQUEST
    ) -> None:
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise APIException(status_code=status_code, message=error_message) from e

    @staticmethod
    def _role_setting_key(key: str, organization_id: str | None) -> str:
        return f"{key}:{organization_id}" if organization_id else key

    async def _get_default_role_ids(
        self, db: AsyncSession, organization_id: str | None = None
    ) -> set:
        return set(await self._get_ordered_default_role_ids(db, organization_id))

    async def _get_ordered_default_role_ids(
        self, db: AsyncSession, organization_id: str | None = None
    ) -> list[str]:
        try:
            setting = await self.repository.get_setting(
                db, self._role_setting_key("default_registration_roles", organization_id)
            )
            if setting and setting.value:
                try:
                    val = json.loads(setting.value)
                    if isinstance(val, list):
                        return list(
                            dict.fromkeys(
                                item.strip()
                                for item in val
                                if isinstance(item, str) and item.strip()
                            )
                        )
                except Exception:
                    return list(
                        dict.fromkeys(s.strip() for s in setting.value.split(",") if s.strip())
                    )
            legacy = await self.repository.get_setting(
                db, self._role_setting_key("default_registration_role", organization_id)
            )
            if legacy and legacy.value:
                return [legacy.value.strip()] if legacy.value.strip() else []
        except Exception:
            logger.warning("Failed to resolve configured default role IDs", exc_info=True)
        return []

    async def _resolve_role_permission_keys(self, db: AsyncSession, role: Role) -> list[str]:
        """Resolve the effective permission keys for a role strictly from its assigned
        role_permissions (no role-name based shortcuts and no implicit expansion).

        The protected global Super Admin role is represented with the explicit
        approved catalog for display. Organization roles, including Admin and
        other system roles, resolve only to assigned approved permissions.
        """
        if is_global_super_admin_role(role):
            return sorted(APPROVED_PERMISSION_KEYS)
        assigned = await self.repository.get_role_permissions(db, role.id)
        return [p.key for p in assigned if p.key in ADMIN_PERMISSIONS] if assigned else []

    async def _get_permission_keys_for_role(self, db: AsyncSession, role: Role) -> list[str]:
        return await self._resolve_role_permission_keys(db, role)

    @staticmethod
    def _ensure_mutable_role(role: Role) -> None:
        """Deny mutation of system roles. Enforced server-side regardless of caller permissions."""
        if getattr(role, "is_system_role", False):
            raise ForbiddenError(message="System roles cannot be modified or deleted.")

    @staticmethod
    def _current_org_id(current_user: User) -> str:
        org_id = effective_organization_id(current_user)
        if not org_id:
            raise ForbiddenError(message="Authenticated user has no current organization")
        return org_id

    @staticmethod
    def _audit(
        db: AsyncSession,
        *,
        current_user: User,
        action: str,
        target_type: str,
        target_id: str,
        before: dict | None = None,
        after: dict | None = None,
    ) -> None:
        db.add(
            AuditLog(
                organization_id=effective_organization_id(current_user),
                user_id=current_user.id,
                action=action,
                details=json.dumps(
                    {
                        "target_type": target_type,
                        "target_id": target_id,
                        "before": before,
                        "after": after,
                    },
                    sort_keys=True,
                ),
            )
        )

    async def _validated_permissions(
        self, db: AsyncSession, values: list[str]
    ) -> tuple[list[str], list]:
        keys = validate_permission_keys(values)
        if not keys:
            return [], []
        permissions = list(await self.repository.get_permissions_by_keys_or_ids(db, keys))
        by_key = {permission.key: permission for permission in permissions if permission.key}
        missing = sorted(set(keys) - set(by_key))
        if missing:
            raise APIException(
                status_code=status.HTTP_409_CONFLICT,
                code="PERMISSION_CATALOG_INCOMPLETE",
                message=f"Approved permission keys are not provisioned: {', '.join(missing)}",
            )
        return keys, [by_key[key] for key in keys]

    @classmethod
    def _ensure_assignable_role_ownership(cls, role: Role, current_user: User) -> None:
        org_id = cls._current_org_id(current_user)
        if role.organization_id != org_id:
            raise NotFoundError(message=f"Role '{role.id}' not found")

    @classmethod
    def _ensure_mutable_role_ownership(cls, role: Role, current_user: User) -> None:
        cls._ensure_assignable_role_ownership(role, current_user)
        cls._ensure_mutable_role(role)

    # --- List roles ---
    async def list_roles(
        self,
        db: AsyncSession,
        search: str | None = None,
        org_id: str | None = None,
        *,
        page: int | None = None,
        limit: int = 50,
    ) -> list[dict]:
        default_ids = await self._get_default_role_ids(db, org_id)
        if page is None:
            roles = list(await self.repository.list_roles(db, search, org_id=org_id))
        else:
            roles = list(
                await self.repository.list_roles(db, search, org_id=org_id, page=page, limit=limit)
            )
        permissions_by_role = await self.repository.get_permission_keys_by_role_ids(
            db, [role.id for role in roles]
        )

        result = []
        for r in roles:
            perm_keys = (
                sorted(APPROVED_PERMISSION_KEYS)
                if is_global_super_admin_role(r)
                else sorted(
                    key for key in permissions_by_role.get(r.id, []) if key in ADMIN_PERMISSIONS
                )
            )
            if r.id in default_ids or r.name in default_ids:
                role_type = "default"
            elif getattr(r, "is_system_role", False):
                role_type = "system"
            else:
                role_type = "custom"
            result.append(
                role_to_dict(r, perm_keys, str(getattr(r, "created_at", "2026-08-05")))
                | {"type": role_type}
            )
        return result

    async def count_roles(
        self, db: AsyncSession, search: str | None = None, org_id: str | None = None
    ) -> int:
        return await self.repository.count_roles(db, search, org_id=org_id)

    # --- Create role ---
    async def create_role(self, db: AsyncSession, payload: RoleCreate, current_user: User) -> dict:
        org_id = self._current_org_id(current_user)
        try:
            permission_keys, permissions = await self._validated_permissions(
                db, payload.permissions
            )
            role = await self.repository.create_role(
                db,
                name=payload.name,
                description=payload.description or "",
                organization_id=org_id,
            )
            await db.flush()
            for permission in permissions:
                await self.repository.add_role_permission(db, role.id, permission.id)
            self._audit(
                db,
                current_user=current_user,
                action="ROLE_CREATED",
                target_type="role",
                target_id=role.id,
                after={
                    "name": role.name,
                    "description": role.description or "",
                    "permissions": permission_keys,
                },
            )
            await self._commit(db, "Failed to create role", status_code=409)
            await db.refresh(role)
        except IntegrityError as exc:
            await db.rollback()
            raise APIException(
                status_code=409, message="A role with this name already exists"
            ) from exc
        except APIException:
            await db.rollback()
            raise
        except Exception:
            await db.rollback()
            raise

        return role_to_dict(
            role, permission_keys, str(getattr(role, "created_at", datetime.now().isoformat()))
        ) | {"type": "custom"}

    # --- Get permission matrix ---
    async def get_permission_matrix(self, db: AsyncSession) -> list[dict]:
        perms = await self.repository.get_permission_matrix(db)
        return [
            {
                "id": p.id,
                "key": p.key,
                "name": p.name or p.key.replace(":", " ").title(),
                "category": p.category or "General",
                "description": p.description or "",
            }
            for p in perms
            if p.key in ADMIN_PERMISSIONS
        ]

    # --- Create permission ---
    async def create_permission(self, db: AsyncSession, payload: PermissionCreate) -> dict:
        validate_permission_keys([payload.key], allow_platform=True)
        p = await self.repository.create_permission(
            db,
            data={
                "key": payload.key,
                "name": payload.name,
                "category": payload.category or "General",
                "description": payload.description or payload.name,
            },
        )
        try:
            await db.commit()
            await db.refresh(p)
        except Exception as exc:
            await db.rollback()
            raise APIException(
                status_code=409, message="Permission could not be saved; its key may already exist"
            ) from exc
        return {
            "id": p.id,
            "key": p.key,
            "name": p.name,
            "category": p.category,
            "description": p.description or "",
        }

    # --- Import permissions batch ---
    async def import_permissions_batch(
        self, db: AsyncSession, payload: list[PermissionCreate]
    ) -> dict:
        validate_permission_keys([item.key for item in payload], allow_platform=True)
        try:
            count = 0
            for item in payload:
                await self.repository.create_permission(
                    db,
                    data={
                        "key": item.key,
                        "name": item.name,
                        "category": item.category or "General",
                        "description": item.description or item.name,
                    },
                )
                count += 1
            await db.commit()
            return {
                "message": f"Successfully imported {count} permissions from JSON.",
                "status": "success",
            }
        except Exception as exc:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Permission import failed. No permissions were imported.",
            ) from exc

    # --- System roles ---
    async def list_system_roles(self, db: AsyncSession, current_user: User) -> list[dict]:
        organization_id = self._current_org_id(current_user)
        roles = list(await self.repository.get_system_roles(db, organization_id))
        permissions_by_role = await self.repository.get_permission_keys_by_role_ids(
            db, [role.id for role in roles]
        )
        return [
            role_to_dict(
                role,
                sorted(
                    key for key in permissions_by_role.get(role.id, []) if key in ADMIN_PERMISSIONS
                ),
                str(getattr(role, "created_at", datetime.now(UTC))),
            )
            | {"description": role.description or "System Role"}
            for role in roles
        ]

    # --- List assignable roles ---
    async def list_assignable_roles(
        self, db: AsyncSession, search: str | None = None, org_id: str | None = None
    ) -> list[dict]:
        """Roles that may be assigned to users (Create/Invite/Edit/Assign flows).

        The platform ``super_admin`` role is intentionally excluded here so it can
        never be offered (or picked) as an assignable target — it remains visible
        in the Roles & Permissions listing via ``list_roles``. Assignment is still
        independently enforced server-side by ``ensure_can_assign_role``.
        """
        roles = await self.list_roles(db, search, org_id=org_id)
        return [r for r in roles if not is_super_admin_role_name(r.get("name", ""))]

    # --- Set multiple default roles ---
    async def set_multiple_default_roles(
        self, db: AsyncSession, role_ids: list[str], current_user: User
    ) -> dict:
        try:
            organization_id = self._current_org_id(current_user)
            role_ids = list(dict.fromkeys(role_ids))
            await self.repository.lock_default_roles(db, organization_id)
            before = sorted(await self._get_default_role_ids(db, organization_id))
            for role_id in sorted(role_ids):
                role = await self.repository.get_role_for_update(db, role_id, organization_id)
                if not role:
                    raise NotFoundError(message=f"Role '{role_id}' not found")
                self._ensure_assignable_role_ownership(role, current_user)
            new_val = json.dumps(role_ids)
            await self.repository.upsert_setting(
                db,
                self._role_setting_key("default_registration_roles", organization_id),
                new_val,
                "Default registration roles JSON array",
            )
            await self.repository.upsert_setting(
                db,
                self._role_setting_key("default_registration_role", organization_id),
                role_ids[0] if role_ids else "",
                "Legacy default role",
            )
            self._audit(
                db,
                current_user=current_user,
                action="ROLE_DEFAULTS_CHANGED",
                target_type="organization",
                target_id=organization_id,
                before={"role_ids": before},
                after={"role_ids": role_ids},
            )
            await db.commit()
            return {
                "message": f"Successfully updated default registration roles ({len(role_ids)} selected)",
                "status": "success",
            }
        except APIException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            raise APIException(status_code=status.HTTP_400_BAD_REQUEST, message=str(e)) from e

    # --- Get default role ---
    async def get_default_role(self, db: AsyncSession, current_user: User) -> dict:
        organization_id = self._current_org_id(current_user)
        primary = await self.repository.get_setting(
            db, self._role_setting_key("default_registration_role", organization_id)
        )
        ordered_default_ids = await self._get_ordered_default_role_ids(db, organization_id)
        default_ids = set(ordered_default_ids)
        primary_id = primary.value.strip() if primary and primary.value else None
        selected_id = (
            primary_id if primary_id in default_ids else next(iter(ordered_default_ids), None)
        )
        role_obj = (
            await self.repository.get_role_by_id_or_name(
                db, selected_id, organization_id=organization_id
            )
            if selected_id
            else None
        )
        if not role_obj:
            raise APIException(
                status_code=status.HTTP_409_CONFLICT,
                code="DEFAULT_ROLE_NOT_CONFIGURED",
                message="The organization has no valid default role",
            )
        self._ensure_assignable_role_ownership(role_obj, current_user)
        assigned = await self.repository.get_role_permissions(db, role_obj.id)
        perm_keys = sorted(p.key for p in assigned if p.key in ADMIN_PERMISSIONS)
        return role_to_dict(role_obj, perm_keys, str(getattr(role_obj, "created_at", ""))) | {
            "description": role_obj.description or "Default Registration Role"
        }

    # --- Stub endpoints ---
    async def role_audit_logs(
        self, db: AsyncSession, current_user: User, *, page: int = 1, limit: int = 20
    ) -> list[dict]:
        organization_id = self._current_org_id(current_user)
        actions = {
            "ROLE_CREATED",
            "ROLE_UPDATED",
            "ROLE_DELETED",
            "ROLE_PERMISSIONS_CHANGED",
            "ROLE_ASSIGNED_TO_USER",
            "ROLE_PERMISSION_REMOVED",
            "ROLE_DEFAULTS_CHANGED",
        }
        logs = list(
            (
                await db.execute(
                    select(AuditLog)
                    .where(
                        AuditLog.organization_id == organization_id,
                        AuditLog.action.in_(actions),
                    )
                    .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
                    .offset((page - 1) * limit)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        result = []
        for log in logs:
            try:
                details = json.loads(log.details or "{}")
            except (TypeError, ValueError):
                details = {}
            before = details.get("before") or {}
            after = details.get("after") or {}
            role_name = (
                "Default registration roles"
                if log.action == "ROLE_DEFAULTS_CHANGED"
                else after.get("name")
                or after.get("role_name")
                or before.get("name")
                or details.get("target_id")
                or "Role"
            )
            result.append(
                {
                    "id": log.id,
                    "action": log.action,
                    "role_name": role_name,
                    "user": log.user_id or "system",
                    "timestamp": str(log.created_at),
                    "details": details,
                }
            )
        return result

    async def count_role_audit_logs(self, db: AsyncSession, current_user: User) -> int:
        organization_id = self._current_org_id(current_user)
        actions = {
            "ROLE_CREATED",
            "ROLE_UPDATED",
            "ROLE_DELETED",
            "ROLE_PERMISSIONS_CHANGED",
            "ROLE_ASSIGNED_TO_USER",
            "ROLE_PERMISSION_REMOVED",
            "ROLE_DEFAULTS_CHANGED",
        }
        result = await db.execute(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.organization_id == organization_id, AuditLog.action.in_(actions))
        )
        return int(result.scalar_one())

    async def export_roles(self) -> dict:
        raise APIException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            code="ROLE_EXPORT_UNAVAILABLE",
            message="Role export is not available",
        )

    async def import_roles(self) -> dict:
        raise APIException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            code="ROLE_IMPORT_UNAVAILABLE",
            message="Role import is not available",
        )

    async def _ensure_role_unassigned(self, db: AsyncSession, role: Role) -> None:
        references = await self.repository.get_role_reference_kinds(db, role)
        if references:
            raise APIException(
                status_code=status.HTTP_409_CONFLICT,
                code="ROLE_IN_USE",
                message=(
                    f"Role '{role.name}' is referenced by {', '.join(references)} "
                    "and cannot be deleted"
                ),
            )

    # --- Bulk delete ---
    async def bulk_delete_roles(self, db: AsyncSession, ids: list[str], current_user: User) -> dict:
        organization_id = self._current_org_id(current_user)
        await self.repository.lock_default_roles(db, organization_id)
        default_ids = await self._get_default_role_ids(db, organization_id)
        roles = []
        for role_id in sorted(set(ids)):
            role = await self.repository.get_role_for_update(db, role_id, organization_id)
            if role:
                self._ensure_mutable_role_ownership(role, current_user)
                roles.append(role)
        for role in roles:
            self._ensure_mutable_role(role)
        deleted_count = 0
        for role in roles:
            if role.id not in default_ids and role.name not in default_ids:
                await self._ensure_role_unassigned(db, role)
                self._audit(
                    db,
                    current_user=current_user,
                    action="ROLE_DELETED",
                    target_type="role",
                    target_id=role.id,
                    before={"name": role.name, "description": role.description or ""},
                )
                await self.repository.delete_role(db, role)
                deleted_count += 1
        await self._commit(db, "Failed to bulk delete roles")
        return {
            "affected_count": deleted_count,
            "message": f"Successfully deleted {deleted_count} non-default role(s)",
        }

    # --- Get user role ---
    async def get_user_role(self, db: AsyncSession, user_id: str, current_user: User) -> dict:
        role_obj = None
        u = await self.repository.get_user_by_id_or_email(db, user_id)
        if not u or u.organization_id != self._current_org_id(current_user):
            raise NotFoundError(message=f"User '{user_id}' not found")
        mapping = await self.repository.get_user_role_mapping(db, u.id)
        if mapping:
            role_obj = await self.repository.get_role_by_id_or_name(
                db, mapping.role_id, organization_id=self._current_org_id(current_user)
            )
        elif getattr(u, "role", None):
            role_obj = await self.repository.get_role_by_id_or_name(
                db, u.role, organization_id=self._current_org_id(current_user)
            )
        if role_obj:
            self._ensure_assignable_role_ownership(role_obj, current_user)
            perm_keys = await self._resolve_role_permission_keys(db, role_obj)
            return role_to_dict(
                role_obj, perm_keys, str(getattr(role_obj, "created_at", "2026-08-05"))
            ) | {"description": role_obj.description or "User assigned role"}
        raise NotFoundError(message=f"Role for user '{user_id}' not found")

    # --- Assign role to user ---
    async def assign_role_to_user(
        self, db: AsyncSession, user_id: str, role_id: str, current_user: User
    ) -> dict:
        u = await self.repository.get_user_by_id_or_email(db, user_id)
        if not u or u.organization_id != self._current_org_id(current_user):
            raise NotFoundError(message=f"User '{user_id}' not found")
        ensure_tenant_managed_user(u)
        r = await self.repository.get_role_by_id_or_name(
            db, role_id, organization_id=self._current_org_id(current_user)
        )
        if not r:
            raise NotFoundError(message=f"Role '{role_id}' not found")
        r = await self.repository.get_role_for_update(db, r.id, self._current_org_id(current_user))
        if not r:
            raise NotFoundError(message=f"Role '{role_id}' not found")
        self._ensure_assignable_role_ownership(r, current_user)
        # Platform identity can only be provisioned through the offline service.
        if is_super_admin_role(r):
            ensure_can_assign_role(
                actor_is_super_admin=await is_super_admin_user(db, current_user),
                target_is_super_admin=True,
            )
        from app.services.user_service import UserService

        await UserService()._ensure_not_last_admin(db, u, replacement_role_name=r.name)
        previous_mapping = await self.repository.get_user_role_mapping(db, u.id)
        previous_role = (
            previous_mapping.role_id if previous_mapping else (u.role or "").strip() or None
        )
        u.role = r.id
        await self.repository.replace_user_role(db, u.id, r.id)
        self._audit(
            db,
            current_user=current_user,
            action="ROLE_ASSIGNED_TO_USER",
            target_type="user",
            target_id=u.id,
            before={"role_id": previous_role},
            after={"role_id": r.id, "role_name": r.name},
        )
        await self._commit(db, "Failed to assign role")
        return {
            "message": f"Successfully assigned role '{r.name}' to user '{u.name}'",
            "status": "success",
        }

    # --- Check permission ---
    async def check_permission(
        self, db: AsyncSession, user_id: str, permission: str, current_user: User
    ) -> dict:
        """Fail-closed permission check for a user against a single permission key.

        The decision uses the tenant-scoped role's assigned approved
        permissions. Unknown roles, users, permissions, or resolution failures
        yield ``allowed=False``.
        """
        try:
            u = await self.repository.get_user_by_id_or_email(db, user_id)
            if not u or u.organization_id != self._current_org_id(current_user):
                raise NotFoundError(message=f"User '{user_id}' not found")
            normalized = validate_permission_keys([permission])
            if not normalized:
                return {"user_id": user_id, "permission": permission, "allowed": False}
            effective = await self.authorization_service.get_user_permissions(db, u)
            return {
                "user_id": user_id,
                "permission": normalized[0],
                "allowed": normalized[0] in effective,
            }
        except Exception:
            return {"user_id": user_id, "permission": permission, "allowed": False}

    # --- Get role by id ---
    async def get_role(self, db: AsyncSession, role_id: str, current_user: User) -> dict:
        r = await self.repository.get_role(db, role_id)
        if not r:
            raise NotFoundError(message=f"Role '{role_id}' not found")
        self._ensure_assignable_role_ownership(r, current_user)
        perm_keys = await self._get_permission_keys_for_role(db, r)
        return role_to_dict(r, perm_keys, str(getattr(r, "created_at", "2026-08-05")))

    # --- Update role ---
    async def update_role(
        self, db: AsyncSession, role_id: str, payload: RoleUpdate, current_user: User
    ) -> dict:
        r = await self.repository.get_role(db, role_id)
        if not r:
            raise NotFoundError(message=f"Role '{role_id}' not found")
        self._ensure_mutable_role_ownership(r, current_user)
        r = await self.repository.get_role_for_update(db, r.id, self._current_org_id(current_user))
        if not r:
            raise NotFoundError(message=f"Role '{role_id}' not found")
        self._ensure_mutable_role_ownership(r, current_user)
        try:
            permission_keys = None
            permissions = []
            if payload.permissions is not None:
                permission_keys, permissions = await self._validated_permissions(
                    db, payload.permissions
                )
            before_permissions = [
                permission.key
                for permission in await self.repository.get_role_permissions(db, r.id)
                if permission.key
            ]
            before = {
                "name": r.name,
                "description": r.description or "",
                "permissions": sorted(before_permissions),
            }
            if payload.name:
                self.repository.validate_custom_role_name(payload.name)
                normalized_name = payload.name.strip()
                if normalized_name != r.name:
                    references = await self.repository.get_role_reference_kinds(db, r)
                    if references:
                        raise APIException(
                            status_code=status.HTTP_409_CONFLICT,
                            code="ROLE_IN_USE",
                            message=(
                                f"Role '{r.name}' is referenced by {', '.join(references)} "
                                "and cannot be renamed"
                            ),
                        )
                    r.name = normalized_name
            if payload.description is not None:
                r.description = payload.description
            if payload.permissions is not None:
                existing = await self.repository.get_role_permission_ids(db, role_id)
                for item in existing:
                    await self.repository.delete_role_permission(db, item)
                # Flush deletes before reusing unique role/permission pairs.
                # This remains inside the surrounding transaction.
                await db.flush()
                for p in permissions:
                    await self.repository.add_role_permission(db, role_id, p.id)
            final_permissions = (
                permission_keys if permission_keys is not None else before_permissions
            )
            self._audit(
                db,
                current_user=current_user,
                action="ROLE_UPDATED",
                target_type="role",
                target_id=r.id,
                before=before,
                after={
                    "name": r.name,
                    "description": r.description or "",
                    "permissions": sorted(final_permissions),
                },
            )
            await self._commit(db, "Failed to update role", status_code=409)
            await db.refresh(r)
            return role_to_dict(
                r,
                sorted(final_permissions),
                str(getattr(r, "created_at", "2026-08-05")),
            )
        except IntegrityError as exc:
            await db.rollback()
            raise APIException(
                status_code=409, message="A role with this name already exists"
            ) from exc
        except APIException:
            await db.rollback()
            raise
        except Exception:
            await db.rollback()
            raise

    # --- Delete role ---
    async def delete_role(self, db: AsyncSession, role_id: str, current_user: User) -> dict:
        organization_id = self._current_org_id(current_user)
        r = await self.repository.get_role_by_id_or_name(
            db, role_id, organization_id=organization_id
        )
        if not r:
            raise NotFoundError(message=f"Role '{role_id}' not found")
        await self.repository.lock_default_roles(db, organization_id)
        r = await self.repository.get_role_for_update(db, r.id, organization_id)
        if not r:
            raise NotFoundError(message=f"Role '{role_id}' not found")
        default_ids = await self._get_default_role_ids(db, self._current_org_id(current_user))
        if r.id in default_ids or r.name in default_ids:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=f"Cannot delete default registration role '{r.name}'. Remove default status first.",
            )
        self._ensure_mutable_role_ownership(r, current_user)
        await self._ensure_role_unassigned(db, r)
        self._audit(
            db,
            current_user=current_user,
            action="ROLE_DELETED",
            target_type="role",
            target_id=r.id,
            before={"name": r.name, "description": r.description or ""},
        )
        await self.repository.delete_role(db, r)
        await self._commit(db, "Failed to delete role")
        return {"message": f"Role '{r.name}' deleted successfully", "status": "success"}

    # --- Clone role ---
    async def clone_role(
        self, db: AsyncSession, role_id: str, new_name: str, current_user: User
    ) -> dict:
        organization_id = self._current_org_id(current_user)
        orig = await self.repository.get_role_for_update(db, role_id, organization_id)
        if not orig:
            raise NotFoundError(message=f"Role '{role_id}' not found")
        self._ensure_assignable_role_ownership(orig, current_user)
        orig_perms = await self.repository.get_role_permissions(db, role_id)
        approved_permissions = [
            permission for permission in orig_perms if permission.key in ADMIN_PERMISSIONS
        ]
        try:
            r = await self.repository.create_role(
                db,
                name=new_name,
                description=f"Cloned from {orig.name}",
                organization_id=organization_id,
            )
            await db.flush()
            for permission in approved_permissions:
                await self.repository.add_role_permission(db, r.id, permission.id)
            self._audit(
                db,
                current_user=current_user,
                action="ROLE_CREATED",
                target_type="role",
                target_id=r.id,
                after={
                    "name": r.name,
                    "description": r.description,
                    "permissions": sorted(p.key for p in approved_permissions),
                    "cloned_from": orig.id,
                },
            )
            await self._commit(db, "Failed to clone role", status_code=409)
            await db.refresh(r)
        except APIException:
            await db.rollback()
            raise
        except Exception:
            await db.rollback()
            raise
        return role_to_dict(
            r,
            sorted(permission.key for permission in approved_permissions),
            str(getattr(r, "created_at", datetime.now().isoformat())),
        )

    # --- Assign permissions to role ---
    async def assign_permissions(
        self, db: AsyncSession, role_id: str, permissions: list[str], current_user: User
    ) -> dict:
        role = await self.repository.get_role(db, role_id)
        if not role:
            raise NotFoundError(message=f"Role '{role_id}' not found")
        self._ensure_mutable_role_ownership(role, current_user)
        try:
            role = await self.repository.get_role_for_update(
                db, role.id, self._current_org_id(current_user)
            )
            if not role:
                raise NotFoundError(message=f"Role '{role_id}' not found")
            self._ensure_mutable_role_ownership(role, current_user)
            permission_keys, permission_rows = await self._validated_permissions(db, permissions)
            before = sorted(
                permission.key
                for permission in await self.repository.get_role_permissions(db, role_id)
                if permission.key
            )
            existing = await self.repository.get_role_permission_ids(db, role_id)
            for item in existing:
                await self.repository.delete_role_permission(db, item)
            await db.flush()
            for permission in permission_rows:
                await self.repository.add_role_permission(db, role_id, permission.id)
            self._audit(
                db,
                current_user=current_user,
                action="ROLE_PERMISSIONS_CHANGED",
                target_type="role",
                target_id=role.id,
                before={"permissions": before},
                after={"permissions": permission_keys},
            )
            await self._commit(db, "Failed to assign role permissions")
        except APIException:
            await db.rollback()
            raise
        except Exception:
            await db.rollback()
            raise
        return {"message": f"Updated permissions for role {role_id}", "status": "success"}

    # --- Remove permission from role ---
    async def remove_permission(
        self, db: AsyncSession, role_id: str, perm_id: str, current_user: User
    ) -> dict:
        role = await self.repository.get_role(db, role_id)
        if not role:
            raise NotFoundError(message=f"Role '{role_id}' not found")
        self._ensure_mutable_role_ownership(role, current_user)
        try:
            role = await self.repository.get_role_for_update(
                db, role.id, self._current_org_id(current_user)
            )
            if not role:
                raise NotFoundError(message=f"Role '{role_id}' not found")
            self._ensure_mutable_role_ownership(role, current_user)
            target_perm = await self.repository.get_permission_by_id_or_key(db, perm_id)
            if not target_perm or target_perm.key not in ADMIN_PERMISSIONS:
                raise NotFoundError(message=f"Permission '{perm_id}' not found")
            removed = await self.repository.remove_permission_from_role(db, role_id, target_perm.id)
            if not removed:
                raise NotFoundError(message=f"Permission '{perm_id}' is not assigned to this role")
            self._audit(
                db,
                current_user=current_user,
                action="ROLE_PERMISSION_REMOVED",
                target_type="role",
                target_id=role.id,
                before={"removed_permission": target_perm.key},
                after=None,
            )
            await self._commit(db, "Failed to remove permission")
            return {
                "message": f"Permission '{perm_id}' removed from role",
                "status": "success",
            }
        except APIException:
            await db.rollback()
            raise
        except Exception:
            await db.rollback()
            raise

    # --- Get role users ---
    async def get_role_users(
        self,
        db: AsyncSession,
        role_id: str,
        current_user: User,
        *,
        page: int = 1,
        limit: int = 15,
    ) -> list[dict]:
        r = await self.repository.get_role_by_id_or_name(
            db, role_id, organization_id=self._current_org_id(current_user)
        )
        if not r:
            raise NotFoundError(message=f"Role '{role_id}' not found")
        self._ensure_assignable_role_ownership(r, current_user)
        target_role_id = r.id
        target_role_name = r.name
        org_id = self._current_org_id(current_user)
        matched = await self.repository.get_effective_users_by_role(
            db,
            role_id=target_role_id,
            role_name=target_role_name,
            organization_id=org_id,
            page=page,
            limit=limit,
        )
        if matched:
            return [
                {
                    "id": u.id,
                    "name": u.name,
                    "email": u.email,
                    "role": target_role_name,
                    "created_at": str(getattr(u, "created_at", "2026-08-05")),
                }
                for u in matched
            ]
        return []

    async def count_role_users(self, db: AsyncSession, role_id: str, current_user: User) -> int:
        role = await self.repository.get_role_by_id_or_name(
            db, role_id, organization_id=self._current_org_id(current_user)
        )
        if not role:
            raise NotFoundError(message=f"Role '{role_id}' not found")
        self._ensure_assignable_role_ownership(role, current_user)
        return await self.repository.count_effective_users_by_role(
            db,
            role_id=role.id,
            role_name=role.name,
            organization_id=self._current_org_id(current_user),
        )

    # --- Set default role ---
    async def set_default_role(self, db: AsyncSession, role_id: str, current_user: User) -> dict:
        organization_id = self._current_org_id(current_user)
        await self.repository.lock_default_roles(db, organization_id)
        r = await self.repository.get_role_by_id_or_name(
            db, role_id, organization_id=organization_id
        )
        if not r:
            raise NotFoundError(message=f"Role '{role_id}' not found")
        r = await self.repository.get_role_for_update(db, r.id, organization_id)
        if not r:
            raise NotFoundError(message=f"Role '{role_id}' not found")
        self._ensure_assignable_role_ownership(r, current_user)
        roles_setting_key = self._role_setting_key("default_registration_roles", organization_id)
        role_setting_key = self._role_setting_key("default_registration_role", organization_id)
        setting = await self.repository.get_setting(db, roles_setting_key)
        current_defaults = []
        if setting and setting.value:
            try:
                current_defaults = json.loads(setting.value)
                if not isinstance(current_defaults, list):
                    current_defaults = [str(current_defaults)]
            except Exception:
                current_defaults = [s.strip() for s in setting.value.split(",") if s.strip()]
        before_defaults = list(current_defaults)
        target_id = r.id
        if target_id in current_defaults:
            current_defaults.remove(target_id)
            msg = f"Role '{r.name}' removed from default registration roles"
        else:
            current_defaults.append(target_id)
            msg = f"Role '{r.name}' added as default for new registrations"
        new_val = json.dumps(current_defaults)
        await self.repository.upsert_setting(
            db, roles_setting_key, new_val, "Default registration roles JSON array"
        )
        await self.repository.upsert_setting(
            db,
            role_setting_key,
            current_defaults[0] if current_defaults else "",
            "Legacy single default role",
        )
        self._audit(
            db,
            current_user=current_user,
            action="ROLE_DEFAULTS_CHANGED",
            target_type="role",
            target_id=r.id,
            before={"role_ids": before_defaults},
            after={"role_ids": current_defaults},
        )
        await self._commit(db, "Failed to update default roles")
        return {"message": msg, "status": "success"}


role_service = RoleService()
