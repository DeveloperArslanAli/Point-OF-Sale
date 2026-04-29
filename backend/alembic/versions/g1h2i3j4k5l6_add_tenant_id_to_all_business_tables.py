"""Add tenant_id to all business tables for multi-tenant isolation.

Revision ID: g1h2i3j4k5l6
Revises: f8a1b2c3d4e5
Create Date: 2024-12-12 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g1h2i3j4k5l6'
down_revision = 'f8a1b2c3d4e5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add tenant_id column to all business entity tables."""
    
    # Tables that need tenant_id for multi-tenant isolation
    tables_with_tenant = [
        'products',
        'categories',
        'customers',
        'suppliers',
        'sales',
        'sale_items',
        'inventory_movements',
        'promotions',
        'gift_cards',
        'purchase_orders',
        'purchase_order_items',
        'returns',
        'return_items',
        'employees',
        'employee_bonuses',
        'salary_history',
        'cash_drawers',
        'shifts',
        'receipts',
        'payments',
        'product_import_jobs',
        'product_import_items',
    ]
    
    for table in tables_with_tenant:
        # Check if table exists before adding column
        try:
            op.add_column(
                table,
                sa.Column('tenant_id', sa.String(26), nullable=True, index=True)
            )
            # Create index for tenant filtering performance
            op.create_index(f'ix_{table}_tenant_id', table, ['tenant_id'])
        except Exception:
            # Table might not exist in some environments
            pass


def downgrade() -> None:
    """Remove tenant_id column from all business entity tables."""
    tables_with_tenant = [
        'products',
        'categories',
        'customers',
        'suppliers',
        'sales',
        'sale_items',
        'inventory_movements',
        'promotions',
        'gift_cards',
        'purchase_orders',
        'purchase_order_items',
        'returns',
        'return_items',
        'employees',
        'employee_bonuses',
        'salary_history',
        'cash_drawers',
        'shifts',
        'receipts',
        'payments',
        'product_import_jobs',
        'product_import_items',
    ]
    
    for table in tables_with_tenant:
        try:
            op.drop_index(f'ix_{table}_tenant_id', table_name=table)
            op.drop_column(table, 'tenant_id')
        except Exception:
            pass
