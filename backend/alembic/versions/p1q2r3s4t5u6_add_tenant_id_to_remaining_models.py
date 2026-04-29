"""Add tenant_id to remaining models for multi-tenant RLS.

Revision ID: p1q2r3s4t5u6
Revises: o9p0q1r2s3t4
Create Date: 2025-12-12 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "p1q2r3s4t5u6"
down_revision = "o9p0q1r2s3t4"
branch_labels = None
depends_on = None


def table_exists(table: str) -> bool:
    """Check if a table exists."""
    bind = op.get_bind()
    insp = inspect(bind)
    return table in insp.get_table_names()


def column_exists(table: str, column: str) -> bool:
    """Check if a column exists in a table."""
    bind = op.get_bind()
    insp = inspect(bind)
    columns = [c["name"] for c in insp.get_columns(table)]
    return column in columns


def index_exists(table: str, index_name: str) -> bool:
    """Check if an index exists on a table."""
    bind = op.get_bind()
    insp = inspect(bind)
    indexes = [idx["name"] for idx in insp.get_indexes(table)]
    return index_name in indexes


def add_tenant_id_to_table(table: str) -> None:
    """Add tenant_id column with index to a table if it exists and doesn't have it."""
    if not table_exists(table):
        print(f"  Skipping {table} - table does not exist")
        return
    
    if column_exists(table, "tenant_id"):
        print(f"  Skipping {table} - tenant_id column already exists")
        return
    
    print(f"  Adding tenant_id to {table}")
    op.add_column(table, sa.Column("tenant_id", sa.String(26), nullable=True))
    
    idx_name = f"ix_{table}_tenant_id"
    if not index_exists(table, idx_name):
        op.create_index(idx_name, table, ["tenant_id"])


def upgrade() -> None:
    # Tables that need tenant_id for multi-tenant RLS
    tables = [
        "returns",
        "payments",
        "receipts",
        "product_import_jobs",
        "product_supplier_links",  # May not exist in all deployments
    ]
    
    for table in tables:
        add_tenant_id_to_table(table)


def downgrade() -> None:
    # Tables in reverse order
    tables = [
        "product_supplier_links",
        "product_import_jobs",
        "receipts",
        "payments",
        "returns",
    ]
    
    for table in tables:
        if not table_exists(table):
            continue
        
        idx_name = f"ix_{table}_tenant_id"
        if index_exists(table, idx_name):
            op.drop_index(idx_name, table_name=table)
        if column_exists(table, "tenant_id"):
            op.drop_column(table, "tenant_id")
