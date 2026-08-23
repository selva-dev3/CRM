"""seed missing organization and admin standard permissions

Revision ID: f9a0b1c2d3e4
Revises: e7f8a9b0c1d2
Create Date: 2026-08-23 00:00:00.000000

"""

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f9a0b1c2d3e4"
down_revision: Union[str, Sequence[str], None] = "e7f8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# NOTE: STANDARD_PERMISSIONS is intentionally a frozen point-in-time snapshot for migration f9a0b1c2d3e4.
# Future standard permission additions must be added via subsequent new Alembic migrations rather than
# mutating this historical file, preserving Alembic migration reproducibility.
STANDARD_PERMISSIONS = [
    {"key": "dashboard:read", "name": "View Dashboard", "category": "Dashboard", "description": "View CRM executive dashboard metrics"},
    {"key": "dashboard:customize", "name": "Customize Dashboard", "category": "Dashboard", "description": "Customize dashboard widgets and layout"},
    {"key": "dashboard:export", "name": "Export Dashboard", "category": "Dashboard", "description": "Export dashboard data to PDF or Excel"},
    {"key": "leads:read", "name": "View Leads", "category": "Leads", "description": "View sales leads and details"},
    {"key": "leads:create", "name": "Create Leads", "category": "Leads", "description": "Create new sales leads"},
    {"key": "leads:update", "name": "Update Leads", "category": "Leads", "description": "Edit existing lead details"},
    {"key": "leads:delete", "name": "Delete Leads", "category": "Leads", "description": "Delete lead records"},
    {"key": "leads:export", "name": "Export Leads", "category": "Leads", "description": "Export leads to CSV/Excel"},
    {"key": "leads:import", "name": "Import Leads", "category": "Leads", "description": "Import leads from CSV/Excel"},
    {"key": "leads:assign", "name": "Assign Leads", "category": "Leads", "description": "Assign leads to team members"},
    {"key": "leads:convert", "name": "Convert Leads", "category": "Leads", "description": "Convert leads into accounts and deals"},
    {"key": "leads:bulk_delete", "name": "Bulk Delete Leads", "category": "Leads", "description": "Perform bulk deletion on multiple leads"},
    {"key": "leads:bulk_update", "name": "Bulk Update Leads", "category": "Leads", "description": "Perform bulk updates on lead fields"},
    {"key": "contacts:read", "name": "View Contacts", "category": "Contacts", "description": "View contact records"},
    {"key": "contacts:create", "name": "Create Contacts", "category": "Contacts", "description": "Create new contact records"},
    {"key": "contacts:update", "name": "Update Contacts", "category": "Contacts", "description": "Edit existing contact information"},
    {"key": "contacts:delete", "name": "Delete Contacts", "category": "Contacts", "description": "Delete contact records"},
    {"key": "contacts:export", "name": "Export Contacts", "category": "Contacts", "description": "Export contact list"},
    {"key": "contacts:import", "name": "Import Contacts", "category": "Contacts", "description": "Import contact list"},
    {"key": "contacts:assign", "name": "Assign Contacts", "category": "Contacts", "description": "Assign contacts to owners"},
    {"key": "contacts:bulk_delete", "name": "Bulk Delete Contacts", "category": "Contacts", "description": "Bulk delete selected contacts"},
    {"key": "contacts:bulk_update", "name": "Bulk Update Contacts", "category": "Contacts", "description": "Bulk update contact fields"},
    {"key": "companies:read", "name": "View Companies", "category": "Companies", "description": "View company accounts"},
    {"key": "companies:create", "name": "Create Companies", "category": "Companies", "description": "Create new company accounts"},
    {"key": "companies:update", "name": "Update Companies", "category": "Companies", "description": "Update company account details"},
    {"key": "companies:delete", "name": "Delete Companies", "category": "Companies", "description": "Delete company accounts"},
    {"key": "companies:export", "name": "Export Companies", "category": "Companies", "description": "Export company account list"},
    {"key": "companies:import", "name": "Import Companies", "category": "Companies", "description": "Import company accounts"},
    {"key": "companies:bulk_delete", "name": "Bulk Delete Companies", "category": "Companies", "description": "Bulk delete company accounts"},
    {"key": "deals:read", "name": "View Deals", "category": "Deals", "description": "View sales deals and pipelines"},
    {"key": "deals:create", "name": "Create Deals", "category": "Deals", "description": "Create new deal opportunities"},
    {"key": "deals:update", "name": "Update Deals", "category": "Deals", "description": "Update deal stages and amounts"},
    {"key": "deals:delete", "name": "Delete Deals", "category": "Deals", "description": "Delete deal opportunities"},
    {"key": "deals:pipeline", "name": "Manage Pipelines", "category": "Deals", "description": "Configure deal pipeline stages"},
    {"key": "deals:export", "name": "Export Deals", "category": "Deals", "description": "Export sales deal data"},
    {"key": "deals:import", "name": "Import Deals", "category": "Deals", "description": "Import deal opportunities"},
    {"key": "deals:assign", "name": "Assign Deals", "category": "Deals", "description": "Reassign deal ownership"},
    {"key": "deals:bulk_delete", "name": "Bulk Delete Deals", "category": "Deals", "description": "Bulk delete selected deals"},
    {"key": "tasks:read", "name": "View Tasks", "category": "Tasks", "description": "View task lists and status"},
    {"key": "tasks:create", "name": "Create Tasks", "category": "Tasks", "description": "Create new task items"},
    {"key": "tasks:update", "name": "Update Tasks", "category": "Tasks", "description": "Update task progress and status"},
    {"key": "tasks:delete", "name": "Delete Tasks", "category": "Tasks", "description": "Delete task items"},
    {"key": "tasks:assign", "name": "Assign Tasks", "category": "Tasks", "description": "Assign tasks to team members"},
    {"key": "tasks:complete", "name": "Mark Tasks Complete", "category": "Tasks", "description": "Mark assigned tasks completed"},
    {"key": "meetings:read", "name": "View Meetings", "category": "Meetings", "description": "View scheduled meetings"},
    {"key": "meetings:create", "name": "Schedule Meetings", "category": "Meetings", "description": "Schedule new customer meetings"},
    {"key": "meetings:update", "name": "Update Meetings", "category": "Meetings", "description": "Reschedule or update meeting details"},
    {"key": "meetings:delete", "name": "Cancel Meetings", "category": "Meetings", "description": "Cancel or delete meetings"},
    {"key": "meetings:invite", "name": "Invite Meeting Attendees", "category": "Meetings", "description": "Send invitations to meeting attendees"},
    {"key": "calls:read", "name": "View Call Logs", "category": "Calls", "description": "View sales call logs and recordings"},
    {"key": "calls:create", "name": "Log Calls", "category": "Calls", "description": "Log new outbound or inbound calls"},
    {"key": "calls:update", "name": "Update Call Logs", "category": "Calls", "description": "Update call notes and outcomes"},
    {"key": "calls:delete", "name": "Delete Call Logs", "category": "Calls", "description": "Delete call log entries"},
    {"key": "calls:recording", "name": "Access Call Recordings", "category": "Calls", "description": "Listen to and download call recordings"},
    {"key": "emails:read", "name": "View Email Logs", "category": "Emails", "description": "View sent and received emails"},
    {"key": "emails:send", "name": "Send Emails", "category": "Emails", "description": "Send emails to leads and contacts"},
    {"key": "emails:templates", "name": "Manage Templates", "category": "Emails", "description": "Create and edit email templates"},
    {"key": "emails:delete", "name": "Delete Email Logs", "category": "Emails", "description": "Delete stored email conversation logs"},
    {"key": "notes:read", "name": "View Notes", "category": "Notes", "description": "View notes on CRM records"},
    {"key": "notes:create", "name": "Create Notes", "category": "Notes", "description": "Add new notes to leads, contacts, or deals"},
    {"key": "notes:update", "name": "Update Notes", "category": "Notes", "description": "Edit existing note content"},
    {"key": "notes:delete", "name": "Delete Notes", "category": "Notes", "description": "Delete notes from records"},
    {"key": "documents:read", "name": "View Documents", "category": "Documents", "description": "View attached documents and files"},
    {"key": "documents:upload", "name": "Upload Documents", "category": "Documents", "description": "Upload new files to MinIO S3 storage"},
    {"key": "documents:delete", "name": "Delete Documents", "category": "Documents", "description": "Delete uploaded documents"},
    {"key": "documents:share", "name": "Share Documents", "category": "Documents", "description": "Share document links externally"},
    {"key": "products:read", "name": "View Products", "category": "Products", "description": "View product catalog and price list"},
    {"key": "products:create", "name": "Create Products", "category": "Products", "description": "Add new products to catalog"},
    {"key": "products:update", "name": "Update Products", "category": "Products", "description": "Edit product pricing and details"},
    {"key": "products:delete", "name": "Delete Products", "category": "Products", "description": "Remove products from catalog"},
    {"key": "products:export", "name": "Export Products", "category": "Products", "description": "Export product catalog to CSV"},
    {"key": "products:import", "name": "Import Products", "category": "Products", "description": "Import product catalog"},
    {"key": "quotes:read", "name": "View Quotes", "category": "Quotes", "description": "View sales quotes and proposals"},
    {"key": "quotes:create", "name": "Create Quotes", "category": "Quotes", "description": "Generate new sales quotes"},
    {"key": "quotes:update", "name": "Update Quotes", "category": "Quotes", "description": "Edit sales quotes and line items"},
    {"key": "quotes:approve", "name": "Approve Quotes", "category": "Quotes", "description": "Approve high-value sales quotes"},
    {"key": "quotes:delete", "name": "Delete Quotes", "category": "Quotes", "description": "Delete sales quotes"},
    {"key": "quotes:send", "name": "Send Quotes to Client", "category": "Quotes", "description": "Send PDF quote proposals to client"},
    {"key": "invoices:read", "name": "View Invoices", "category": "Invoices", "description": "View customer invoices and payments"},
    {"key": "invoices:create", "name": "Create Invoices", "category": "Invoices", "description": "Create new billing invoices"},
    {"key": "invoices:update", "name": "Update Invoices", "category": "Invoices", "description": "Edit invoice details"},
    {"key": "invoices:send", "name": "Send Invoices", "category": "Invoices", "description": "Send invoices to customers"},
    {"key": "invoices:delete", "name": "Delete Invoices", "category": "Invoices", "description": "Delete invoice records"},
    {"key": "invoices:payment", "name": "Record Payments", "category": "Invoices", "description": "Record payment receipts on invoices"},
    {"key": "reports:read", "name": "View Analytics & Reports", "category": "Reports", "description": "View dashboard charts and reports"},
    {"key": "reports:create", "name": "Create Reports", "category": "Reports", "description": "Build custom analytics reports"},
    {"key": "reports:export", "name": "Export Reports", "category": "Reports", "description": "Export analytics data"},
    {"key": "reports:schedule", "name": "Schedule Automated Reports", "category": "Reports", "description": "Configure automated email report delivery"},
    {"key": "calendar:read", "name": "View Calendar", "category": "Calendar", "description": "View shared team calendar"},
    {"key": "calendar:write", "name": "Manage Calendar Events", "category": "Calendar", "description": "Create and edit team calendar events"},
    {"key": "calendar:sync", "name": "Sync External Calendar", "category": "Calendar", "description": "Sync Google and Outlook calendars"},
    {"key": "users:read", "name": "View Users", "category": "Users", "description": "View organization user list"},
    {"key": "users:create", "name": "Create Users", "category": "Users", "description": "Create new user accounts"},
    {"key": "users:invite", "name": "Invite Users", "category": "Users", "description": "Invite new users to organization"},
    {"key": "users:update", "name": "Update Users", "category": "Users", "description": "Update user profiles and status"},
    {"key": "users:delete", "name": "Delete Users", "category": "Users", "description": "Remove users from organization"},
    {"key": "users:export", "name": "Export User Directory", "category": "Users", "description": "Export team member directory"},
    {"key": "users:import", "name": "Import Users", "category": "Users", "description": "Import users in bulk"},
    {"key": "users:roles", "name": "Assign User Roles", "category": "Users", "description": "Change assigned RBAC roles for users"},
    {"key": "roles:read", "name": "View Roles & Permissions", "category": "Roles", "description": "View RBAC roles and permissions"},
    {"key": "roles:create", "name": "Create Custom Roles", "category": "Roles", "description": "Create new custom RBAC roles"},
    {"key": "roles:update", "name": "Update Roles", "category": "Roles", "description": "Edit role permissions"},
    {"key": "roles:delete", "name": "Delete Roles", "category": "Roles", "description": "Delete custom RBAC roles"},
    {"key": "roles:assign", "name": "Assign Role Permissions", "category": "Roles", "description": "Modify assigned action permissions"},
    {"key": "organization:read", "name": "View Organization Details", "category": "Organization", "description": "View organization profile"},
    {"key": "organization:update", "name": "Update Organization Profile", "category": "Organization", "description": "Edit organization settings"},
    {"key": "organization:billing", "name": "Manage Subscriptions", "category": "Organization", "description": "Manage subscription plans and billing"},
    {"key": "organization:domains", "name": "Manage Custom Domains", "category": "Organization", "description": "Configure custom domain verification"},
    {"key": "organization:branding", "name": "Update Organization Logo", "category": "Organization", "description": "Upload S3 logo and branding colors"},
    {"key": "organization:audit", "name": "View Audit Trail Logs", "category": "Organization", "description": "View organization audit logs"},
    {"key": "invitations:read", "name": "View Organization Invitations", "category": "Organization Invitations", "description": "View pending organization invites"},
    {"key": "invitations:create", "name": "Create Organization Invitation", "category": "Organization Invitations", "description": "Send new organization invitations"},
    {"key": "invitations:resend", "name": "Resend Invitation", "category": "Organization Invitations", "description": "Resend pending organization invitations"},
    {"key": "invitations:revoke", "name": "Revoke Invitation", "category": "Organization Invitations", "description": "Revoke pending organization invitations"},
    {"key": "integrations:read", "name": "View Integrations", "category": "Integrations", "description": "View connected third-party tools"},
    {"key": "integrations:manage", "name": "Manage Integrations", "category": "Integrations", "description": "Configure webhooks and integrations"},
    {"key": "integrations:apikeys", "name": "Manage API Keys", "category": "Integrations", "description": "Generate and revoke developer API keys"},
    {"key": "notifications:read", "name": "View Notifications", "category": "Notifications", "description": "View system notifications and alerts"},
    {"key": "notifications:manage", "name": "Manage Notification Rules", "category": "Notifications", "description": "Configure notification delivery preferences"},
    {"key": "notifications:send", "name": "Send Broadcast Notifications", "category": "Notifications", "description": "Send broadcast alerts to team"},
    {"key": "settings:read", "name": "View System Settings", "category": "Settings", "description": "View system-wide settings"},
    {"key": "settings:update", "name": "Update System Settings", "category": "Settings", "description": "Modify system configurations"},
    {"key": "settings:security", "name": "Manage Security & Auth Settings", "category": "Settings", "description": "Configure password policies and 2FA"},
    {"key": "activities:read", "name": "View Activity Trail", "category": "Activities", "description": "View activity logs across CRM"},
    {"key": "activities:create", "name": "Log Activity", "category": "Activities", "description": "Log new system activity"},
    {"key": "activities:export", "name": "Export Activity Trail", "category": "Activities", "description": "Export activity trail logs to CSV"},
    {"key": "ai:read", "name": "Access AI Sales Assistant", "category": "AI Assistant", "description": "Chat with AI sales assistant"},
    {"key": "ai:generate", "name": "Generate AI Content & Insights", "category": "AI Assistant", "description": "Generate AI email drafts and deal summaries"},
]


