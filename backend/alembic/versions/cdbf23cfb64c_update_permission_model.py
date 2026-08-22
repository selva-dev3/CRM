"""update permission model

Revision ID: cdbf23cfb64c
Revises: 39346817277b
Create Date: 2026-08-05 14:21:09.223832

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cdbf23cfb64c'
down_revision: Union[str, Sequence[str], None] = "39346817277b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema safely checking column existence."""
    conn = op.get_bind()
    try:
        inspector = sa.inspect(conn)
        existing_columns = [c['name'] for c in inspector.get_columns('permissions')]
        existing_indexes = [i['name'] for i in inspector.get_indexes('permissions')]
    except Exception:
        existing_columns = []
        existing_indexes = []

    if 'key' not in existing_columns:
        op.add_column('permissions', sa.Column('key', sa.String(length=150), nullable=False, server_default=''))
    if 'name' not in existing_columns:
        op.add_column('permissions', sa.Column('name', sa.String(length=150), nullable=False, server_default='Permission'))
    if 'category' not in existing_columns:
        op.add_column('permissions', sa.Column('category', sa.String(length=100), nullable=False, server_default='General'))

    if 'ix_permissions_module' in existing_indexes:
        try:
            op.drop_index('ix_permissions_module', table_name='permissions')
        except Exception:
            pass
    if 'ix_permissions_category' not in existing_indexes:
        try:
            op.create_index('ix_permissions_category', 'permissions', ['category'], unique=False)
        except Exception:
            pass
    if 'ix_permissions_key' not in existing_indexes:
        try:
            op.create_index('ix_permissions_key', 'permissions', ['key'], unique=True)
        except Exception:
            pass

    if 'module' in existing_columns:
        try:
            op.drop_column('permissions', 'module')
        except Exception:
            pass
    if 'action' in existing_columns:
        try:
            op.drop_column('permissions', 'action')
        except Exception:
            pass


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    try:
        inspector = sa.inspect(conn)
        existing_columns = [c['name'] for c in inspector.get_columns('permissions')]
    except Exception:
        existing_columns = []

    if 'action' not in existing_columns:
        op.add_column('permissions', sa.Column('action', sa.VARCHAR(length=100), autoincrement=False, nullable=True))
    if 'module' not in existing_columns:
        op.add_column('permissions', sa.Column('module', sa.VARCHAR(length=100), autoincrement=False, nullable=True))
