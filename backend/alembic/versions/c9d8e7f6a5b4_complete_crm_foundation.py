"""Complete CRM teams, support, dashboards, workflows, scopes, and project links.

Revision ID: c9d8e7f6a5b4
Revises: p1r2o3j4s5f6
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import insert

revision: str = "c9d8e7f6a5b4"
down_revision: str | None = "p1r2o3j4s5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_PERMISSIONS = {
    "tickets:read": ("View Tickets", "Tickets"),
    "tickets:create": ("Create Tickets", "Tickets"),
    "tickets:update": ("Update Tickets", "Tickets"),
    "tickets:delete": ("Archive Tickets", "Tickets"),
    "tickets:assign": ("Assign Tickets", "Tickets"),
    "tickets:export": ("Export Tickets", "Tickets"),
    "knowledge_base:read": ("View Knowledge Base", "Knowledge Base"),
    "knowledge_base:create": ("Create Knowledge Articles", "Knowledge Base"),
    "knowledge_base:update": ("Update Knowledge Articles", "Knowledge Base"),
    "knowledge_base:delete": ("Delete Knowledge Articles", "Knowledge Base"),
    "knowledge_base:publish": ("Publish Knowledge Articles", "Knowledge Base"),
    "teams:read": ("View Teams", "Teams"),
    "teams:create": ("Create Teams", "Teams"),
    "teams:update": ("Update Teams", "Teams"),
    "teams:delete": ("Delete Teams", "Teams"),
    "teams:manage_members": ("Manage Team Members", "Teams"),
    "workflows:read": ("View Workflows", "Workflows"),
    "workflows:create": ("Create Workflows", "Workflows"),
    "workflows:update": ("Update Workflows", "Workflows"),
    "workflows:delete": ("Delete Workflows", "Workflows"),
}


def upgrade() -> None:
    permission_table = sa.table(
        "permissions",
        sa.column("id", sa.String()),
        sa.column("key", sa.String()),
        sa.column("name", sa.String()),
        sa.column("category", sa.String()),
        sa.column("description", sa.Text()),
    )
    op.execute(
        insert(permission_table)
        .values(
            [
                {
                    "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"crm-permission:{key}")),
                    "key": key,
                    "name": name,
                    "category": category,
                    "description": name,
                }
                for key, (name, category) in NEW_PERMISSIONS.items()
            ]
        )
        .on_conflict_do_nothing(index_elements=["key"])
    )
    op.add_column(
        "organizations",
        sa.Column("ticket_prefix", sa.String(20), server_default="TKT", nullable=False),
    )
    op.add_column(
        "organizations",
        sa.Column("ticket_sequence", sa.BigInteger(), server_default="0", nullable=False),
    )
    op.add_column("tasks", sa.Column("created_by", sa.String(), nullable=True))
    op.create_foreign_key(
        "fk_tasks_created_by",
        "tasks",
        "users",
        ["created_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_tasks_created_by", "tasks", ["created_by"])
    op.execute(sa.text("UPDATE tasks SET created_by = assigned_to WHERE created_by IS NULL"))
    for table, column in (
        ("leads", "created_by"),
        ("deals", "created_by"),
        ("contacts", "owner_id"),
        ("contacts", "created_by"),
        ("companies", "owner_id"),
        ("companies", "created_by"),
    ):
        op.add_column(table, sa.Column(column, sa.String(), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_{column}",
            table,
            "users",
            [column],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(f"ix_{table}_{column}", table, [column])
    op.execute(sa.text("UPDATE leads SET created_by = assigned_to WHERE created_by IS NULL"))
    op.execute(sa.text("UPDATE deals SET created_by = assigned_to WHERE created_by IS NULL"))
    op.execute(
        sa.text(
            "UPDATE contacts SET owner_id = (SELECT id FROM users "
            "WHERE users.organization_id = contacts.organization_id "
            "ORDER BY users.created_at LIMIT 1) WHERE owner_id IS NULL"
        )
    )
    op.execute(sa.text("UPDATE contacts SET created_by = owner_id WHERE created_by IS NULL"))
    op.execute(
        sa.text(
            "UPDATE companies SET owner_id = (SELECT id FROM users "
            "WHERE users.organization_id = companies.organization_id "
            "ORDER BY users.created_at LIMIT 1) WHERE owner_id IS NULL"
        )
    )
    op.execute(sa.text("UPDATE companies SET created_by = owner_id WHERE created_by IS NULL"))
    for table in ("quotes", "sales_orders", "invoices"):
        op.add_column(table, sa.Column("created_by", sa.String(), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_created_by",
            table,
            "users",
            ["created_by"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(f"ix_{table}_created_by", table, ["created_by"])
    op.execute(
        sa.text(
            "UPDATE quotes SET created_by = (SELECT assigned_to FROM deals "
            "WHERE deals.id = quotes.deal_id) WHERE created_by IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE sales_orders SET created_by = (SELECT created_by FROM quotes "
            "WHERE quotes.id = sales_orders.quote_id) WHERE created_by IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE invoices SET created_by = COALESCE("
            "(SELECT created_by FROM quotes WHERE quotes.id = invoices.quote_id), "
            "(SELECT assigned_to FROM deals WHERE deals.id = invoices.deal_id)) "
            "WHERE created_by IS NULL"
        )
    )

    op.create_table(
        "teams",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("manager_id", sa.String()),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["manager_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_teams_organization_id", "teams", ["organization_id"])
    op.create_index("ix_teams_manager_id", "teams", ["manager_id"])
    op.create_index(
        "uq_teams_org_name",
        "teams",
        ["organization_id", sa.text("lower(btrim(name))")],
        unique=True,
    )
    op.create_table(
        "team_memberships",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("team_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_team_membership_pair", "team_memberships", ["team_id", "user_id"], unique=True
    )
    op.create_index(
        "uq_team_membership_primary_user",
        "team_memberships",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_primary"),
    )

    op.create_table(
        "role_record_scopes",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("role_id", sa.String(), nullable=False),
        sa.Column("module", sa.String(50), nullable=False),
        sa.Column("scope", sa.String(20), server_default="all", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "scope IN ('all','team','assigned','own','none')", name="ck_role_record_scopes_scope"
        ),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_role_record_scopes_role_module",
        "role_record_scopes",
        ["role_id", "module"],
        unique=True,
    )
    op.execute(
        sa.text(
            """
            INSERT INTO role_record_scopes (id, role_id, module, scope)
            SELECT 'scope-' || md5(roles.id || ':' || modules.module),
                   roles.id, modules.module, 'all'
            FROM roles
            CROSS JOIN (VALUES
                ('leads'), ('contacts'), ('companies'), ('deals'),
                ('tasks'), ('projects'), ('tickets'), ('documents'),
                ('quotes'), ('orders'), ('invoices'), ('payments')
            ) AS modules(module)
            ON CONFLICT (role_id, module) DO NOTHING
            """
        )
    )

    for column, target in (
        ("company_id", "companies.id"),
        ("contact_id", "contacts.id"),
        ("originating_deal_id", "deals.id"),
        ("created_by", "users.id"),
    ):
        op.add_column("projects", sa.Column(column, sa.String(), nullable=True))
        op.create_foreign_key(
            f"fk_projects_{column}",
            "projects",
            target.split(".")[0],
            [column],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(
            f"ix_projects_{column}", "projects", [column], unique=column == "originating_deal_id"
        )
    op.create_table(
        "project_stakeholders",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("contact_id", sa.String(), nullable=False),
        sa.Column("role", sa.String(100), server_default="Stakeholder", nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "contact_id", name="uq_project_stakeholder_pair"),
    )
    op.create_index("ix_project_stakeholders_project_id", "project_stakeholders", ["project_id"])
    op.create_index("ix_project_stakeholders_contact_id", "project_stakeholders", ["contact_id"])

    op.create_table(
        "tickets",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("ticket_number", sa.String(50), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), server_default="New", nullable=False),
        sa.Column("priority", sa.String(20), server_default="Medium", nullable=False),
        sa.Column("source", sa.String(20), server_default="CRM", nullable=False),
        sa.Column("contact_id", sa.String()),
        sa.Column("company_id", sa.String()),
        sa.Column("assigned_to", sa.String()),
        sa.Column("team_id", sa.String()),
        sa.Column("sla_policy_id", sa.String()),
        sa.Column("created_by", sa.String()),
        sa.Column("first_response_due_at", sa.DateTime(timezone=True)),
        sa.Column("resolution_due_at", sa.DateTime(timezone=True)),
        sa.Column("first_responded_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("is_archived", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('New','Open','Pending','Resolved','Closed')", name="ck_tickets_status"
        ),
        sa.CheckConstraint(
            "priority IN ('Low','Medium','High','Urgent')", name="ck_tickets_priority"
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["sla_policy_id"], ["sla_policies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "ticket_number", name="uq_tickets_org_number"),
    )
    for col in (
        "organization_id",
        "status",
        "priority",
        "contact_id",
        "company_id",
        "assigned_to",
        "team_id",
        "sla_policy_id",
        "created_by",
    ):
        op.create_index(f"ix_tickets_{col}", "tickets", [col])
    op.create_index(
        "ix_tickets_org_status_created", "tickets", ["organization_id", "status", "created_at"]
    )
    op.add_column("tasks", sa.Column("ticket_id", sa.String(), nullable=True))
    op.create_foreign_key(
        "fk_tasks_ticket_id",
        "tasks",
        "tickets",
        ["ticket_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_tasks_ticket_id", "tasks", ["ticket_id"])

    op.create_table(
        "ticket_comments",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "ticket_id",
            sa.String(),
            sa.ForeignKey("tickets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_internal", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_ticket_comments_ticket_id", "ticket_comments", ["ticket_id"])
    op.create_table(
        "ticket_status_history",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "ticket_id",
            sa.String(),
            sa.ForeignKey("tickets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_status", sa.String(20)),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("changed_by", sa.String(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_ticket_status_history_ticket_id", "ticket_status_history", ["ticket_id"])

    op.create_table(
        "knowledge_articles",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("summary", sa.String(500)),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("category", sa.String(100)),
        sa.Column("status", sa.String(20), server_default="Draft", nullable=False),
        sa.Column("author_id", sa.String(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("organization_id", "slug", name="uq_knowledge_articles_org_slug"),
    )
    op.create_index(
        "ix_knowledge_articles_organization_id", "knowledge_articles", ["organization_id"]
    )
    op.create_table(
        "ticket_knowledge_articles",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "ticket_id",
            sa.String(),
            sa.ForeignKey("tickets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "article_id",
            sa.String(),
            sa.ForeignKey("knowledge_articles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.UniqueConstraint("ticket_id", "article_id", name="uq_ticket_knowledge_pair"),
    )

    op.create_table(
        "dashboard_layouts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("owner_id", sa.String(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("is_shared", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("widgets", sa.JSON(), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("organization_id", "name", name="uq_dashboard_layouts_org_name"),
    )

    op.create_table(
        "workflows",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("module", sa.String(50), nullable=False),
        sa.Column("trigger", sa.String(50), nullable=False),
        sa.Column("conditions", sa.JSON(), nullable=False),
        sa.Column("actions", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_by", sa.String(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("activated_by", sa.String(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("organization_id", "name", name="uq_workflows_org_name"),
    )
    for column in ("organization_id", "module", "trigger", "is_active", "created_by"):
        op.create_index(f"ix_workflows_{column}", "workflows", [column])
    op.create_table(
        "workflow_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("module", sa.String(50), nullable=False),
        sa.Column("trigger", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("actor_id", sa.String(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("correlation_id", sa.String(36), nullable=False),
        sa.Column("depth", sa.Integer(), server_default="0", nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), server_default="Pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(500)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
    )
    for column in ("organization_id", "entity_id", "correlation_id", "status"):
        op.create_index(f"ix_workflow_events_{column}", "workflow_events", [column])
    op.create_index(
        "ix_workflow_events_claim",
        "workflow_events",
        ["status", "next_attempt_at", "created_at"],
    )
    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "event_id",
            sa.String(),
            sa.ForeignKey("workflow_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workflow_id",
            sa.String(),
            sa.ForeignKey("workflows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("action_results", sa.JSON(), nullable=False),
        sa.Column("error", sa.String(500)),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("event_id", "workflow_id", name="uq_workflow_runs_event_workflow"),
    )
    op.create_index("ix_workflow_runs_event_id", "workflow_runs", ["event_id"])
    op.create_index("ix_workflow_runs_workflow_id", "workflow_runs", ["workflow_id"])


def downgrade() -> None:
    # Permission rows are intentionally retained: deleting them can cascade
    # through role assignments and destroy administrator configuration.
    op.drop_index("ix_tasks_ticket_id", table_name="tasks")
    op.drop_constraint("fk_tasks_ticket_id", "tasks", type_="foreignkey")
    op.drop_column("tasks", "ticket_id")
    for table in (
        "workflow_runs",
        "workflow_events",
        "workflows",
        "dashboard_layouts",
        "ticket_knowledge_articles",
        "knowledge_articles",
        "ticket_status_history",
        "ticket_comments",
        "tickets",
        "project_stakeholders",
        "role_record_scopes",
        "team_memberships",
        "teams",
    ):
        op.drop_table(table)
    for column in ("created_by", "originating_deal_id", "contact_id", "company_id"):
        op.drop_column("projects", column)
    op.drop_index("ix_tasks_created_by", table_name="tasks")
    op.drop_constraint("fk_tasks_created_by", "tasks", type_="foreignkey")
    op.drop_column("tasks", "created_by")
    for table, column in (
        ("invoices", "created_by"),
        ("sales_orders", "created_by"),
        ("quotes", "created_by"),
        ("companies", "created_by"),
        ("companies", "owner_id"),
        ("contacts", "created_by"),
        ("contacts", "owner_id"),
        ("deals", "created_by"),
        ("leads", "created_by"),
    ):
        op.drop_index(f"ix_{table}_{column}", table_name=table)
        op.drop_constraint(f"fk_{table}_{column}", table, type_="foreignkey")
        op.drop_column(table, column)
    op.drop_column("organizations", "ticket_sequence")
    op.drop_column("organizations", "ticket_prefix")
