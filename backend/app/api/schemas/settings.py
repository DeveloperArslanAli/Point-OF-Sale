"""Pydantic schemas for tenant settings API."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TaxRateSchema(BaseModel):
    """Individual tax rate configuration."""
    
    name: str = Field(..., min_length=1, max_length=50)
    rate: float = Field(..., ge=0, le=1, description="Tax rate as decimal (0.20 = 20%)")
    is_default: bool = False
    applies_to_shipping: bool = False


class BrandingSchema(BaseModel):
    """Branding configuration."""
    
    logo_url: str | None = None
    logo_dark_url: str | None = None
    favicon_url: str | None = None
    primary_color: str = Field("#6366f1", pattern=r"^#[0-9a-fA-F]{6}$")
    secondary_color: str = Field("#8b5cf6", pattern=r"^#[0-9a-fA-F]{6}$")
    accent_color: str = Field("#bb86fc", pattern=r"^#[0-9a-fA-F]{6}$")
    background_color: str = Field("#1a1c1e", pattern=r"^#[0-9a-fA-F]{6}$")
    surface_color: str = Field("#2d3033", pattern=r"^#[0-9a-fA-F]{6}$")
    company_name: str = Field("", max_length=255)
    company_tagline: str | None = Field(None, max_length=255)
    company_address: str | None = None
    company_phone: str | None = Field(None, max_length=50)
    company_email: str | None = Field(None, max_length=255)
    company_website: str | None = Field(None, max_length=255)
    business_registration_number: str | None = Field(None, max_length=100)
    tax_registration_number: str | None = Field(None, max_length=100)


class CurrencySchema(BaseModel):
    """Currency configuration."""
    
    currency_code: str = Field("USD", min_length=3, max_length=3)
    currency_symbol: str = Field("$", max_length=5)
    currency_position: Literal["before", "after"] = "before"
    decimal_places: int = Field(2, ge=0, le=4)
    thousand_separator: str = Field(",", max_length=1)
    decimal_separator: str = Field(".", max_length=1)
    
    @field_validator("thousand_separator", "decimal_separator")
    @classmethod
    def validate_separators(cls, v: str) -> str:
        if v not in [",", ".", " ", "'", ""]:
            raise ValueError("Invalid separator")
        return v


class LocaleSchema(BaseModel):
    """Locale and timezone configuration."""
    
    timezone: str = Field("UTC", max_length=50)
    date_format: Literal["YYYY-MM-DD", "MM/DD/YYYY", "DD/MM/YYYY", "MMMM DD, YYYY"] = "YYYY-MM-DD"
    time_format: Literal["12h", "24h"] = "24h"
    first_day_of_week: int = Field(1, ge=0, le=6)
    language: str = Field("en", max_length=10)


class TaxSchema(BaseModel):
    """Tax configuration."""
    
    default_tax_rate: float = Field(0.0, ge=0, le=1)
    tax_inclusive_pricing: bool = False
    show_tax_breakdown: bool = True
    tax_rates: list[TaxRateSchema] = Field(default_factory=list)


class InvoiceSchema(BaseModel):
    """Invoice and receipt configuration."""
    
    invoice_prefix: str = Field("INV", max_length=10)
    invoice_number_length: int = Field(6, ge=4, le=10)
    invoice_header_text: str | None = None
    invoice_footer_text: str | None = None
    receipt_footer_message: str = Field("Thank you for your business!", max_length=500)
    show_logo_on_receipt: bool = True
    show_logo_on_invoice: bool = True
    show_tax_breakdown: bool = True
    show_payment_instructions: bool = False
    payment_instructions: str | None = None
    terms_and_conditions: str | None = None


class ThemeSchema(BaseModel):
    """Theme configuration."""
    
    mode: Literal["light", "dark", "system"] = "dark"
    custom_css: str | None = None
    font_family: str = Field("Roboto", max_length=50)
    border_radius: int = Field(10, ge=0, le=50)


# =====================
# Request Schemas
# =====================


class UpdateSettingsRequest(BaseModel):
    """Request to update all settings at once."""
    
    branding: BrandingSchema | None = None
    currency: CurrencySchema | None = None
    locale: LocaleSchema | None = None
    tax: TaxSchema | None = None
    invoice: InvoiceSchema | None = None
    theme: ThemeSchema | None = None


class UpdateBrandingRequest(BaseModel):
    """Request to update branding settings only."""
    
    logo_url: str | None = None
    logo_dark_url: str | None = None
    favicon_url: str | None = None
    primary_color: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    secondary_color: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    accent_color: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    background_color: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    surface_color: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    company_name: str | None = Field(None, max_length=255)
    company_tagline: str | None = Field(None, max_length=255)
    company_address: str | None = None
    company_phone: str | None = Field(None, max_length=50)
    company_email: str | None = Field(None, max_length=255)
    company_website: str | None = Field(None, max_length=255)
    business_registration_number: str | None = Field(None, max_length=100)
    tax_registration_number: str | None = Field(None, max_length=100)


class UpdateCurrencyRequest(BaseModel):
    """Request to update currency settings only."""
    
    currency_code: str | None = Field(None, min_length=3, max_length=3)
    currency_symbol: str | None = Field(None, max_length=5)
    currency_position: Literal["before", "after"] | None = None
    decimal_places: int | None = Field(None, ge=0, le=4)
    thousand_separator: str | None = Field(None, max_length=1)
    decimal_separator: str | None = Field(None, max_length=1)


class UpdateTaxRequest(BaseModel):
    """Request to update tax settings only."""
    
    default_tax_rate: float | None = Field(None, ge=0, le=1)
    tax_inclusive_pricing: bool | None = None
    show_tax_breakdown: bool | None = None
    tax_rates: list[TaxRateSchema] | None = None


class UpdateThemeRequest(BaseModel):
    """Request to update theme settings only."""
    
    mode: Literal["light", "dark", "system"] | None = None
    custom_css: str | None = None
    font_family: str | None = Field(None, max_length=50)
    border_radius: int | None = Field(None, ge=0, le=50)


# =====================
# Response Schemas
# =====================


class TenantSettingsResponse(BaseModel):
    """Complete tenant settings response."""
    
    id: str
    tenant_id: str
    branding: BrandingSchema
    currency: CurrencySchema
    locale: LocaleSchema
    tax: TaxSchema
    invoice: InvoiceSchema
    theme: ThemeSchema
    created_at: datetime
    updated_at: datetime
    version: int

    class Config:
        from_attributes = True


class LogoUploadResponse(BaseModel):
    """Response after logo upload."""
    
    logo_url: str
    message: str = "Logo uploaded successfully"


class CurrencyListItem(BaseModel):
    """Currency option for dropdown."""
    
    code: str
    name: str
    symbol: str


class TimezoneListItem(BaseModel):
    """Timezone option for dropdown."""
    
    name: str
    offset: str


# Common currencies for dropdown
COMMON_CURRENCIES = [
    CurrencyListItem(code="USD", name="US Dollar", symbol="$"),
    CurrencyListItem(code="EUR", name="Euro", symbol="€"),
    CurrencyListItem(code="GBP", name="British Pound", symbol="£"),
    CurrencyListItem(code="JPY", name="Japanese Yen", symbol="¥"),
    CurrencyListItem(code="CAD", name="Canadian Dollar", symbol="C$"),
    CurrencyListItem(code="AUD", name="Australian Dollar", symbol="A$"),
    CurrencyListItem(code="CHF", name="Swiss Franc", symbol="CHF"),
    CurrencyListItem(code="CNY", name="Chinese Yuan", symbol="¥"),
    CurrencyListItem(code="INR", name="Indian Rupee", symbol="₹"),
    CurrencyListItem(code="MXN", name="Mexican Peso", symbol="$"),
    CurrencyListItem(code="BRL", name="Brazilian Real", symbol="R$"),
    CurrencyListItem(code="KRW", name="South Korean Won", symbol="₩"),
    CurrencyListItem(code="SGD", name="Singapore Dollar", symbol="S$"),
    CurrencyListItem(code="HKD", name="Hong Kong Dollar", symbol="HK$"),
    CurrencyListItem(code="NOK", name="Norwegian Krone", symbol="kr"),
    CurrencyListItem(code="SEK", name="Swedish Krona", symbol="kr"),
    CurrencyListItem(code="DKK", name="Danish Krone", symbol="kr"),
    CurrencyListItem(code="NZD", name="New Zealand Dollar", symbol="NZ$"),
    CurrencyListItem(code="ZAR", name="South African Rand", symbol="R"),
    CurrencyListItem(code="RUB", name="Russian Ruble", symbol="₽"),
    CurrencyListItem(code="TRY", name="Turkish Lira", symbol="₺"),
    CurrencyListItem(code="PLN", name="Polish Zloty", symbol="zł"),
    CurrencyListItem(code="THB", name="Thai Baht", symbol="฿"),
    CurrencyListItem(code="IDR", name="Indonesian Rupiah", symbol="Rp"),
    CurrencyListItem(code="MYR", name="Malaysian Ringgit", symbol="RM"),
    CurrencyListItem(code="PHP", name="Philippine Peso", symbol="₱"),
    CurrencyListItem(code="CZK", name="Czech Koruna", symbol="Kč"),
    CurrencyListItem(code="ILS", name="Israeli Shekel", symbol="₪"),
    CurrencyListItem(code="CLP", name="Chilean Peso", symbol="$"),
    CurrencyListItem(code="PKR", name="Pakistani Rupee", symbol="₨"),
    CurrencyListItem(code="AED", name="UAE Dirham", symbol="د.إ"),
    CurrencyListItem(code="SAR", name="Saudi Riyal", symbol="﷼"),
    CurrencyListItem(code="EGP", name="Egyptian Pound", symbol="£"),
    CurrencyListItem(code="NGN", name="Nigerian Naira", symbol="₦"),
    CurrencyListItem(code="KES", name="Kenyan Shilling", symbol="KSh"),
    CurrencyListItem(code="GHS", name="Ghanaian Cedi", symbol="₵"),
    CurrencyListItem(code="VND", name="Vietnamese Dong", symbol="₫"),
    CurrencyListItem(code="BDT", name="Bangladeshi Taka", symbol="৳"),
    CurrencyListItem(code="TWD", name="Taiwan Dollar", symbol="NT$"),
    CurrencyListItem(code="ARS", name="Argentine Peso", symbol="$"),
]
