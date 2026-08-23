"""add s3_key columns and relax legacy URL columns for report_exports and documents

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-08-24 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add nullable s3_key columns and relax legacy URL columns."""
    # report_exports: stable object key, plus make legacy presigned-URL column nullable
    op.add_column(
        'report_exports',
        sa.Column('s3_key', sa.String(length=1024), nullable=True),
    )
    op.alter_column(
        'report_exports',
        'download_url',
        existing_type=sa.String(length=500),
        nullable=True,
    )
    op.create_index(
        op.f('ix_report_exports_s3_key'),
        'report_exports',
        ['s3_key'],
        unique=False,
    )

    # documents: stable object key, plus make legacy presigned-URL column nullable
    op.add_column(
        'documents',
        sa.Column('s3_key', sa.String(length=1024), nullable=True),
    )
    op.alter_column(
        'documents',
        'file_url',
        existing_type=sa.String(length=500),
        nullable=True,
    )
    op.create_index(
        op.f('ix_documents_s3_key'),
        'documents',
        ['s3_key'],
        unique=False,
    )


def downgrade() -> None:
    """Reverse: drop s3_key columns and restore NOT NULL on legacy URL columns."""
    op.drop_index(op.f('ix_documents_s3_key'), table_name='documents')
    op.drop_column('documents', 's3_key')
    op.alter_column(
        'documents',
        'file_url',
        existing_type=sa.String(length=500),
        nullable=False,
    )

    op.drop_index(op.f('ix_report_exports_s3_key'), table_name='report_exports')
    op.drop_column('report_exports', 's3_key')
    op.alter_column(
        'report_exports',
        'download_url',
        existing_type=sa.String(length=500),
        nullable=False,
    )
