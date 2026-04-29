"""Tenant Settings domain entities.

Contains entities for tenant-level configuration including branding,
currency, locale, tax, and theme settings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class CurrencyPosition(str, Enum):
    """Position of currency symbol relative to amount."""
    
    BEFORE = "before"  # $100.00
    AFTER = "after"    # 100.00€


class TimeFormat(str, Enum):
    """Time display format."""
    
    HOUR_12 = "12h"  # 2:30 PM
    HOUR_24 = "24h"  # 14:30


class DateFormat(str, Enum):
    """Date display format."""
    
    ISO = "YYYY-MM-DD"        # 2025-12-24
    US = "MM/DD/YYYY"         # 12/24/2025
    EU = "DD/MM/YYYY"         # 24/12/2025
    LONG = "MMMM DD, YYYY"    # December 24, 2025


class ThemeMode(str, Enum):
    """UI theme mode."""
    
    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


@dataclass
class TaxRate:
    """Individual tax rate configuration."""
    
    name: str
    rate: Decimal  # e.g., 0.20 for 20%
    is_default: bool = False
    applies_to_shipping: bool = False
    
    def calculate_tax(self, amount: Decimal) -> Decimal:
        """Calculate tax amount for given base amount."""
        return (amount * self.rate).quantize(Decimal("0.01"))


@dataclass
class BrandingConfig:
    """Tenant branding configuration."""
    
    # Logo URLs
    logo_url: str | None = None
    logo_dark_url: str | None = None  # For dark mode
    favicon_url: str | None = None
    
    # Colors (hex format)
    primary_color: str = "#6366f1"     # Indigo
    secondary_color: str = "#8b5cf6"   # Purple
    accent_color: str = "#bb86fc"      # Light purple
    background_color: str = "#1a1c1e"  # Dark background
    surface_color: str = "#2d3033"     # Card/surface background
    
    # Company Identity
    company_name: str = ""
    company_tagline: str | None = None
    company_address: str | None = None
    company_phone: str | None = None
    company_email: str | None = None
    company_website: str | None = None
    business_registration_number: str | None = None
    tax_registration_number: str | None = None


@dataclass
class CurrencyConfig:
    """Currency and number formatting configuration."""
    
    currency_code: str = "USD"         # ISO 4217 code
    currency_symbol: str = "$"
    currency_position: CurrencyPosition = CurrencyPosition.BEFORE
    decimal_places: int = 2
    thousand_separator: str = ","
    decimal_separator: str = "."
    
    def format_amount(self, amount: Decimal | float | int) -> str:
        """Format a monetary amount according to settings."""
        if isinstance(amount, (float, int)):
            amount = Decimal(str(amount))
        
        # Round to decimal places
        quantize_str = "0." + "0" * self.decimal_places
        rounded = amount.quantize(Decimal(quantize_str))
        
        # Format with separators
        str_amount = f"{rounded:,.{self.decimal_places}f}"
        
        # Replace default separators with configured ones
        if self.thousand_separator != ",":
            str_amount = str_amount.replace(",", "TEMP")
        if self.decimal_separator != ".":
            str_amount = str_amount.replace(".", self.decimal_separator)
        if self.thousand_separator != ",":
            str_amount = str_amount.replace("TEMP", self.thousand_separator)
        
        # Position symbol
        if self.currency_position == CurrencyPosition.BEFORE:
            return f"{self.currency_symbol}{str_amount}"
        else:
            return f"{str_amount}{self.currency_symbol}"


@dataclass
class LocaleConfig:
    """Timezone and date/time formatting configuration."""
    
    timezone: str = "UTC"
    date_format: DateFormat = DateFormat.ISO
    time_format: TimeFormat = TimeFormat.HOUR_24
    first_day_of_week: int = 1  # 0=Sunday, 1=Monday
    language: str = "en"


@dataclass
class TaxConfig:
    """Tax configuration for the tenant."""
    
    default_tax_rate: Decimal = Decimal("0.00")
    tax_inclusive_pricing: bool = False  # If True, prices include tax
    show_tax_breakdown: bool = True
    tax_rates: list[TaxRate] = field(default_factory=list)
    
    def get_default_rate(self) -> TaxRate | None:
        """Get the default tax rate if any."""
        for rate in self.tax_rates:
            if rate.is_default:
                return rate
        return None
    
    def calculate_total_tax(self, subtotal: Decimal) -> Decimal:
        """Calculate total tax from all applicable rates."""
        if not self.tax_rates:
            return (subtotal * self.default_tax_rate).quantize(Decimal("0.01"))
        
        total_tax = Decimal("0.00")
        for rate in self.tax_rates:
            total_tax += rate.calculate_tax(subtotal)
        return total_tax


@dataclass
class InvoiceConfig:
    """Invoice and receipt configuration."""
    
    invoice_prefix: str = "INV"
    invoice_number_length: int = 6  # e.g., INV-000001
    invoice_header_text: str | None = None
    invoice_footer_text: str | None = None
    receipt_footer_message: str = "Thank you for your business!"
    show_logo_on_receipt: bool = True
    show_logo_on_invoice: bool = True
    show_tax_breakdown: bool = True
    show_payment_instructions: bool = False
    payment_instructions: str | None = None
    terms_and_conditions: str | None = None


@dataclass
class ThemeConfig:
    """UI theme configuration."""
    
    mode: ThemeMode = ThemeMode.DARK
    custom_css: str | None = None
    font_family: str = "Roboto"
    border_radius: int = 10  # pixels


@dataclass
class TenantSettings:
    """Complete tenant settings aggregate.
    
    This is the main entity that encompasses all tenant configuration.
    """
    
    id: str
    tenant_id: str
    
    # Sub-configurations
    branding: BrandingConfig = field(default_factory=BrandingConfig)
    currency: CurrencyConfig = field(default_factory=CurrencyConfig)
    locale: LocaleConfig = field(default_factory=LocaleConfig)
    tax: TaxConfig = field(default_factory=TaxConfig)
    invoice: InvoiceConfig = field(default_factory=InvoiceConfig)
    theme: ThemeConfig = field(default_factory=ThemeConfig)
    
    # Audit fields
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    version: int = 1
    
    def format_money(self, amount: Decimal | float) -> str:
        """Format a monetary amount using tenant currency settings."""
        return self.currency.format_amount(amount)
    
    def calculate_tax(self, subtotal: Decimal) -> Decimal:
        """Calculate tax for a subtotal using tenant tax settings."""
        return self.tax.calculate_total_tax(subtotal)
    
    @classmethod
    def create_default(cls, tenant_id: str, settings_id: str, company_name: str = "") -> TenantSettings:
        """Create default settings for a new tenant."""
        return cls(
            id=settings_id,
            tenant_id=tenant_id,
            branding=BrandingConfig(company_name=company_name),
            currency=CurrencyConfig(),
            locale=LocaleConfig(),
            tax=TaxConfig(),
            invoice=InvoiceConfig(),
            theme=ThemeConfig(),
        )
