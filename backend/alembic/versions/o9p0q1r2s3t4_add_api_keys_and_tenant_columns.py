"""Add API keys table and tenant_id to shift/cash_drawer

Revision ID: o9p0q1r2s3t4
Revises: n8o9p0q1r2s3
Create Date: 2025-12-12

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'o9p0q1r2s3t4'
down_revision = 'n8o9p0q1r2s3'
branch_labels = None
depends_on = None


def upgrade():
    # Create api_keys table
    op.create_table(
        'api_keys',
        sa.Column('id', sa.String(26), primary_key=True),
        sa.Column('tenant_id', sa.String(26), nullable=False, index=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('key_prefix', sa.String(8), nullable=False, unique=True, index=True),
        sa.Column('key_hash', sa.String(256), nullable=False),
        sa.Column('scopes', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('rate_limit_per_minute', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('status', sa.String(20), nullable=False, server_default='active', index=True),
        sa.Column('created_by', sa.String(26), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_by', sa.String(26), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='0'),
    )
    
    # Add tenant_id to shifts table
    op.add_column('shifts', sa.Column('tenant_id', sa.String(26), nullable=True))
    op.create_index('ix_shifts_tenant_id', 'shifts', ['tenant_id'])
    
    # Add tenant_id to cash_drawer_sessions table
    op.add_column('cash_drawer_sessions', sa.Column('tenant_id', sa.String(26), nullable=True))
    op.create_index('ix_cash_drawer_sessions_tenant_id', 'cash_drawer_sessions', ['tenant_id'])


def downgrade():
    # Remove tenant_id from cash_drawer_sessions
    op.drop_index('ix_cash_drawer_sessions_tenant_id', 'cash_drawer_sessions')
    op.drop_column('cash_drawer_sessions', 'tenant_id')
    
    # Remove tenant_id from shifts
    op.drop_index('ix_shifts_tenant_id', 'shifts')
    op.drop_column('shifts', 'tenant_id')
    
    # Drop api_keys table
    op.drop_table('api_keys')