def upgrade() -> None:
    """Ensure all standard permissions exist and are attached to the system Admin role."""
    connection = op.get_bind()

    # 1. Insert missing permissions
    existing_perms = {
        row[0]: row[1]
        for row in connection.execute(
            sa.text("SELECT key, id FROM permissions WHERE key IS NOT NULL")
        ).fetchall()
    }

    for p in STANDARD_PERMISSIONS:
        key = p["key"]
        if key not in existing_perms:
            p_id = str(uuid.uuid4())
            connection.execute(
                sa.text(
                    "INSERT INTO permissions (id, key, name, category, description) "
                    "VALUES (:id, :key, :name, :category, :description)"
                ),
                {
                    "id": p_id,
                    "key": key,
                    "name": p["name"],
                    "category": p["category"],
                    "description": p["description"],
                },
            )
            existing_perms[key] = p_id

    # 2. Find or create ONLY the global system Admin role
    admin_res = connection.execute(
        sa.text(
            "SELECT id FROM roles "
            "WHERE LOWER(name) = 'admin' "
            "AND is_system_role = TRUE "
            "AND organization_id IS NULL "
            "ORDER BY created_at ASC "
            "LIMIT 1"
        )
    )
    admin = admin_res.fetchone() if admin_res else None

    if not admin:
        admin_id = str(uuid.uuid4())
        connection.execute(
            sa.text(
                "INSERT INTO roles (id, organization_id, name, description, is_system_role, created_at) "
                "VALUES (:id, NULL, 'Admin', 'Default admin role with all standard permissions', TRUE, NOW())"
            ),
            {"id": admin_id},
        )
    else:
        admin_id = admin[0]

    # 3. Attach ONLY standard catalog permissions to the system Admin role
    standard_keys = tuple(
        p["key"]
        for p in STANDARD_PERMISSIONS
        if p.get("key") and p["key"] != "all" and p["key"] != "super_admin:manage"
    )

    if standard_keys:
        all_perm_rows = connection.execute(
            sa.text(
                "SELECT id FROM permissions "
                "WHERE key IN :keys "
                "AND key IS NOT NULL "
                "AND key != 'all' "
                "AND key != 'super_admin:manage'"
            ).bindparams(sa.bindparam("keys", expanding=True)),
            {"keys": standard_keys},
        ).fetchall()

        existing_rp = {
            row[0]
            for row in connection.execute(
                sa.text("SELECT permission_id FROM role_permissions WHERE role_id = :role_id"),
                {"role_id": admin_id},
            ).fetchall()
        }

        for row in all_perm_rows:
            perm_id = row[0]
            if perm_id not in existing_rp:
                connection.execute(
                    sa.text(
                        "INSERT INTO role_permissions (id, role_id, permission_id) "
                        "VALUES (:id, :role_id, :permission_id)"
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "role_id": admin_id,
                        "permission_id": perm_id,
                    },
                )
                existing_rp.add(perm_id)


def downgrade() -> None:
    """No destructive downgrade needed as permissions are additive standard catalog definitions."""
    pass
