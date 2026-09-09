"""Add isolated WhatsApp channel persistence (expand-only)."""

import sqlalchemy as sa
from alembic import op

revision = "v6f7a8b9c0d1"
down_revision = "u5e6f7a8b9c0"
branch_labels = None
depends_on = None

WHATSAPP_PERMISSION_KEYS = (
    "whatsapp:read_assigned",
    "whatsapp:read_all",
    "whatsapp:send",
    "whatsapp:assign",
    "whatsapp:takeover",
    "whatsapp:manage_ai",
)


def upgrade() -> None:
    op.add_column("contacts", sa.Column("normalized_phone", sa.String(length=16), nullable=True))
    op.add_column(
        "contacts",
        sa.Column("whatsapp_phone_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("leads", sa.Column("normalized_phone", sa.String(length=16), nullable=True))
    op.add_column(
        "leads", sa.Column("whatsapp_phone_verified_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_unique_constraint(
        "uq_contacts_org_id_whatsapp", "contacts", ["organization_id", "id"]
    )
    op.create_unique_constraint("uq_leads_org_id_whatsapp", "leads", ["organization_id", "id"])
    op.create_table(
        "whatsapp_integrations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("catalog_integration_id", sa.String(), nullable=False),
        sa.Column("business_account_id", sa.String(length=100), nullable=False),
        sa.Column("phone_number_id", sa.String(length=100), nullable=False),
        sa.Column("display_phone_number", sa.String(length=50), nullable=True),
        sa.Column("verified_name", sa.String(length=255), nullable=True),
        sa.Column("api_version", sa.String(length=20), nullable=False),
        sa.Column("default_phone_region", sa.String(length=2), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "phone_index_ready", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "phone_backfill_stage", sa.String(length=10), server_default="contacts", nullable=False
        ),
        sa.Column("phone_backfill_cursor", sa.String(), nullable=True),
        sa.Column("ai_user_id", sa.String(), nullable=True),
        sa.Column("default_assignee_id", sa.String(), nullable=True),
        sa.Column("last_webhook_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_successful_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["ai_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["catalog_integration_id"], ["integrations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["default_assignee_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("catalog_integration_id"),
        sa.UniqueConstraint("organization_id"),
        sa.UniqueConstraint("organization_id", "id"),
        sa.UniqueConstraint("phone_number_id"),
    )
    op.create_table(
        "whatsapp_phone_repairs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(length=10), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("entity_type IN ('contact','lead')", name="ck_wa_phone_repair_type"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "entity_type", "entity_id"),
    )
    op.create_index(
        "ix_whatsapp_phone_repairs_organization_id",
        "whatsapp_phone_repairs",
        ["organization_id"],
    )
    op.create_index("ix_wa_phone_repair_work", "whatsapp_phone_repairs", ["created_at", "id"])
    op.create_table(
        "whatsapp_templates",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("integration_id", sa.String(), nullable=False),
        sa.Column("provider_template_id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("language", sa.String(length=20), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("body_parameter_count", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "integration_id"],
            ["whatsapp_integrations.organization_id", "whatsapp_integrations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("integration_id", "name", "language"),
        sa.UniqueConstraint("integration_id", "provider_template_id"),
    )
    op.create_index(
        "ix_whatsapp_templates_organization_id", "whatsapp_templates", ["organization_id"]
    )
    op.create_index("ix_whatsapp_templates_status", "whatsapp_templates", ["status"])
    op.create_table(
        "whatsapp_webhook_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("integration_id", sa.String(), nullable=False),
        sa.Column("event_key", sa.String(length=64), nullable=False),
        sa.Column("correlation_id", sa.String(length=36), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "integration_id"],
            ["whatsapp_integrations.organization_id", "whatsapp_integrations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("integration_id", "event_key"),
    )
    op.create_index(
        "ix_wa_event_work", "whatsapp_webhook_events", ["status", "next_attempt_at"], unique=False
    )
    op.create_table(
        "whatsapp_contact_identities",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("integration_id", sa.String(), nullable=False),
        sa.Column("normalized_phone_number", sa.String(length=16), nullable=False),
        sa.Column("contact_id", sa.String(), nullable=True),
        sa.Column("lead_id", sa.String(), nullable=True),
        sa.Column("state", sa.String(length=30), nullable=False),
        sa.Column("consent", sa.String(length=20), nullable=False),
        sa.Column("consent_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "consent IN ('UNKNOWN','OPTED_IN','OPTED_OUT')", name="ck_wa_identity_consent"
        ),
        sa.CheckConstraint(
            "state IN ('UNKNOWN','AMBIGUOUS','MATCHED_CONTACT','MATCHED_LEAD')",
            name="ck_wa_identity_state",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "contact_id"],
            ["contacts.organization_id", "contacts.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "lead_id"],
            ["leads.organization_id", "leads.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "integration_id"],
            ["whatsapp_integrations.organization_id", "whatsapp_integrations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("integration_id", "normalized_phone_number"),
        sa.UniqueConstraint("organization_id", "integration_id", "id"),
    )
    op.create_index(
        op.f("ix_whatsapp_contact_identities_contact_id"),
        "whatsapp_contact_identities",
        ["contact_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_whatsapp_contact_identities_lead_id"),
        "whatsapp_contact_identities",
        ["lead_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_whatsapp_contact_identities_organization_id"),
        "whatsapp_contact_identities",
        ["organization_id"],
        unique=False,
    )
    op.create_table(
        "whatsapp_conversations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("integration_id", sa.String(), nullable=False),
        sa.Column("identity_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("ai_enabled", sa.Boolean(), nullable=False),
        sa.Column("assigned_user_id", sa.String(), nullable=True),
        sa.Column("last_customer_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('OPEN','HUMAN_HANDOFF','CLOSED')", name="ck_wa_conversation_status"
        ),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["organization_id", "integration_id", "identity_id"],
            [
                "whatsapp_contact_identities.organization_id",
                "whatsapp_contact_identities.integration_id",
                "whatsapp_contact_identities.id",
            ],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("identity_id"),
        sa.UniqueConstraint("organization_id", "integration_id", "id"),
    )
    op.create_index(
        "ix_wa_conversation_inbox",
        "whatsapp_conversations",
        ["organization_id", "last_message_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_whatsapp_conversations_assigned_user_id"),
        "whatsapp_conversations",
        ["assigned_user_id"],
        unique=False,
    )
    op.create_table(
        "whatsapp_messages",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("integration_id", sa.String(), nullable=False),
        sa.Column("conversation_id", sa.String(), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("reply_to_message_id", sa.String(), nullable=True),
        sa.Column("direction", sa.String(length=10), nullable=False),
        sa.Column("source", sa.String(length=10), nullable=False),
        sa.Column("message_type", sa.String(length=30), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("media_metadata", sa.JSON(), nullable=True),
        sa.Column("media_s3_key", sa.String(length=500), nullable=True),
        sa.Column("template_payload", sa.JSON(), nullable=True),
        sa.Column("ai_topic", sa.String(length=30), nullable=True),
        sa.Column("sender_phone", sa.String(length=50), nullable=False),
        sa.Column("recipient_phone", sa.String(length=50), nullable=False),
        sa.Column("actor_user_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("work_status", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.String(length=255), nullable=True),
        sa.Column("provider_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("direction IN ('INBOUND','OUTBOUND')", name="ck_wa_message_direction"),
        sa.CheckConstraint(
            "status IN ('RECEIVED','PENDING','PROCESSING','ACCEPTED','SENT','DELIVERED','READ','FAILED','UNKNOWN')",
            name="ck_wa_message_status",
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["organization_id", "integration_id", "conversation_id"],
            [
                "whatsapp_conversations.organization_id",
                "whatsapp_conversations.integration_id",
                "whatsapp_conversations.id",
            ],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["reply_to_message_id"], ["whatsapp_messages.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("integration_id", "idempotency_key"),
        sa.UniqueConstraint("integration_id", "provider_message_id"),
        sa.UniqueConstraint("reply_to_message_id"),
    )
    op.create_index(
        "ix_wa_message_history",
        "whatsapp_messages",
        ["organization_id", "conversation_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_wa_message_work",
        "whatsapp_messages",
        ["work_status", "next_attempt_at", "direction"],
        unique=False,
    )
    op.create_table(
        "whatsapp_read_states",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("integration_id", sa.String(), nullable=False),
        sa.Column("conversation_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "integration_id", "conversation_id"],
            [
                "whatsapp_conversations.organization_id",
                "whatsapp_conversations.integration_id",
                "whatsapp_conversations.id",
            ],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_id", "user_id"),
    )
    op.create_index(
        "ix_contacts_org_normalized_phone", "contacts", ["organization_id", "normalized_phone"]
    )
    op.create_index(
        "ix_leads_org_normalized_phone", "leads", ["organization_id", "normalized_phone"]
    )
    # Covers imports, bulk SQL and older application instances during rollout.
    # A changed phone invalidates only that record's verification. It must never
    # suspend matching for every other customer in the organization.
    op.execute("""
        CREATE FUNCTION crm_invalidate_whatsapp_phone() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'INSERT' OR NEW.phone IS DISTINCT FROM OLD.phone THEN
                NEW.whatsapp_phone_verified_at := NULL;
                IF EXISTS (
                    SELECT 1 FROM whatsapp_integrations
                    WHERE organization_id = NEW.organization_id
                ) THEN
                    PERFORM pg_advisory_xact_lock(
                        hashtext('wa-phone:' || NEW.organization_id)
                    );
                    INSERT INTO whatsapp_phone_repairs (
                        id, organization_id, entity_type, entity_id
                    ) VALUES (
                        gen_random_uuid()::text, NEW.organization_id,
                        CASE WHEN TG_TABLE_NAME = 'contacts' THEN 'contact' ELSE 'lead' END,
                        NEW.id
                    )
                    ON CONFLICT (organization_id, entity_type, entity_id)
                    DO UPDATE SET created_at = now();
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute(
        "CREATE TRIGGER contacts_whatsapp_phone_change BEFORE INSERT OR UPDATE OF phone ON contacts FOR EACH ROW EXECUTE FUNCTION crm_invalidate_whatsapp_phone()"
    )
    op.execute(
        "CREATE TRIGGER leads_whatsapp_phone_change BEFORE INSERT OR UPDATE OF phone ON leads FOR EACH ROW EXECUTE FUNCTION crm_invalidate_whatsapp_phone()"
    )
    op.execute("""
        INSERT INTO permissions (id, key, name, category)
        SELECT gen_random_uuid()::text, key, initcap(replace(split_part(key, ':', 2), '_', ' ')), 'WhatsApp'
        FROM unnest(ARRAY['whatsapp:read_assigned','whatsapp:read_all','whatsapp:send','whatsapp:assign','whatsapp:takeover','whatsapp:manage_ai']) AS key
        ON CONFLICT (key) DO NOTHING
        """)
    op.execute("""
        INSERT INTO role_permissions (id, role_id, permission_id)
        SELECT gen_random_uuid()::text, role.id, permission.id
        FROM roles role CROSS JOIN permissions permission
        WHERE permission.key LIKE 'whatsapp:%'
          AND (
            role.name IN ('Admin', 'Sales Manager', 'Customer Support')
            OR (role.name = 'Sales Executive' AND permission.key IN ('whatsapp:read_assigned','whatsapp:send','whatsapp:takeover'))
          )
        ON CONFLICT DO NOTHING
        """)


def downgrade() -> None:
    raise RuntimeError(
        "Data-preserving migration: disable WhatsApp and roll back application code; do not drop conversation history."
    )
