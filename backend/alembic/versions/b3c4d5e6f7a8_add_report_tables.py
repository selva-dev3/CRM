"""add report tables (report_exports, custom_reports, scheduled_reports)

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-08-23 23:25:00.000000

Adoption-safe: databases whose schema was previously created by the
application's ``Base.metadata.create_all`` startup hook (development mode
in ``app/main.py``) already contain these tables outside Alembic. For
those databases this migration verifies the existing structure and skips
re-creation, so migration state can be reconciled without data loss.
If an existing table shows real structural drift (missing columns,
missing PK/FK), the migration raises instead of silently stamping a
drifted schema.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, Sequence[str], None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_REPORT_EXPORTS_COLUMNS = {
    'id', 'organization_id', 'report_type', 'file_format',
    'download_url', 'requested_by', 'created_at',
}
_CUSTOM_REPORTS_COLUMNS = {
    'id', 'organization_id', 'name', 'filters', 'metrics_included', 'created_at',
}
_SCHEDULED_REPORTS_COLUMNS = {
    'id', 'organization_id', 'report_type', 'email', 'frequency',
    'next_run', 'created_at',
}


def _verify_existing_table(inspector: sa.engine.reflection.Inspector,
                           table: str, required_columns: set) -> None:
    """Structurally verify a pre-existing table instead of recreating it.

    Raises RuntimeError on real drift so deployment fails loudly rather
    than stamping an inconsistent schema.
    """
    columns = {c['name'] for c in inspector.get_columns(table)}
    missing = required_columns - columns
    if missing:
        raise RuntimeError(
            f"Table '{table}' already exists but is missing columns "
            f"{sorted(missing)} expected by migration b3c4d5e6f7a8. "
            "Reconcile the existing schema with an ALTER migration before "
            "stamping."
        )

    pk = inspector.get_pk_constraint(table)
    if 'id' not in (pk.get('constrained_columns') or []):
        raise RuntimeError(
            f"Table '{table}' already exists but has no primary key on "
            "'id' as required by migration b3c4d5e6f7a8."
        )

    fk_targets = {
        (tuple(fk.get('constrained_columns') or ()), fk.get('referred_table'))
        for fk in inspector.get_foreign_keys(table)
    }
    expected_fks = [(('organization_id',), 'organizations')]
    if table == 'report_exports':
        expected_fks.append((('requested_by',), 'users'))
    for constrained, referred in expected_fks:
        if (constrained, referred) not in fk_targets:
            raise RuntimeError(
                f"Table '{table}' already exists but is missing foreign "
                f"key {'/'.join(constrained)} -> {referred}(id) required "
                "by migration b3c4d5e6f7a8."
            )

    index_names = {idx['name'] for idx in inspector.get_indexes(table)}
    org_index = op.f(f'ix_{table}_organization_id')
    if org_index not in index_names:
        op.create_index(org_index, table, ['organization_id'], unique=False)


def upgrade() -> None:
    """Create report_exports, custom_reports, and scheduled_reports tables."""
    inspector = sa.inspect(op.get_bind())
    existing = set(inspector.get_table_names())

    # 1. report_exports
    if 'report_exports' not in existing:
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
    else:
        _verify_existing_table(inspector, 'report_exports', _REPORT_EXPORTS_COLUMNS)

    # 2. custom_reports
    if 'custom_reports' not in existing:
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
    else:
        _verify_existing_table(inspector, 'custom_reports', _CUSTOM_REPORTS_COLUMNS)

    # 3. scheduled_reports
    if 'scheduled_reports' not in existing:
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
    else:
        _verify_existing_table(inspector, 'scheduled_reports', _SCHEDULED_REPORTS_COLUMNS)


def downgrade() -> None:
    """Drop report tables in reverse order."""
    op.drop_index(op.f('ix_scheduled_reports_organization_id'), table_name='scheduled_reports')
    op.drop_table('scheduled_reports')

    op.drop_index(op.f('ix_custom_reports_organization_id'), table_name='custom_reports')
    op.drop_table('custom_reports')

    op.drop_index(op.f('ix_report_exports_organization_id'), table_name='report_exports')
    op.drop_table('report_exports')
