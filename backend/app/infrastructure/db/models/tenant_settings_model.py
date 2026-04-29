"""SQLAlchemy model for Tenant Settings.

Stores all tenant-level configuration including branding, currency,
locale, tax, invoice, and theme settings.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.session import Base


class TenantSettingsModel(Base):
    """Tenant Settings ORM model.

    Maps to app.domain.tenant_settings.entities.TenantSettings
    """

    __tablename__ = "tenant_settings"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # ===================
    # Branding Settings
    # ===================
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    logo_dark_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    favicon_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Colors (hex format)
    primary_color: Mapped[str] = mapped_column(String(7), nullable=False, default="#6366f1")
    secondary_color: Mapped[str] = mapped_column(String(7), nullable=False, default="#8b5cf6")
    accent_color: Mapped[str] = mapped_column(String(7), nullable=False, default="#bb86fc")
    background_color: Mapped[str] = mapped_column(String(7), nullable=False, default="#1a1c1e")
    surface_color: Mapped[str] = mapped_column(String(7), nullable=False, default="#2d3033")
    
    # Company Identity
    company_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    company_tagline: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    company_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    business_registration_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tax_registration_number: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ===================
    # Currency Settings
    # ===================
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    currency_symbol: Mapped[str] = mapped_column(String(5), nullable=False, default="$")
    currency_position: Mapped[str] = mapped_column(String(10), nullable=False, default="before")
    decimal_places: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    thousand_separator: Mapped[str] = mapped_column(String(1), nullable=False, default=",")
    decimal_separator: Mapped[str] = mapped_column(String(1), nullable=False, default=".")

    # ===================
    # Locale Settings
    # ===================
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="UTC")
    date_format: Mapped[str] = mapped_column(String(20), nullable=False, default="YYYY-MM-DD")
    time_format: Mapped[str] = mapped_column(String(5), nullable=False, default="24h")
    first_day_of_week: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")

    # ===================
    # Tax Settings
    # ===================
    default_tax_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, default=Decimal("0.0000")
    )
    tax_inclusive_pricing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    show_tax_breakdown: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # JSON array of tax rates: [{"name": "VAT", "rate": 0.20, "is_default": true, "applies_to_shipping": false}]
    tax_rates: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # ===================
    # Invoice Settings
    # ===================
    invoice_prefix: Mapped[str] = mapped_column(String(10), nullable=False, default="INV")
    invoice_number_length: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    invoice_header_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    invoice_footer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    receipt_footer_message: Mapped[str] = mapped_column(
        String(500), nullable=False, default="Thank you for your business!"
    )
    show_logo_on_receipt: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    show_logo_on_invoice: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    show_payment_instructions: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    payment_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    terms_and_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ===================
    # Theme Settings
    # ===================
    theme_mode: Mapped[str] = mapped_column(String(10), nullable=False, default="dark")
    custom_css: Mapped[str | None] = mapped_column(Text, nullable=True)
    font_family: Mapped[str] = mapped_column(String(50), nullable=False, default="Roboto")
    border_radius: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    # ===================
    # Audit Fields
    # ===================
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    def __repr__(self) -> str:
        return (
            f"<TenantSettingsModel(id={self.id!r}, tenant_id={self.tenant_id!r}, "
            f"company={self.company_name!r}, currency={self.currency_code!r})>"
        )
