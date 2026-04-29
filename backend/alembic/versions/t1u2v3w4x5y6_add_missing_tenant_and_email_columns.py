"""Add missing tenant_id columns and customer email_hash.

Revision ID: t1u2v3w4x5y6
Revises: q2r3s4t5u6v7
Create Date: 2025-12-19 10:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "t1u2v3w4x5y6"
down_revision = "q2r3s4t5u6v7"
branch_labels = None
depends_on = None


def _table_exists(inspector, table: str) -> bool:
    return table in inspector.get_table_names()


def _column_exists(inspector, table: str, column: str) -> bool:
    return column in [c["name"] for c in inspector.get_columns(table)]


def _index_exists(inspector, table: str, index_name: str) -> bool:
    return index_name in [idx["name"] for idx in inspector.get_indexes(table)]


def _add_column_if_missing(table: str, column: sa.Column, create_index: bool = False) -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    if not _table_exists(insp, table):
        return
    if _column_exists(insp, table, column.name):
        return

    op.add_column(table, column)

    if create_index:
        idx_name = f"ix_{table}_{column.name}"
        if not _index_exists(insp, table, idx_name):
            op.create_index(idx_name, table, [column.name])


def upgrade() -> None:
    # Business tables needing tenant_id for multi-tenant isolation
    tables_with_tenant = [
        "products",
        "categories",
        "customers",
        "suppliers",
        "sales",
        "sale_items",
        "inventory_movements",
        "promotions",
        "gift_cards",
        "purchase_orders",
        "purchase_order_items",
        "returns",
        "return_items",
        "employees",
        "employee_bonuses",
        "salary_history",
        "cash_drawers",
        "shifts",
        "receipts",
        "payments",
        "product_import_jobs",
        "product_import_items",
    ]

    tenant_col = sa.Column("tenant_id", sa.String(length=26), nullable=True)

    for table in tables_with_tenant:
        _add_column_if_missing(table, tenant_col.copy(), create_index=True)

    # Customer email hashing support for encrypted lookup
    _add_column_if_missing(
        "customers",
        sa.Column("email_hash", sa.String(length=64), nullable=True, unique=True),
        create_index=True,
    )


def downgrade() -> None:
    # Drop email_hash index/column if present
    bind = op.get_bind()
    insp = inspect(bind)

    if _table_exists(insp, "customers"):
        if _index_exists(insp, "customers", "ix_customers_email_hash"):
            op.drop_index("ix_customers_email_hash", table_name="customers")
        if _column_exists(insp, "customers", "email_hash"):
            op.drop_column("customers", "email_hash")

    tables_with_tenant = [
        "product_import_items",
        "product_import_jobs",
        "payments",
        "receipts",
        "shifts",
        "cash_drawers",
        "salary_history",
        "employee_bonuses",
        "employees",
        "return_items",
        "returns",
        "purchase_order_items",
        "purchase_orders",
        "gift_cards",
        "promotions",
        "inventory_movements",
        "sale_items",
        "sales",
        "suppliers",
        "customers",
        "categories",
        "products",
    ]

    for table in tables_with_tenant:
        if not _table_exists(insp, table):
            continue
        idx_name = f"ix_{table}_tenant_id"
        if _index_exists(insp, table, idx_name):
            op.drop_index(idx_name, table_name=table)
        if _column_exists(insp, table, "tenant_id"):
            op.drop_column(table, "tenant_id")
