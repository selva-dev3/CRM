"""merge AI runtime and deal custom field heads

Revision ID: e8f9a0b1c2d3
Revises: d4e5f6a7b8c0, d6e7f8a9b0c1
"""

from collections.abc import Sequence

revision: str = "e8f9a0b1c2d3"
down_revision: str | Sequence[str] | None = (
    "d4e5f6a7b8c0",
    "d6e7f8a9b0c1",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join the two migration branches without applying additional DDL."""


def downgrade() -> None:
    """Split the revision graph back into its two parent heads."""
