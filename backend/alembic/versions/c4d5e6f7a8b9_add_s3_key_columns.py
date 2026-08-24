"""add s3_key columns and relax legacy URL columns for report_exports and documents

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-08-24 12:00:00.000000

Adoption-safe: databases whose schema was previously created by the
application's ``Base.metadata.create_all`` startup hook (development mode
in ``app/main.py``) may already contain these columns. Existing state is
inspected first; each DDL step is applied only when missing, with no data
destructive operations.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _ensure_s3_key(inspector: sa.engine.reflection.Inspector, table: str,
                   url_column: str) -> None:
    """Add stable s3_key column + index and relax the legacy URL column."""
    columns = {c['name']: c for c in inspector.get_columns(table)}

    if 's3_key' not in columns:
        op.add_column(table, sa.Column('s3_key', sa.String(length=1024), nullable=True))

    if url_column in columns and not columns[url_column]['nullable']:
        op.alter_column(
            table,
            url_column,
            existing_type=sa.String(length=500),
            nullable=True,
        )

    index_names = {idx['name'] for idx in inspector.get_indexes(table)}
    s3_index = op.f(f'ix_{table}_s3_key')
    if s3_index not in index_names:
        op.create_index(s3_index, table, ['s3_key'], unique=False)


def upgrade() -> None:
    """Add nullable s3_key columns and relax legacy URL columns."""
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    # report_exports: stable object key, plus make legacy presigned-URL column nullable
    if 'report_exports' in tables:
        _ensure_s3_key(inspector, 'report_exports', 'download_url')

    # documents: stable object key, plus make legacy presigned-URL column nullable
    if 'documents' in tables:
        _ensure_s3_key(inspector, 'documents', 'file_url')


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
