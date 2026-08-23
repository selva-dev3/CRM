"""add report tables (report_exports, custom_reports, scheduled_reports)

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-08-23 23:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, Sequence[str], None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create report_exports, custom_reports, and scheduled_reports tables."""
    # 1. report_exports
    op.create_table(
        'report_exports',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('organization_id', sa.String(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('report_type', sa.String(length=100), nullable=False),
        sa.Column('file_format', sa.String(length=20), server_default='csv', nullable=False),
        sa.Column('download_url', sa.String(length=500), nullable=False),
        sa.Column('requested_by', sa.String(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index(op.f('ix_report_exports_organization_id'), 'report_exports', ['organization_id'], unique=False)

    # 2. custom_reports
    op.create_table(
        'custom_reports',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('organization_id', sa.String(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('filters', sa.Text(), nullable=True),
        sa.Column('metrics_included', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index(op.f('ix_custom_reports_organization_id'), 'custom_reports', ['organization_id'], unique=False)

    # 3. scheduled_reports
    op.create_table(
        'scheduled_reports',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('organization_id', sa.String(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('report_type', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('frequency', sa.String(length=50), server_default='Weekly', nullable=False),
        sa.Column('next_run', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index(op.f('ix_scheduled_reports_organization_id'), 'scheduled_reports', ['organization_id'], unique=False)


def downgrade() -> None:
    """Drop report tables in reverse order."""
    op.drop_index(op.f('ix_scheduled_reports_organization_id'), table_name='scheduled_reports')
    op.drop_table('scheduled_reports')

    op.drop_index(op.f('ix_custom_reports_organization_id'), table_name='custom_reports')
    op.drop_table('custom_reports')

    op.drop_index(op.f('ix_report_exports_organization_id'), table_name='report_exports')
    op.drop_table('report_exports')
