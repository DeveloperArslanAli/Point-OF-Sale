"""Add product_supplier_links table for explicit cost/lead time overrides

Revision ID: j4k5l6m7n8o9
Revises: 4ae8e28625e1
Create Date: 2025-12-12 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "j4k5l6m7n8o9"
down_revision: Union[str, None] = "4ae8e28625e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create product_supplier_links table for explicit product-supplier relationships
    op.create_table(
        "product_supplier_links",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("product_id", sa.String(26), nullable=False),
        sa.Column("supplier_id", sa.String(26), nullable=False),
        
        # Cost information
        sa.Column("unit_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("minimum_order_quantity", sa.Integer(), nullable=False, server_default="1"),
        
        # Lead time
        sa.Column("lead_time_days", sa.Integer(), nullable=False, server_default="7"),
        
        # Supplier ranking (lower = preferred)
        sa.Column("priority", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_preferred", sa.Boolean(), nullable=False, server_default="false"),
        
        # Status
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        
        # Notes
        sa.Column("notes", sa.Text(), nullable=True),
        
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        
        # Foreign keys
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], ondelete="CASCADE"),
        
        # Unique constraint for product-supplier combination
        sa.UniqueConstraint("product_id", "supplier_id", name="uq_product_supplier_link"),
    )
    
    # Create indexes
    op.create_index("ix_product_supplier_links_product_id", "product_supplier_links", ["product_id"])
    op.create_index("ix_product_supplier_links_supplier_id", "product_supplier_links", ["supplier_id"])
    op.create_index("ix_product_supplier_links_is_preferred", "product_supplier_links", ["is_preferred"])
    op.create_index("ix_product_supplier_links_priority", "product_supplier_links", ["priority"])


def downgrade() -> None:
    op.drop_index("ix_product_supplier_links_priority")
    op.drop_index("ix_product_supplier_links_is_preferred")
    op.drop_index("ix_product_supplier_links_supplier_id")
    op.drop_index("ix_product_supplier_links_product_id")
    op.drop_table("product_supplier_links")
