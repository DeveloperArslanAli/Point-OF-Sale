"""create_receipts_table

Revision ID: e8d28c25aa2b
Revises: 3213c39da6e6
Create Date: 2025-12-06 20:36:48.499712

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8d28c25aa2b'
down_revision: Union[str, None] = '3213c39da6e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'receipts',
        sa.Column('id', sa.String(26), nullable=False),
        sa.Column('sale_id', sa.String(26), nullable=False),
        sa.Column('receipt_number', sa.String(50), nullable=False),
        sa.Column('store_name', sa.String(200), nullable=False),
        sa.Column('store_address', sa.Text, nullable=False),
        sa.Column('store_phone', sa.String(20), nullable=False),
        sa.Column('store_tax_id', sa.String(50), nullable=True),
        sa.Column('cashier_name', sa.String(200), nullable=False),
        sa.Column('customer_name', sa.String(200), nullable=True),
        sa.Column('customer_email', sa.String(255), nullable=True),
        sa.Column('line_items', sa.JSON, nullable=False),
        sa.Column('payments', sa.JSON, nullable=False),
        sa.Column('totals', sa.JSON, nullable=False),
        sa.Column('sale_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('tax_rate', sa.Numeric(10, 4), nullable=False),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('footer_message', sa.String(500), nullable=True),
        sa.Column('format_type', sa.String(20), nullable=False, server_default='thermal'),
        sa.Column('locale', sa.String(10), nullable=False, server_default='en_US'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('version', sa.Integer, nullable=False, server_default='1'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('ix_receipts_sale_id', 'receipts', ['sale_id'], unique=True)
    op.create_index('ix_receipts_receipt_number', 'receipts', ['receipt_number'], unique=True)
    op.create_index('ix_receipts_sale_date', 'receipts', ['sale_date'])


def downgrade() -> None:
    op.drop_index('ix_receipts_sale_date', 'receipts')
    op.drop_index('ix_receipts_receipt_number', 'receipts')
    op.drop_index('ix_receipts_sale_id', 'receipts')
    op.drop_table('receipts')
