import json
from datetime import UTC, datetime

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIException, ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.core.permissions import (
    ensure_can_assign_role,
    is_super_admin_role,
    is_super_admin_role_name,
    is_super_admin_user,
)
from app.models import Role, User, UserRole
from app.repositories.role_repository import RoleRepository
from app.schemas.crm_schemas import PermissionCreate, RoleCreate, RoleUpdate

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

    def __init__(self, repository: RoleRepository | None = None) -> None:
        self.repository = repository or RoleRepository()

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
        try:
            setting = await self.repository.get_setting(
                db, self._role_setting_key("default_registration_roles", organization_id)
            )
            if setting and setting.value:
                try:
                    val = json.loads(setting.value)
                    if isinstance(val, list):
                        return set(val)
                except Exception:
                    return {s.strip() for s in setting.value.split(",") if s.strip()}
            legacy = await self.repository.get_setting(
                db, self._role_setting_key("default_registration_role", organization_id)
            )
            if legacy and legacy.value:
                return {legacy.value}
        except Exception:
            logger.warning("Failed to resolve configured default role IDs", exc_info=True)
        return set()

    async def _resolve_role_permission_keys(
        self, db: AsyncSession, role: Role, all_db_keys: list[str]
    ) -> list[str]:
        """Resolve the effective permission keys for a role strictly from its assigned
        role_permissions (no role-name based shortcuts and no implicit expansion).

        Only the ``super_admin`` role (identified by name) is treated as
        unrestricted and resolves to every known permission key. Every other
        role — including Admin and other system roles — resolves to exactly the
        keys explicitly assigned via role_permissions. Holding the
        ``super_admin:manage`` permission or the ``all`` sentinel does NOT
        implicitly expand a non-super_admin role.
        """
        if is_super_admin_role(role):
            return all_db_keys
        assigned = await self.repository.get_role_permissions(db, role.id)
        return [p.key for p in assigned if p.key] if assigned else []

    async def _get_permission_keys_for_role(
        self, db: AsyncSession, role: Role, all_db_keys: list[str]
    ) -> list[str]:
        return await self._resolve_role_permission_keys(db, role, all_db_keys)

    @staticmethod
    def _ensure_mutable_role(role: Role) -> None:
        """Deny mutation of system roles. Enforced server-side regardless of caller permissions."""
        if getattr(role, "is_system_role", False):
            raise ForbiddenError(message="System roles cannot be modified or deleted.")

    @staticmethod
    def _current_org_id(current_user: User) -> str:
        org_id = getattr(current_user, "organization_id", None)
        if not org_id:
            raise ForbiddenError(message="Authenticated user has no current organization")
        return org_id

    @classmethod
    def _ensure_assignable_role_ownership(cls, role: Role, current_user: User) -> None:
        org_id = cls._current_org_id(current_user)
        if role.organization_id is not None and role.organization_id != org_id:
            raise NotFoundError(message=f"Role '{role.id}' not found")

    @classmethod
    def _ensure_mutable_role_ownership(cls, role: Role, current_user: User) -> None:
        cls._ensure_mutable_role(role)
        org_id = cls._current_org_id(current_user)
        if role.organization_id != org_id:
            raise NotFoundError(message=f"Role '{role.id}' not found")

    # --- List roles ---
    async def list_roles(
        self, db: AsyncSession, search: str | None = None, org_id: str | None = None
    ) -> list[dict]:
        default_ids = await self._get_default_role_ids(db, org_id)
        all_db_keys = await self.repository.get_permission_keys(db)
        roles = await self.repository.list_roles(db, search, org_id=org_id)

        result = []
        for r in roles:
            perm_keys = await self._get_permission_keys_for_role(db, r, all_db_keys)
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

    # --- Create role ---
    async def create_role(
        self, db: AsyncSession, payload: RoleCreate, current_user: User
    ) -> dict:
        org_id = self._current_org_id(current_user)
        role = await self.repository.create_role(
            db,
            name=payload.name,
            description=payload.description or "",
            organization_id=org_id,
        )
        try:
            await db.commit()
            await db.refresh(role)
        except Exception as e:
            await db.rollback()
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST, message=f"Failed to create role: {str(e)}"
            ) from e

        saved_permissions = []
        if payload.permissions:
            found_perms = await self.repository.get_permissions_by_keys_or_ids(
                db, payload.permissions
            )
            found_keys_set = {p.key for p in found_perms if p.key} | {
                p.id for p in found_perms if p.id
            }
            for p in found_perms:
                await self.repository.add_role_permission(db, role.id, p.id)
            missing_keys = set(payload.permissions) - found_keys_set
            for key_str in missing_keys:
                if key_str and isinstance(key_str, str):
                    category = key_str.split(":")[0].capitalize() if ":" in key_str else "General"
                    name = key_str.replace(":", " ").capitalize()
                    new_perm = await self.repository.create_permission(
                        db,
                        data={
                            "key": key_str,
                            "name": name,
                            "category": category,
                            "description": name,
                        },
                    )
                    await db.flush()
                    await self.repository.add_role_permission(db, role.id, new_perm.id)
            await self._commit(db, "Failed to save role permissions")
            saved_permissions = payload.permissions

        return role_to_dict(
            role, saved_permissions, str(getattr(role, "created_at", datetime.now().isoformat()))
        ) | {"type": "custom"}

    # --- Get permission matrix ---
    async def get_permission_matrix(self, db: AsyncSession) -> list[dict]:
        try:
            await self.repository.seed_permissions(db, ALL_STANDARD_PERMISSIONS)
        except Exception:
            await db.rollback()
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
            if p.key and p.key != "all" and getattr(p, "category", "").lower() != "all"
        ]

    # --- Create permission ---
    async def create_permission(self, db: AsyncSession, payload: PermissionCreate) -> dict:
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
        except Exception:
            await db.rollback()
            return {
                "id": f"perm-{int(datetime.now().timestamp())}",
                "key": payload.key,
                "name": payload.name,
                "category": payload.category or "General",
                "description": payload.description or "",
            }
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
    async def list_system_roles(
        self, db: AsyncSession, current_user: User
    ) -> list[dict]:
        organization_id = self._current_org_id(current_user)
        all_db_keys = await self.repository.get_permission_keys(db)
        try:
            setting = await self.repository.get_setting(
                db, self._role_setting_key("default_registration_role", organization_id)
            )
            default_role_id = setting.value if setting else None
            if default_role_id:
                r = await self.repository.get_role_by_id_or_name(db, default_role_id)
                if r:
                    self._ensure_assignable_role_ownership(r, current_user)
                    perm_keys = await self._resolve_role_permission_keys(db, r, all_db_keys)
                    return [
                        role_to_dict(r, perm_keys, str(getattr(r, "created_at", datetime.now(UTC))))
                        | {"description": r.description or "Registration Default Role"}
                    ]
            roles = await self.repository.get_system_roles(db, organization_id)
            if roles:
                result = []
                for r in roles:
                    perm_keys = await self._resolve_role_permission_keys(db, r, all_db_keys)
                    result.append(
                        role_to_dict(r, perm_keys, str(getattr(r, "created_at", datetime.now(UTC))))
                        | {"description": r.description or "System Role"}
                    )
                return result
        except Exception:
            logger.warning(
                "Failed to load system roles; using compatibility fallback", exc_info=True
            )
        return [
            {
                "id": "sys-manager",
                "name": "manager",
                "description": "Registration Default Role",
                "permissions": ["dashboard:read", "users:read", "leads:read"],
                "is_system_role": True,
                "created_at": datetime.now(UTC).isoformat(),
            }
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
            for role_id in role_ids:
                role = await self.repository.get_role(db, role_id)
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
            if role_ids:
                await self.repository.upsert_setting(
                    db,
                    self._role_setting_key("default_registration_role", organization_id),
                    role_ids[0],
                    "Legacy default role",
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
        fallback = {
            "id": "sys-manager",
            "name": "manager",
            "description": "Default role",
            "permissions": ["dashboard:read", "users:read"],
            "is_system_role": True,
            "created_at": "2026-08-05",
        }
        try:
            setting = await self.repository.get_setting(
                db, self._role_setting_key("default_registration_role", organization_id)
            )
            role_obj = None
            if setting and setting.value:
                role_obj = await self.repository.get_role_by_id_or_name(db, setting.value)
            if not role_obj:
                res = await db.execute(
                    select(Role)
                    .where(
                        Role.is_system_role.is_(True),
                        (Role.organization_id.is_(None))
                        | (Role.organization_id == organization_id),
                    )
                    .limit(1)
                )
                role_obj = res.scalars().first()
            if not role_obj:
                roles = await self.repository.list_roles(db, org_id=organization_id)
                role_obj = next(iter(roles), None)
            if role_obj:
                self._ensure_assignable_role_ownership(role_obj, current_user)
                assigned = await self.repository.get_role_permissions(db, role_obj.id)
                perm_keys = (
                    [p.key for p in assigned if p.key]
                    if assigned
                    else ["dashboard:read", "users:read"]
                )
                return role_to_dict(
                    role_obj, perm_keys, str(getattr(role_obj, "created_at", "2026-08-05"))
                ) | {"description": role_obj.description or "Default Registration Role"}
        except Exception:
            return fallback
        return fallback

    # --- Stub endpoints ---
    async def role_audit_logs(self) -> list[dict]:
        return [
            {
                "id": "aud-1",
                "action": "Created Role",
                "role_name": "Regional Director",
                "user": "Admin User",
                "timestamp": "2026-08-04T10:15:00Z",
            },
            {
                "id": "aud-2",
                "action": "Updated Permissions",
                "role_name": "Sales Manager",
                "user": "Admin User",
                "timestamp": "2026-08-05T11:20:00Z",
            },
        ]

    async def export_roles(self) -> dict:
        return {"download_url": "https://api.crm.com/exports/roles_permissions_schema.json"}

    async def import_roles(self) -> dict:
        return {"message": "Role definitions JSON imported successfully", "status": "success"}

    # --- Bulk delete ---
    async def bulk_delete_roles(
        self, db: AsyncSession, ids: list[str], current_user: User
    ) -> dict:
        default_ids = await self._get_default_role_ids(
            db, self._current_org_id(current_user)
        )
        roles = []
        for role_id in ids:
            role = await self.repository.get_role(db, role_id)
            if role:
                self._ensure_mutable_role_ownership(role, current_user)
                roles.append(role)
        for role in roles:
            self._ensure_mutable_role(role)
        deleted_count = 0
        for role in roles:
            if role.id not in default_ids and role.name not in default_ids:
                await self.repository.delete_role(db, role)
                deleted_count += 1
        await self._commit(db, "Failed to bulk delete roles")
        return {
            "affected_count": deleted_count,
            "message": f"Successfully deleted {deleted_count} non-default role(s)",
        }

    # --- Get user role ---
    async def get_user_role(
        self, db: AsyncSession, user_id: str, current_user: User
    ) -> dict:
        all_db_keys = await self.repository.get_permission_keys(db)
        role_obj = None
        u = await self.repository.get_user_by_id_or_email(db, user_id)
        if not u or u.organization_id != self._current_org_id(current_user):
            raise NotFoundError(message=f"User '{user_id}' not found")
        if getattr(u, "role", None):
            role_obj = await self.repository.get_role_by_id_or_name(db, u.role)
        if not role_obj:
            mapping = await self.repository.get_user_role_mapping(db, u.id)
            if mapping:
                role_obj = await self.repository.get_role(db, mapping.role_id)
        if role_obj:
            self._ensure_assignable_role_ownership(role_obj, current_user)
            perm_keys = await self._resolve_role_permission_keys(db, role_obj, all_db_keys)
            return role_to_dict(
                role_obj, perm_keys, str(getattr(role_obj, "created_at", "2026-08-05"))
            ) | {"description": role_obj.description or "User assigned role"}
        raise NotFoundError(message=f"Role for user '{user_id}' not found")

    # --- Assign role to user ---
    async def assign_role_to_user(
        self, db: AsyncSession, user_id: str, role_id: str, current_user: User
    ) -> dict:
        u = await self.repository.get_user_by_id_or_email(db, user_id)
        r = await self.repository.get_role_by_id_or_name(db, role_id)
        if not u or u.organization_id != self._current_org_id(current_user):
            raise NotFoundError(message=f"User '{user_id}' not found")
        if not r:
            raise NotFoundError(message=f"Role '{role_id}' not found")
        self._ensure_assignable_role_ownership(r, current_user)
        # The super_admin role may only be assigned by a super_admin actor (403 otherwise).
        if is_super_admin_role(r):
            ensure_can_assign_role(
                actor_is_super_admin=await is_super_admin_user(db, current_user),
                target_is_super_admin=True,
            )
        u.role = r.id
        entry = await self.repository.get_user_role_mapping(db, u.id)
        if entry:
            entry.role_id = r.id
        else:
            db.add(UserRole(user_id=u.id, role_id=r.id))
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

        The decision is based exclusively on the resolved role's assigned
        permissions: unrestricted access is granted only to the ``super_admin``
        role (identified by name). Every other role — including Admin and other
        system roles — must explicitly include ``permission`` in its assigned
        keys; holding ``super_admin:manage`` or the ``all`` sentinel does NOT
        grant implicit access. An unknown role, an unknown user, or any
        resolution error yields ``allowed=False``.
        """
        try:
            u = await self.repository.get_user_by_id_or_email(db, user_id)
            if not u or u.organization_id != self._current_org_id(current_user):
                raise NotFoundError(message=f"User '{user_id}' not found")
            user_role_id = None
            if u and getattr(u, "role", None):
                user_role_id = u.role
            if not user_role_id and u:
                entry = await self.repository.get_user_role_mapping(db, u.id)
                if entry:
                    user_role_id = entry.role_id
            if not user_role_id:
                user_role_id = user_id
            role_obj = await self.repository.get_role_by_id_or_name(db, user_role_id)

            allowed = False
            if role_obj:
                self._ensure_assignable_role_ownership(role_obj, current_user)
                if is_super_admin_role(role_obj):
                    allowed = True
                else:
                    assigned = await self.repository.get_role_permissions(db, role_obj.id)
                    perm_keys = [p.key for p in assigned if p.key] if assigned else []
                    allowed = permission in perm_keys
            return {"user_id": user_id, "permission": permission, "allowed": allowed}
        except Exception:
            return {"user_id": user_id, "permission": permission, "allowed": False}

    # --- Get role by id ---
    async def get_role(self, db: AsyncSession, role_id: str, current_user: User) -> dict:
        r = await self.repository.get_role(db, role_id)
        if not r:
            raise NotFoundError(message=f"Role '{role_id}' not found")
        self._ensure_assignable_role_ownership(r, current_user)
        all_db_keys = await self.repository.get_permission_keys(db)
        perm_keys = await self._get_permission_keys_for_role(db, r, all_db_keys)
        return role_to_dict(r, perm_keys, str(getattr(r, "created_at", "2026-08-05")))

    # --- Update role ---
    async def update_role(
        self, db: AsyncSession, role_id: str, payload: RoleUpdate, current_user: User
    ) -> dict:
        r = await self.repository.get_role(db, role_id)
        if not r:
            raise NotFoundError(message=f"Role '{role_id}' not found")
        self._ensure_mutable_role_ownership(r, current_user)
        try:
            if payload.name:
                r.name = payload.name
            if payload.description:
                r.description = payload.description
            await db.commit()
            await db.refresh(r)
            if payload.permissions is not None:
                existing = await self.repository.get_role_permission_ids(db, role_id)
                for item in existing:
                    await self.repository.delete_role_permission(db, item)
                found_perms = await self.repository.get_permissions_by_keys_or_ids(
                    db, payload.permissions
                )
                for p in found_perms:
                    await self.repository.add_role_permission(db, role_id, p.id)
                await self._commit(db, "Failed to update role permissions")
            return role_to_dict(
                r,
                payload.permissions if payload.permissions is not None else [],
                str(getattr(r, "created_at", "2026-08-05")),
            )
        except Exception as e:
            await db.rollback()
            raise APIException(status_code=status.HTTP_400_BAD_REQUEST, message=str(e)) from e

    # --- Delete role ---
    async def delete_role(self, db: AsyncSession, role_id: str, current_user: User) -> dict:
        r = await self.repository.get_role_by_id_or_name(db, role_id)
        if not r:
            raise NotFoundError(message=f"Role '{role_id}' not found")
        default_ids = await self._get_default_role_ids(
            db, self._current_org_id(current_user)
        )
        if r.id in default_ids or r.name in default_ids:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                message=f"Cannot delete default registration role '{r.name}'. Remove default status first.",
            )
        self._ensure_mutable_role_ownership(r, current_user)
        await self.repository.delete_role(db, r)
        await self._commit(db, "Failed to delete role")
        return {"message": f"Role '{r.name}' deleted successfully", "status": "success"}

    # --- Clone role ---
    async def clone_role(
        self, db: AsyncSession, role_id: str, new_name: str, current_user: User
    ) -> dict:
        orig = await self.repository.get_role(db, role_id)
        if not orig:
            raise NotFoundError(message=f"Role '{role_id}' not found")
        self._ensure_assignable_role_ownership(orig, current_user)
        r = await self.repository.create_role(
            db,
            name=new_name,
            description=f"Cloned from {orig.name}",
            organization_id=self._current_org_id(current_user),
        )
        await self._commit(db, "Failed to clone role")
        await db.refresh(r)
        orig_perms = await self.repository.get_role_permissions(db, role_id)
        for op in orig_perms:
            await self.repository.add_role_permission(db, r.id, op.id)
        await self._commit(db, "Failed to copy role permissions")
        return role_to_dict(
            r,
            [op.key for op in orig_perms] if orig_perms else ["dashboard:read"],
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
        existing = await self.repository.get_role_permission_ids(db, role_id)
        for item in existing:
            await self.repository.delete_role_permission(db, item)
        if permissions:
            found_perms = await self.repository.get_permissions_by_keys_or_ids(db, permissions)
            for p in found_perms:
                await self.repository.add_role_permission(db, role_id, p.id)
        await self._commit(db, "Failed to assign permissions")
        return {"message": f"Updated permissions for role {role_id}", "status": "success"}

    # --- Remove permission from role ---
    async def remove_permission(
        self, db: AsyncSession, role_id: str, perm_id: str, current_user: User
    ) -> dict:
        role = await self.repository.get_role(db, role_id)
        if not role:
            raise NotFoundError(message=f"Role '{role_id}' not found")
        self._ensure_mutable_role_ownership(role, current_user)
        target_perm = await self.repository.get_permission_by_id_or_key(db, perm_id)
        target_id = target_perm.id if target_perm else perm_id
        await self.repository.remove_permission_from_role(db, role_id, target_id)
        await self._commit(db, "Failed to remove permission")
        return {"message": f"Permission '{perm_id}' removed from role", "status": "success"}

    # --- Get role users ---
    async def get_role_users(
        self, db: AsyncSession, role_id: str, current_user: User
    ) -> list[dict]:
        r = await self.repository.get_role_by_id_or_name(db, role_id)
        if not r:
            raise NotFoundError(message=f"Role '{role_id}' not found")
        self._ensure_assignable_role_ownership(r, current_user)
        target_role_id = r.id
        target_role_name = r.name
        users = await self.repository.get_users_by_role(db, target_role_id)
        ur_users = await self.repository.get_users_by_user_role_id(db, target_role_id)
        user_dict = {u.id: u for u in list(users) + list(ur_users)}
        org_id = self._current_org_id(current_user)
        matched = [u for u in user_dict.values() if u.organization_id == org_id]
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

    # --- Set default role ---
    async def set_default_role(
        self, db: AsyncSession, role_id: str, current_user: User
    ) -> dict:
        r = await self.repository.get_role_by_id_or_name(db, role_id)
        if not r:
            raise NotFoundError(message=f"Role '{role_id}' not found")
        self._ensure_assignable_role_ownership(r, current_user)
        organization_id = self._current_org_id(current_user)
        roles_setting_key = self._role_setting_key(
            "default_registration_roles", organization_id
        )
        role_setting_key = self._role_setting_key(
            "default_registration_role", organization_id
        )
        setting = await self.repository.get_setting(db, roles_setting_key)
        current_defaults = []
        if setting and setting.value:
            try:
                current_defaults = json.loads(setting.value)
                if not isinstance(current_defaults, list):
                    current_defaults = [str(current_defaults)]
            except Exception:
                current_defaults = [s.strip() for s in setting.value.split(",") if s.strip()]
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
        if current_defaults:
            await self.repository.upsert_setting(
                db, role_setting_key, current_defaults[0], "Legacy single default role"
            )
        await db.commit()
        return {"message": msg, "status": "success"}


role_service = RoleService()
