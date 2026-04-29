"""enhance_audit_log_fields

Revision ID: n8o9p0q1r2s3
Revises: m7n8o9p0q1r2
Create Date: 2024-01-17 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'n8o9p0q1r2s3'
down_revision: Union[str, None] = 'm7n8o9p0q1r2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add enhanced audit fields for comprehensive security logging."""
    # Add new columns
    op.add_column('admin_action_logs', sa.Column('category', sa.String(32), nullable=False, server_default='user_mgmt'))
    op.add_column('admin_action_logs', sa.Column('severity', sa.String(16), nullable=False, server_default='medium'))
    op.add_column('admin_action_logs', sa.Column('entity_type', sa.String(64), nullable=True))
    op.add_column('admin_action_logs', sa.Column('entity_id', sa.String(26), nullable=True))
    op.add_column('admin_action_logs', sa.Column('before_state', sa.JSON(), nullable=False, server_default='{}'))
    op.add_column('admin_action_logs', sa.Column('after_state', sa.JSON(), nullable=False, server_default='{}'))
    op.add_column('admin_action_logs', sa.Column('ip_address', sa.String(45), nullable=True))
    op.add_column('admin_action_logs', sa.Column('user_agent', sa.String(512), nullable=True))
    
    # Add indexes for new columns
    op.create_index('ix_admin_action_logs_category', 'admin_action_logs', ['category'])
    op.create_index('ix_admin_action_logs_severity', 'admin_action_logs', ['severity'])
    op.create_index('ix_admin_action_logs_entity_type', 'admin_action_logs', ['entity_type'])
    op.create_index('ix_admin_action_logs_entity_id', 'admin_action_logs', ['entity_id'])
    op.create_index('ix_admin_action_logs_entity', 'admin_action_logs', ['entity_type', 'entity_id'])
    op.create_index('ix_admin_action_logs_security', 'admin_action_logs', ['category', 'severity', 'created_at'])


def downgrade() -> None:
    """Remove enhanced audit fields."""
    op.drop_index('ix_admin_action_logs_security', table_name='admin_action_logs')
    op.drop_index('ix_admin_action_logs_entity', table_name='admin_action_logs')
    op.drop_index('ix_admin_action_logs_entity_id', table_name='admin_action_logs')
    op.drop_index('ix_admin_action_logs_entity_type', table_name='admin_action_logs')
    op.drop_index('ix_admin_action_logs_severity', table_name='admin_action_logs')
    op.drop_index('ix_admin_action_logs_category', table_name='admin_action_logs')
    
    op.drop_column('admin_action_logs', 'user_agent')
    op.drop_column('admin_action_logs', 'ip_address')
    op.drop_column('admin_action_logs', 'after_state')
    op.drop_column('admin_action_logs', 'before_state')
    op.drop_column('admin_action_logs', 'entity_id')
    op.drop_column('admin_action_logs', 'entity_type')
    op.drop_column('admin_action_logs', 'severity')
    op.drop_column('admin_action_logs', 'category')
