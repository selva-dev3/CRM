"""Migrate active AI provider configuration from OpenRouter to Susanoox."""

from alembic import op

revision = "w7a8b9c0d1e2"
down_revision = "v6f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE ai_organization_configs
        SET provider = 'susanoox',
            model_name = 'susanoox-fast',
            updated_at = now()
        WHERE lower(btrim(provider)) = 'openrouter'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE ai_organization_configs
        SET provider = 'openrouter',
            model_name = 'minimax/minimax-m3:free',
            updated_at = now()
        WHERE lower(btrim(provider)) = 'susanoox'
          AND model_name IN ('susanoox-fast', 'susanoox-large')
        """
    )
