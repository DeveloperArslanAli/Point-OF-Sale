"""create_payments_table

Revision ID: 2a7bd182147b
Revises: a69fcc420eab
Create Date: 2025-12-06 17:24:45.651799

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2a7bd182147b'
down_revision: Union[str, None] = 'a69fcc420eab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'payments',
        sa.Column('id', sa.String(length=26), nullable=False),
        sa.Column('sale_id', sa.String(length=26), nullable=False),
        sa.Column('method', sa.String(length=50), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('provider_transaction_id', sa.String(length=255), nullable=True),
        sa.Column('provider_metadata', sa.JSON(), nullable=True),
        sa.Column('card_last4', sa.String(length=4), nullable=True),
        sa.Column('card_brand', sa.String(length=50), nullable=True),
        sa.Column('authorized_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('captured_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('refunded_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('refunded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('created_by', sa.String(length=26), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.CheckConstraint('amount > 0', name='ck_payments_amount_positive'),
        sa.CheckConstraint('refunded_amount >= 0', name='ck_payments_refunded_amount_positive'),
        sa.CheckConstraint('refunded_amount <= amount', name='ck_payments_refunded_amount_lte_amount'),
        sa.ForeignKeyConstraint(['sale_id'], ['sales.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_payments_sale_id', 'payments', ['sale_id'])
    op.create_index('ix_payments_status', 'payments', ['status'])
    op.create_index('ix_payments_provider_transaction_id', 'payments', ['provider_transaction_id'])
    op.create_index('ix_payments_created_at', 'payments', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_payments_created_at', table_name='payments')
    op.drop_index('ix_payments_provider_transaction_id', table_name='payments')
    op.drop_index('ix_payments_status', table_name='payments')
    op.drop_index('ix_payments_sale_id', table_name='payments')
    op.drop_table('payments')
