"""create_sale_payments_table

Revision ID: 7334b3c4522e
Revises: e8d28c25aa2b
Create Date: 2025-12-06 21:05:27.664608

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7334b3c4522e'
down_revision: Union[str, None] = 'e8d28c25aa2b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'sale_payments',
        sa.Column('id', sa.String(26), nullable=False),
        sa.Column('sale_id', sa.String(26), nullable=False),
        sa.Column('payment_method', sa.String(50), nullable=False),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False),
        sa.Column('reference_number', sa.String(100), nullable=True),
        sa.Column('card_last_four', sa.String(4), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['sale_id'], ['sales.id'], ondelete='CASCADE'),
    )
    
    # Create indexes
    op.create_index('ix_sale_payments_sale_id', 'sale_payments', ['sale_id'])
    op.create_index('ix_sale_payments_payment_method', 'sale_payments', ['payment_method'])


def downgrade() -> None:
    op.drop_index('ix_sale_payments_payment_method', 'sale_payments')
    op.drop_index('ix_sale_payments_sale_id', 'sale_payments')
    op.drop_table('sale_payments')
