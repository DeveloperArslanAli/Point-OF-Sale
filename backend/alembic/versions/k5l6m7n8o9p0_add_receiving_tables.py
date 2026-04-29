"""Add purchase order receiving tables

Revision ID: k5l6m7n8o9p0
Revises: j4k5l6m7n8o9
Create Date: 2025-12-12 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "k5l6m7n8o9p0"
down_revision: Union[str, None] = "j4k5l6m7n8o9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    receiving_status_enum = postgresql.ENUM(
        "pending", "partial", "complete", "complete_with_exceptions", "cancelled",
        name="receiving_status",
        create_type=False,
    )
    receiving_status_enum.create(op.get_bind(), checkfirst=True)

    receiving_exception_type_enum = postgresql.ENUM(
        "partial_delivery", "over_delivery", "damaged", "missing", "wrong_item", "quality_issue",
        name="receiving_exception_type",
        create_type=False,
    )
    receiving_exception_type_enum.create(op.get_bind(), checkfirst=True)

    # Create purchase_order_receivings table
    op.create_table(
        "purchase_order_receivings",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("purchase_order_id", sa.String(26), nullable=False),
        
        # Status
        sa.Column("status", receiving_status_enum, nullable=False, server_default="pending"),
        
        # Timestamps
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        
        # Receiver info
        sa.Column("received_by_user_id", sa.String(26), nullable=True),
        
        # Notes
        sa.Column("notes", sa.Text(), nullable=True),
        
        # Foreign keys
        sa.ForeignKeyConstraint(["purchase_order_id"], ["purchase_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["received_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    
    op.create_index("ix_po_receivings_purchase_order_id", "purchase_order_receivings", ["purchase_order_id"])
    op.create_index("ix_po_receivings_status", "purchase_order_receivings", ["status"])
    op.create_index("ix_po_receivings_received_at", "purchase_order_receivings", ["received_at"])

    # Create receiving_line_items table
    op.create_table(
        "receiving_line_items",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("receiving_id", sa.String(26), nullable=False),
        sa.Column("purchase_order_item_id", sa.String(26), nullable=False),
        sa.Column("product_id", sa.String(26), nullable=False),
        
        # Quantities
        sa.Column("quantity_ordered", sa.Integer(), nullable=False),
        sa.Column("quantity_received", sa.Integer(), nullable=False),
        sa.Column("quantity_damaged", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quantity_accepted", sa.Integer(), nullable=False),
        
        # Exception tracking
        sa.Column("exception_type", receiving_exception_type_enum, nullable=True),
        sa.Column("exception_notes", sa.Text(), nullable=True),
        
        # Timestamps
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        
        # Foreign keys
        sa.ForeignKeyConstraint(["receiving_id"], ["purchase_order_receivings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["purchase_order_item_id"], ["purchase_order_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
    )
    
    op.create_index("ix_receiving_line_items_receiving_id", "receiving_line_items", ["receiving_id"])
    op.create_index("ix_receiving_line_items_product_id", "receiving_line_items", ["product_id"])
    op.create_index("ix_receiving_line_items_exception_type", "receiving_line_items", ["exception_type"])


def downgrade() -> None:
    op.drop_index("ix_receiving_line_items_exception_type")
    op.drop_index("ix_receiving_line_items_product_id")
    op.drop_index("ix_receiving_line_items_receiving_id")
    op.drop_table("receiving_line_items")
    
    op.drop_index("ix_po_receivings_received_at")
    op.drop_index("ix_po_receivings_status")
    op.drop_index("ix_po_receivings_purchase_order_id")
    op.drop_table("purchase_order_receivings")
    
    # Drop enum types
    op.execute("DROP TYPE IF EXISTS receiving_exception_type")
    op.execute("DROP TYPE IF EXISTS receiving_status")
