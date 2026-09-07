"""Add authentication session families and lifecycle metadata.

Existing authentication rows are preserved. Existing refresh records receive
one family identifier per row because their historical lineage is unknown.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "s3c4d5e6f7a8"
down_revision: str | Sequence[str] | None = "r1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_sessions", sa.Column("family_id", sa.String(length=36), nullable=True))
    op.add_column("user_sessions", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("user_sessions", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("user_sessions", sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column("refresh_tokens", sa.Column("family_id", sa.String(length=36), nullable=True))
    op.add_column("refresh_tokens", sa.Column("generation", sa.Integer(), nullable=True))
    op.add_column("refresh_tokens", sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("refresh_tokens", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("refresh_tokens", sa.Column("replaced_by", sa.String(length=36), nullable=True))

    op.execute(sa.text("UPDATE refresh_tokens SET family_id = id WHERE family_id IS NULL"))
    op.execute(sa.text("UPDATE refresh_tokens SET generation = 0 WHERE generation IS NULL"))
    op.execute(sa.text("UPDATE refresh_tokens SET absolute_expires_at = expires_at WHERE absolute_expires_at IS NULL"))
    op.alter_column("refresh_tokens", "family_id", nullable=False)
    op.alter_column("refresh_tokens", "generation", nullable=False, server_default="0")

    op.create_index("ix_user_sessions_family_id", "user_sessions", ["family_id"])
    op.create_index("ix_user_sessions_expires_at", "user_sessions", ["expires_at"])
    op.create_index("ix_user_sessions_revoked_at", "user_sessions", ["revoked_at"])
    op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])
    op.create_index("ix_refresh_tokens_absolute_expires_at", "refresh_tokens", ["absolute_expires_at"])
    op.create_index("ix_refresh_tokens_revoked_at", "refresh_tokens", ["revoked_at"])


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_revoked_at", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_absolute_expires_at", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_family_id", table_name="refresh_tokens")
    op.drop_index("ix_user_sessions_revoked_at", table_name="user_sessions")
    op.drop_index("ix_user_sessions_expires_at", table_name="user_sessions")
    op.drop_index("ix_user_sessions_family_id", table_name="user_sessions")
    op.drop_column("refresh_tokens", "replaced_by")
    op.drop_column("refresh_tokens", "revoked_at")
    op.drop_column("refresh_tokens", "absolute_expires_at")
    op.drop_column("refresh_tokens", "generation")
    op.drop_column("refresh_tokens", "family_id")
    op.drop_column("user_sessions", "last_used_at")
    op.drop_column("user_sessions", "revoked_at")
    op.drop_column("user_sessions", "expires_at")
    op.drop_column("user_sessions", "family_id")
