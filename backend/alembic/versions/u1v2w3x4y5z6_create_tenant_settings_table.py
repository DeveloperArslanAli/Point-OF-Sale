"""Create tenant_settings table.

Revision ID: u1v2w3x4y5z6
Revises: t1u2v3w4x5y6
Create Date: 2025-12-24 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "u1v2w3x4y5z6"
down_revision = "t1u2v3w4x5y6"  # Links to the last migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create tenant_settings table."""
    op.create_table(
        "tenant_settings",
        # Primary Key
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(26),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
            index=True,
        ),
        
        # Branding Settings
        sa.Column("logo_url", sa.String(500), nullable=True),
        sa.Column("logo_dark_url", sa.String(500), nullable=True),
        sa.Column("favicon_url", sa.String(500), nullable=True),
        sa.Column("primary_color", sa.String(7), nullable=False, server_default="#6366f1"),
        sa.Column("secondary_color", sa.String(7), nullable=False, server_default="#8b5cf6"),
        sa.Column("accent_color", sa.String(7), nullable=False, server_default="#bb86fc"),
        sa.Column("background_color", sa.String(7), nullable=False, server_default="#1a1c1e"),
        sa.Column("surface_color", sa.String(7), nullable=False, server_default="#2d3033"),
        sa.Column("company_name", sa.String(255), nullable=False, server_default=""),
        sa.Column("company_tagline", sa.String(255), nullable=True),
        sa.Column("company_address", sa.Text, nullable=True),
        sa.Column("company_phone", sa.String(50), nullable=True),
        sa.Column("company_email", sa.String(255), nullable=True),
        sa.Column("company_website", sa.String(255), nullable=True),
        sa.Column("business_registration_number", sa.String(100), nullable=True),
        sa.Column("tax_registration_number", sa.String(100), nullable=True),
        
        # Currency Settings
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("currency_symbol", sa.String(5), nullable=False, server_default="$"),
        sa.Column("currency_position", sa.String(10), nullable=False, server_default="before"),
        sa.Column("decimal_places", sa.Integer, nullable=False, server_default="2"),
        sa.Column("thousand_separator", sa.String(1), nullable=False, server_default=","),
        sa.Column("decimal_separator", sa.String(1), nullable=False, server_default="."),
        
        # Locale Settings
        sa.Column("timezone", sa.String(50), nullable=False, server_default="UTC"),
        sa.Column("date_format", sa.String(20), nullable=False, server_default="YYYY-MM-DD"),
        sa.Column("time_format", sa.String(5), nullable=False, server_default="24h"),
        sa.Column("first_day_of_week", sa.Integer, nullable=False, server_default="1"),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        
        # Tax Settings
        sa.Column("default_tax_rate", sa.Numeric(5, 4), nullable=False, server_default="0.0000"),
        sa.Column("tax_inclusive_pricing", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("show_tax_breakdown", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("tax_rates", sa.JSON, nullable=False, server_default="[]"),
        
        # Invoice Settings
        sa.Column("invoice_prefix", sa.String(10), nullable=False, server_default="INV"),
        sa.Column("invoice_number_length", sa.Integer, nullable=False, server_default="6"),
        sa.Column("invoice_header_text", sa.Text, nullable=True),
        sa.Column("invoice_footer_text", sa.Text, nullable=True),
        sa.Column(
            "receipt_footer_message",
            sa.String(500),
            nullable=False,
            server_default="Thank you for your business!",
        ),
        sa.Column("show_logo_on_receipt", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("show_logo_on_invoice", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("show_payment_instructions", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("payment_instructions", sa.Text, nullable=True),
        sa.Column("terms_and_conditions", sa.Text, nullable=True),
        
        # Theme Settings
        sa.Column("theme_mode", sa.String(10), nullable=False, server_default="dark"),
        sa.Column("custom_css", sa.Text, nullable=True),
        sa.Column("font_family", sa.String(50), nullable=False, server_default="Roboto"),
        sa.Column("border_radius", sa.Integer, nullable=False, server_default="10"),
        
        # Audit Fields
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    )
    
    # Create index for fast lookups
    op.create_index("ix_tenant_settings_tenant_id", "tenant_settings", ["tenant_id"], unique=True)


def downgrade() -> None:
    """Drop tenant_settings table."""
    op.drop_index("ix_tenant_settings_tenant_id", table_name="tenant_settings")
    op.drop_table("tenant_settings")
