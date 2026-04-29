"""create report builder tables

Revision ID: f8a1b2c3d4e5
Revises: e8d28c25aa2b
Create Date: 2024-01-20 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f8a1b2c3d4e5'
down_revision: Union[str, None] = 'e8d28c25aa2b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create report_definitions table
    op.create_table(
        'report_definitions',
        sa.Column('id', sa.String(26), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, index=True),
        sa.Column('description', sa.Text, nullable=False, server_default=''),
        sa.Column('report_type', sa.String(50), nullable=False, index=True),
        sa.Column('columns', sa.JSON, nullable=False, server_default='[]'),
        sa.Column('filters', sa.JSON, nullable=False, server_default='[]'),
        sa.Column('group_by', sa.JSON, nullable=False, server_default='[]'),
        sa.Column('schedule', sa.JSON, nullable=True),
        sa.Column('default_format', sa.String(20), nullable=False, server_default='json'),
        sa.Column('owner_id', sa.String(26), nullable=True, index=True),
        sa.Column('tenant_id', sa.String(26), nullable=True, index=True),
        sa.Column('is_public', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('version', sa.Integer, nullable=False, server_default='0'),
    )

    # Create report_executions table
    op.create_table(
        'report_executions',
        sa.Column('id', sa.String(26), primary_key=True),
        sa.Column('report_definition_id', sa.String(26), nullable=False, index=True),
        sa.Column('status', sa.String(20), nullable=False, index=True),
        sa.Column('format', sa.String(20), nullable=False),
        sa.Column('parameters', sa.JSON, nullable=False, server_default='{}'),
        sa.Column('result_path', sa.String(500), nullable=True),
        sa.Column('row_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('requested_by', sa.String(26), nullable=True, index=True),
        sa.Column('tenant_id', sa.String(26), nullable=True, index=True),
    )

    # Create indexes for common queries
    op.create_index(
        'ix_report_definitions_tenant_type',
        'report_definitions',
        ['tenant_id', 'report_type'],
    )
    op.create_index(
        'ix_report_executions_definition_status',
        'report_executions',
        ['report_definition_id', 'status'],
    )


def downgrade() -> None:
    op.drop_index('ix_report_executions_definition_status', 'report_executions')
    op.drop_index('ix_report_definitions_tenant_type', 'report_definitions')
    op.drop_table('report_executions')
    op.drop_table('report_definitions')
