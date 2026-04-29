"""Repository for TenantSettings aggregate."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.common.identifiers import new_ulid
from app.domain.tenant_settings import (
    BrandingConfig,
    CurrencyConfig,
    CurrencyPosition,
    DateFormat,
    InvoiceConfig,
    LocaleConfig,
    TaxConfig,
    TaxRate,
    TenantSettings,
    ThemeConfig,
    ThemeMode,
    TimeFormat,
)
from app.infrastructure.db.models.tenant_settings_model import TenantSettingsModel

if TYPE_CHECKING:
    pass


class TenantSettingsRepository:
    """Repository for TenantSettings persistence operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_tenant_id(self, tenant_id: str) -> TenantSettings | None:
        """Get settings for a specific tenant."""
        stmt = select(TenantSettingsModel).where(
            TenantSettingsModel.tenant_id == tenant_id
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        
        if model is None:
            return None
        
        return self._to_domain(model)

    async def get_or_create_default(self, tenant_id: str, company_name: str = "") -> TenantSettings:
        """Get settings or create default settings for a tenant."""
        settings = await self.get_by_tenant_id(tenant_id)
        
        if settings is not None:
            return settings
        
        # Create default settings
        settings = TenantSettings.create_default(
            tenant_id=tenant_id,
            settings_id=new_ulid(),
            company_name=company_name,
        )
        
        await self.save(settings)
        return settings

    async def save(self, settings: TenantSettings) -> TenantSettings:
        """Save or update tenant settings."""
        # Check if exists
        stmt = select(TenantSettingsModel).where(
            TenantSettingsModel.tenant_id == settings.tenant_id
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update existing
            self._update_model(existing, settings)
            existing.version += 1
        else:
            # Create new
            model = self._to_model(settings)
            self._session.add(model)
        
        await self._session.commit()
        
        # Refresh and return
        return await self.get_by_tenant_id(settings.tenant_id)  # type: ignore

    async def delete(self, tenant_id: str) -> bool:
        """Delete settings for a tenant."""
        stmt = select(TenantSettingsModel).where(
            TenantSettingsModel.tenant_id == tenant_id
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        
        if model:
            await self._session.delete(model)
            await self._session.commit()
            return True
        return False

    def _to_domain(self, model: TenantSettingsModel) -> TenantSettings:
        """Convert DB model to domain entity."""
        # Parse tax rates from JSON
        tax_rates = []
        for rate_data in (model.tax_rates or []):
            tax_rates.append(
                TaxRate(
                    name=rate_data.get("name", "Tax"),
                    rate=Decimal(str(rate_data.get("rate", 0))),
                    is_default=rate_data.get("is_default", False),
                    applies_to_shipping=rate_data.get("applies_to_shipping", False),
                )
            )

        return TenantSettings(
            id=model.id,
            tenant_id=model.tenant_id,
            branding=BrandingConfig(
                logo_url=model.logo_url,
                logo_dark_url=model.logo_dark_url,
                favicon_url=model.favicon_url,
                primary_color=model.primary_color,
                secondary_color=model.secondary_color,
                accent_color=model.accent_color,
                background_color=model.background_color,
                surface_color=model.surface_color,
                company_name=model.company_name,
                company_tagline=model.company_tagline,
                company_address=model.company_address,
                company_phone=model.company_phone,
                company_email=model.company_email,
                company_website=model.company_website,
                business_registration_number=model.business_registration_number,
                tax_registration_number=model.tax_registration_number,
            ),
            currency=CurrencyConfig(
                currency_code=model.currency_code,
                currency_symbol=model.currency_symbol,
                currency_position=CurrencyPosition(model.currency_position),
                decimal_places=model.decimal_places,
                thousand_separator=model.thousand_separator,
                decimal_separator=model.decimal_separator,
            ),
            locale=LocaleConfig(
                timezone=model.timezone,
                date_format=DateFormat(model.date_format) if model.date_format in [e.value for e in DateFormat] else DateFormat.ISO,
                time_format=TimeFormat(model.time_format) if model.time_format in [e.value for e in TimeFormat] else TimeFormat.HOUR_24,
                first_day_of_week=model.first_day_of_week,
                language=model.language,
            ),
            tax=TaxConfig(
                default_tax_rate=model.default_tax_rate,
                tax_inclusive_pricing=model.tax_inclusive_pricing,
                show_tax_breakdown=model.show_tax_breakdown,
                tax_rates=tax_rates,
            ),
            invoice=InvoiceConfig(
                invoice_prefix=model.invoice_prefix,
                invoice_number_length=model.invoice_number_length,
                invoice_header_text=model.invoice_header_text,
                invoice_footer_text=model.invoice_footer_text,
                receipt_footer_message=model.receipt_footer_message,
                show_logo_on_receipt=model.show_logo_on_receipt,
                show_logo_on_invoice=model.show_logo_on_invoice,
                show_tax_breakdown=model.show_tax_breakdown,
                show_payment_instructions=model.show_payment_instructions,
                payment_instructions=model.payment_instructions,
                terms_and_conditions=model.terms_and_conditions,
            ),
            theme=ThemeConfig(
                mode=ThemeMode(model.theme_mode) if model.theme_mode in [e.value for e in ThemeMode] else ThemeMode.DARK,
                custom_css=model.custom_css,
                font_family=model.font_family,
                border_radius=model.border_radius,
            ),
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )

    def _to_model(self, entity: TenantSettings) -> TenantSettingsModel:
        """Convert domain entity to DB model."""
        # Serialize tax rates to JSON
        tax_rates_json = [
            {
                "name": rate.name,
                "rate": float(rate.rate),
                "is_default": rate.is_default,
                "applies_to_shipping": rate.applies_to_shipping,
            }
            for rate in entity.tax.tax_rates
        ]

        return TenantSettingsModel(
            id=entity.id,
            tenant_id=entity.tenant_id,
            # Branding
            logo_url=entity.branding.logo_url,
            logo_dark_url=entity.branding.logo_dark_url,
            favicon_url=entity.branding.favicon_url,
            primary_color=entity.branding.primary_color,
            secondary_color=entity.branding.secondary_color,
            accent_color=entity.branding.accent_color,
            background_color=entity.branding.background_color,
            surface_color=entity.branding.surface_color,
            company_name=entity.branding.company_name,
            company_tagline=entity.branding.company_tagline,
            company_address=entity.branding.company_address,
            company_phone=entity.branding.company_phone,
            company_email=entity.branding.company_email,
            company_website=entity.branding.company_website,
            business_registration_number=entity.branding.business_registration_number,
            tax_registration_number=entity.branding.tax_registration_number,
            # Currency
            currency_code=entity.currency.currency_code,
            currency_symbol=entity.currency.currency_symbol,
            currency_position=entity.currency.currency_position.value,
            decimal_places=entity.currency.decimal_places,
            thousand_separator=entity.currency.thousand_separator,
            decimal_separator=entity.currency.decimal_separator,
            # Locale
            timezone=entity.locale.timezone,
            date_format=entity.locale.date_format.value,
            time_format=entity.locale.time_format.value,
            first_day_of_week=entity.locale.first_day_of_week,
            language=entity.locale.language,
            # Tax
            default_tax_rate=entity.tax.default_tax_rate,
            tax_inclusive_pricing=entity.tax.tax_inclusive_pricing,
            show_tax_breakdown=entity.tax.show_tax_breakdown,
            tax_rates=tax_rates_json,
            # Invoice
            invoice_prefix=entity.invoice.invoice_prefix,
            invoice_number_length=entity.invoice.invoice_number_length,
            invoice_header_text=entity.invoice.invoice_header_text,
            invoice_footer_text=entity.invoice.invoice_footer_text,
            receipt_footer_message=entity.invoice.receipt_footer_message,
            show_logo_on_receipt=entity.invoice.show_logo_on_receipt,
            show_logo_on_invoice=entity.invoice.show_logo_on_invoice,
            show_payment_instructions=entity.invoice.show_payment_instructions,
            payment_instructions=entity.invoice.payment_instructions,
            terms_and_conditions=entity.invoice.terms_and_conditions,
            # Theme
            theme_mode=entity.theme.mode.value,
            custom_css=entity.theme.custom_css,
            font_family=entity.theme.font_family,
            border_radius=entity.theme.border_radius,
        )

    def _update_model(self, model: TenantSettingsModel, entity: TenantSettings) -> None:
        """Update existing model with entity values."""
        # Branding
        model.logo_url = entity.branding.logo_url
        model.logo_dark_url = entity.branding.logo_dark_url
        model.favicon_url = entity.branding.favicon_url
        model.primary_color = entity.branding.primary_color
        model.secondary_color = entity.branding.secondary_color
        model.accent_color = entity.branding.accent_color
        model.background_color = entity.branding.background_color
        model.surface_color = entity.branding.surface_color
        model.company_name = entity.branding.company_name
        model.company_tagline = entity.branding.company_tagline
        model.company_address = entity.branding.company_address
        model.company_phone = entity.branding.company_phone
        model.company_email = entity.branding.company_email
        model.company_website = entity.branding.company_website
        model.business_registration_number = entity.branding.business_registration_number
        model.tax_registration_number = entity.branding.tax_registration_number
        
        # Currency
        model.currency_code = entity.currency.currency_code
        model.currency_symbol = entity.currency.currency_symbol
        model.currency_position = entity.currency.currency_position.value
        model.decimal_places = entity.currency.decimal_places
        model.thousand_separator = entity.currency.thousand_separator
        model.decimal_separator = entity.currency.decimal_separator
        
        # Locale
        model.timezone = entity.locale.timezone
        model.date_format = entity.locale.date_format.value
        model.time_format = entity.locale.time_format.value
        model.first_day_of_week = entity.locale.first_day_of_week
        model.language = entity.locale.language
        
        # Tax
        model.default_tax_rate = entity.tax.default_tax_rate
        model.tax_inclusive_pricing = entity.tax.tax_inclusive_pricing
        model.show_tax_breakdown = entity.tax.show_tax_breakdown
        model.tax_rates = [
            {
                "name": rate.name,
                "rate": float(rate.rate),
                "is_default": rate.is_default,
                "applies_to_shipping": rate.applies_to_shipping,
            }
            for rate in entity.tax.tax_rates
        ]
        
        # Invoice
        model.invoice_prefix = entity.invoice.invoice_prefix
        model.invoice_number_length = entity.invoice.invoice_number_length
        model.invoice_header_text = entity.invoice.invoice_header_text
        model.invoice_footer_text = entity.invoice.invoice_footer_text
        model.receipt_footer_message = entity.invoice.receipt_footer_message
        model.show_logo_on_receipt = entity.invoice.show_logo_on_receipt
        model.show_logo_on_invoice = entity.invoice.show_logo_on_invoice
        model.show_payment_instructions = entity.invoice.show_payment_instructions
        model.payment_instructions = entity.invoice.payment_instructions
        model.terms_and_conditions = entity.invoice.terms_and_conditions
        
        # Theme
        model.theme_mode = entity.theme.mode.value
        model.custom_css = entity.theme.custom_css
        model.font_family = entity.theme.font_family
        model.border_radius = entity.theme.border_radius
