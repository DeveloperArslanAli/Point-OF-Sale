"""Ensure product_supplier_links table exists with tenant/indexes.

Revision ID: r2s3t4u5v6w7
Revises: t1u2v3w4x5y6
Create Date: 2025-12-22 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "r2s3t4u5v6w7"
down_revision: Union[str, None] = "t1u2v3w4x5y6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(insp: sa.Inspector, table: str) -> bool:
    return table in insp.get_table_names()


def _column_exists(insp: sa.Inspector, table: str, column: str) -> bool:
    return column in [c["name"] for c in insp.get_columns(table)]


def _index_exists(insp: sa.Inspector, table: str, index_name: str) -> bool:
    return index_name in [idx["name"] for idx in insp.get_indexes(table)]


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    table_name = "product_supplier_links"

    if not _table_exists(insp, table_name):
        op.create_table(
            table_name,
            sa.Column("id", sa.String(26), primary_key=True),
            sa.Column("tenant_id", sa.String(26), nullable=True, index=True),
            sa.Column("product_id", sa.String(26), nullable=False),
            sa.Column("supplier_id", sa.String(26), nullable=False),
            sa.Column("unit_cost", sa.Numeric(12, 2), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
            sa.Column("minimum_order_quantity", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("lead_time_days", sa.Integer(), nullable=False, server_default="7"),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("is_preferred", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("product_id", "supplier_id", name="uq_product_supplier_link"),
        )

    # Ensure columns / indexes exist (idempotent repair for stamped DBs)
    required_columns = [
        "tenant_id",
        "product_id",
        "supplier_id",
        "unit_cost",
        "currency",
        "minimum_order_quantity",
        "lead_time_days",
        "priority",
        "is_preferred",
        "is_active",
        "notes",
        "created_at",
        "updated_at",
    ]

    if _table_exists(insp, table_name):
        for col in required_columns:
            if not _column_exists(insp, table_name, col):
                # Minimal definition used for backfill; types align with model/migration intent
                if col == "tenant_id":
                    op.add_column(table_name, sa.Column("tenant_id", sa.String(26), nullable=True))
                elif col in {"product_id", "supplier_id"}:
                    op.add_column(table_name, sa.Column(col, sa.String(26), nullable=False))
                elif col == "unit_cost":
                    op.add_column(table_name, sa.Column("unit_cost", sa.Numeric(12, 2), nullable=False, server_default="0"))
                elif col == "currency":
                    op.add_column(table_name, sa.Column("currency", sa.String(3), nullable=False, server_default="USD"))
                elif col == "minimum_order_quantity":
                    op.add_column(table_name, sa.Column("minimum_order_quantity", sa.Integer(), nullable=False, server_default="1"))
                elif col == "lead_time_days":
                    op.add_column(table_name, sa.Column("lead_time_days", sa.Integer(), nullable=False, server_default="7"))
                elif col == "priority":
                    op.add_column(table_name, sa.Column("priority", sa.Integer(), nullable=False, server_default="1"))
                elif col == "is_preferred":
                    op.add_column(table_name, sa.Column("is_preferred", sa.Boolean(), nullable=False, server_default="false"))
                elif col == "is_active":
                    op.add_column(table_name, sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"))
                elif col == "notes":
                    op.add_column(table_name, sa.Column("notes", sa.Text(), nullable=True))
                elif col in {"created_at", "updated_at"}:
                    op.add_column(
                        table_name,
                        sa.Column(
                            col,
                            sa.DateTime(timezone=True),
                            server_default=sa.func.now(),
                            nullable=False,
                        ),
                    )

        # Ensure foreign keys and unique constraint exist (best-effort; safe if already present)
        # Adding FKs conditionally is noisy; rely on table definition when missing.

        index_specs = {
            "ix_product_supplier_links_product_id": ["product_id"],
            "ix_product_supplier_links_supplier_id": ["supplier_id"],
            "ix_product_supplier_links_is_preferred": ["is_preferred"],
            "ix_product_supplier_links_priority": ["priority"],
            "ix_product_supplier_links_tenant_id": ["tenant_id"],
        }

        for idx_name, cols in index_specs.items():
            if not _index_exists(insp, table_name, idx_name):
                op.create_index(idx_name, table_name, cols)


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    table_name = "product_supplier_links"

    index_names = [
        "ix_product_supplier_links_product_id",
        "ix_product_supplier_links_supplier_id",
        "ix_product_supplier_links_is_preferred",
        "ix_product_supplier_links_priority",
        "ix_product_supplier_links_tenant_id",
    ]

    if _table_exists(insp, table_name):
        for idx in index_names:
            if _index_exists(insp, table_name, idx):
                op.drop_index(idx, table_name=table_name)
        op.drop_table(table_name)
