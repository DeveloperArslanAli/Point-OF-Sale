"""Create cash drawer and shift tables.

Revision ID: d4f8e2a1b3c5
Revises: 9c3a0d87d812
Create Date: 2025-12-11
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d4f8e2a1b3c5"
down_revision = "9c3a0d87d812"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create cash_drawer_sessions table
    op.create_table(
        "cash_drawer_sessions",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("terminal_id", sa.String(50), nullable=False, index=True),
        sa.Column(
            "opened_by",
            sa.String(26),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "closed_by",
            sa.String(26),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("opening_float", sa.Numeric(12, 2), nullable=False),
        sa.Column("closing_count", sa.Numeric(12, 2), nullable=True),
        sa.Column("expected_balance", sa.Numeric(12, 2), nullable=False),
        sa.Column("over_short", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, default="USD"),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            default="open",
            index=True,
        ),
        sa.Column(
            "opened_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, default=0),
    )

    # Create cash_movements table
    op.create_table(
        "cash_movements",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column(
            "drawer_session_id",
            sa.String(26),
            sa.ForeignKey("cash_drawer_sessions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("movement_type", sa.String(20), nullable=False, index=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, default="USD"),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("reference_id", sa.String(26), nullable=True, index=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Create shifts table
    op.create_table(
        "shifts",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(26),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("terminal_id", sa.String(50), nullable=False, index=True),
        sa.Column(
            "drawer_session_id",
            sa.String(26),
            sa.ForeignKey("cash_drawer_sessions.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            default="active",
            index=True,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        # Opening/closing cash
        sa.Column("opening_cash", sa.Numeric(12, 2), nullable=True),
        sa.Column("closing_cash", sa.Numeric(12, 2), nullable=True),
        # Totals
        sa.Column("total_sales", sa.Numeric(12, 2), nullable=False, default=0),
        sa.Column("total_transactions", sa.Integer, nullable=False, default=0),
        sa.Column("cash_sales", sa.Numeric(12, 2), nullable=False, default=0),
        sa.Column("card_sales", sa.Numeric(12, 2), nullable=False, default=0),
        sa.Column("gift_card_sales", sa.Numeric(12, 2), nullable=False, default=0),
        sa.Column("other_sales", sa.Numeric(12, 2), nullable=False, default=0),
        sa.Column("total_refunds", sa.Numeric(12, 2), nullable=False, default=0),
        sa.Column("refund_count", sa.Integer, nullable=False, default=0),
        sa.Column("currency", sa.String(3), nullable=False, default="USD"),
        sa.Column("version", sa.Integer, nullable=False, default=0),
    )

    # Add shift_id to sales table for binding
    op.add_column(
        "sales",
        sa.Column(
            "shift_id",
            sa.String(26),
            sa.ForeignKey("shifts.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )

    # Create composite indexes for common queries
    op.create_index(
        "ix_cash_drawer_sessions_terminal_status",
        "cash_drawer_sessions",
        ["terminal_id", "status"],
    )
    op.create_index(
        "ix_shifts_user_status",
        "shifts",
        ["user_id", "status"],
    )


def downgrade() -> None:
    # Remove indexes
    op.drop_index("ix_shifts_user_status", table_name="shifts")
    op.drop_index("ix_cash_drawer_sessions_terminal_status", table_name="cash_drawer_sessions")

    # Remove shift_id from sales
    op.drop_column("sales", "shift_id")

    # Drop tables in reverse order
    op.drop_table("shifts")
    op.drop_table("cash_movements")
    op.drop_table("cash_drawer_sessions")
