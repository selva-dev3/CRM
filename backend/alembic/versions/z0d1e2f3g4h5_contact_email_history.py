"""Add non-blocking contact email-history lookup indexes.

Revision ID: z0d1e2f3g4h5
Revises: y9c0d1e2f3g4
"""

from alembic import op

revision = "z0d1e2f3g4h5"
down_revision = "y9c0d1e2f3g4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_contacts_org_normalized_email
            ON contacts (organization_id, lower(btrim(email)))
            """
        )
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS
                ix_emails_org_normalized_recipient_sent_at
            ON emails (organization_id, lower(btrim(to_email)), sent_at DESC)
            """
        )
        op.create_index(
            "ix_emails_org_contact_sent_at",
            "emails",
            ["organization_id", "contact_id", "sent_at"],
            postgresql_concurrently=True,
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(
            "ix_emails_org_contact_sent_at",
            table_name="emails",
            postgresql_concurrently=True,
            if_exists=True,
        )
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_emails_org_normalized_recipient_sent_at"
        )
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_contacts_org_normalized_email")
