"""create_promotions_table

Revision ID: 3213c39da6e6
Revises: 2a7bd182147b
Create Date: 2025-12-06 20:15:09.026502

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3213c39da6e6'
down_revision: Union[str, None] = '2a7bd182147b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'promotions',
        sa.Column('id', sa.String(length=26), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('discount_rule', sa.JSON(), nullable=False),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('usage_limit', sa.Integer(), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('usage_limit_per_customer', sa.Integer(), nullable=True),
        sa.Column('coupon_code', sa.String(length=100), nullable=True),
        sa.Column('is_case_sensitive', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('customer_ids', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('exclude_sale_items', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_combine_with_other_promotions', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('created_by', sa.String(length=26), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_by', sa.String(length=26), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.CheckConstraint('usage_count >= 0', name='ck_promotions_usage_count_positive'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_promotions_coupon_code', 'promotions', ['coupon_code'], unique=True)
    op.create_index('ix_promotions_status', 'promotions', ['status'])
    op.create_index('ix_promotions_start_date', 'promotions', ['start_date'])
    op.create_index('ix_promotions_end_date', 'promotions', ['end_date'])
    op.create_index('ix_promotions_priority', 'promotions', ['priority'])


def downgrade() -> None:
    op.drop_index('ix_promotions_priority', table_name='promotions')
    op.drop_index('ix_promotions_end_date', table_name='promotions')
    op.drop_index('ix_promotions_start_date', table_name='promotions')
    op.drop_index('ix_promotions_status', table_name='promotions')
    op.drop_index('ix_promotions_coupon_code', table_name='promotions')
    op.drop_table('promotions')
