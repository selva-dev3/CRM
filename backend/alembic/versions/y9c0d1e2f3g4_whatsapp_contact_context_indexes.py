"""Add contact-context lookup indexes without blocking table writes."""

from alembic import op

revision = "y9c0d1e2f3g4"
down_revision = "x8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.create_index(
            "ix_deals_org_contact",
            "deals",
            ["organization_id", "contact_id"],
            postgresql_concurrently=True,
            if_not_exists=True,
        )
        op.create_index(
            "ix_quotes_org_contact",
            "quotes",
            ["organization_id", "contact_id"],
            postgresql_concurrently=True,
            if_not_exists=True,
        )
        op.create_index(
            "ix_invoices_org_contact",
            "invoices",
            ["organization_id", "contact_id"],
            postgresql_concurrently=True,
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(
            "ix_invoices_org_contact",
            table_name="invoices",
            postgresql_concurrently=True,
        )
        op.drop_index(
            "ix_quotes_org_contact",
            table_name="quotes",
            postgresql_concurrently=True,
        )
        op.drop_index(
            "ix_deals_org_contact",
            table_name="deals",
            postgresql_concurrently=True,
        )
