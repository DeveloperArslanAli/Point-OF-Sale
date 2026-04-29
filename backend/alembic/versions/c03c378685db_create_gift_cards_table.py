"""create_gift_cards_table

Revision ID: c03c378685db
Revises: 7334b3c4522e
Create Date: 2025-12-06 23:43:08.583009

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c03c378685db'
down_revision: Union[str, None] = '7334b3c4522e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'gift_cards',
        sa.Column('id', sa.String(length=26), nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('initial_balance', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('current_balance', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('issued_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expiry_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('customer_id', sa.String(length=26), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='SET NULL'),
    )
    
    # Create unique index on code for fast lookups and uniqueness
    op.create_index('ix_gift_cards_code', 'gift_cards', ['code'], unique=True)
    
    # Create index on customer_id for customer gift card queries
    op.create_index('ix_gift_cards_customer_id', 'gift_cards', ['customer_id'])
    
    # Create index on status for filtering active/expired cards
    op.create_index('ix_gift_cards_status', 'gift_cards', ['status'])


def downgrade() -> None:
    op.drop_index('ix_gift_cards_status', table_name='gift_cards')
    op.drop_index('ix_gift_cards_customer_id', table_name='gift_cards')
    op.drop_index('ix_gift_cards_code', table_name='gift_cards')
    op.drop_table('gift_cards')
