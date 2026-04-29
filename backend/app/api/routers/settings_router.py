"""Settings API router.

Handles tenant settings management including branding, currency,
locale, tax, invoice, and theme configuration.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user, require_roles, MANAGEMENT_ROLES
from app.api.schemas.settings import (
    COMMON_CURRENCIES,
    BrandingSchema,
    CurrencyListItem,
    CurrencySchema,
    InvoiceSchema,
    LocaleSchema,
    LogoUploadResponse,
    TaxRateSchema,
    TaxSchema,
    TenantSettingsResponse,
    ThemeSchema,
    UpdateBrandingRequest,
    UpdateCurrencyRequest,
    UpdateSettingsRequest,
    UpdateTaxRequest,
    UpdateThemeRequest,
)
from app.core.tenant import get_current_tenant_id
from app.domain.auth.entities import User, UserRole
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
from app.infrastructure.db.repositories.tenant_settings_repository import TenantSettingsRepository
from app.infrastructure.db.session import get_session

router = APIRouter(prefix="/settings", tags=["settings"])

# Only ADMIN and MANAGER can access most settings
ADMIN_ONLY = (UserRole.ADMIN,)


def get_settings_repository(
    session: Annotated[AsyncSession, Depends(get_session)]
) -> TenantSettingsRepository:
    """Get settings repository dependency."""
    return TenantSettingsRepository(session)


def _settings_to_response(settings: TenantSettings) -> TenantSettingsResponse:
    """Convert domain TenantSettings to API response schema."""
    return TenantSettingsResponse(
        id=settings.id,
        tenant_id=settings.tenant_id,
        branding=BrandingSchema(
            logo_url=settings.branding.logo_url,
            logo_dark_url=settings.branding.logo_dark_url,
            favicon_url=settings.branding.favicon_url,
            primary_color=settings.branding.primary_color,
            secondary_color=settings.branding.secondary_color,
            accent_color=settings.branding.accent_color,
            background_color=settings.branding.background_color,
            surface_color=settings.branding.surface_color,
            company_name=settings.branding.company_name,
            company_tagline=settings.branding.company_tagline,
            company_address=settings.branding.company_address,
            company_phone=settings.branding.company_phone,
            company_email=settings.branding.company_email,
            company_website=settings.branding.company_website,
            business_registration_number=settings.branding.business_registration_number,
            tax_registration_number=settings.branding.tax_registration_number,
        ),
        currency=CurrencySchema(
            currency_code=settings.currency.currency_code,
            currency_symbol=settings.currency.currency_symbol,
            currency_position=settings.currency.currency_position.value,
            decimal_places=settings.currency.decimal_places,
            thousand_separator=settings.currency.thousand_separator,
            decimal_separator=settings.currency.decimal_separator,
        ),
        locale=LocaleSchema(
            timezone=settings.locale.timezone,
            date_format=settings.locale.date_format.value,
            time_format=settings.locale.time_format.value,
            first_day_of_week=settings.locale.first_day_of_week,
            language=settings.locale.language,
        ),
        tax=TaxSchema(
            default_tax_rate=float(settings.tax.default_tax_rate),
            tax_inclusive_pricing=settings.tax.tax_inclusive_pricing,
            show_tax_breakdown=settings.tax.show_tax_breakdown,
            tax_rates=[
                TaxRateSchema(
                    name=rate.name,
                    rate=float(rate.rate),
                    is_default=rate.is_default,
                    applies_to_shipping=rate.applies_to_shipping,
                )
                for rate in settings.tax.tax_rates
            ],
        ),
        invoice=InvoiceSchema(
            invoice_prefix=settings.invoice.invoice_prefix,
            invoice_number_length=settings.invoice.invoice_number_length,
            invoice_header_text=settings.invoice.invoice_header_text,
            invoice_footer_text=settings.invoice.invoice_footer_text,
            receipt_footer_message=settings.invoice.receipt_footer_message,
            show_logo_on_receipt=settings.invoice.show_logo_on_receipt,
            show_logo_on_invoice=settings.invoice.show_logo_on_invoice,
            show_tax_breakdown=settings.invoice.show_tax_breakdown,
            show_payment_instructions=settings.invoice.show_payment_instructions,
            payment_instructions=settings.invoice.payment_instructions,
            terms_and_conditions=settings.invoice.terms_and_conditions,
        ),
        theme=ThemeSchema(
            mode=settings.theme.mode.value,
            custom_css=settings.theme.custom_css,
            font_family=settings.theme.font_family,
            border_radius=settings.theme.border_radius,
        ),
        created_at=settings.created_at,
        updated_at=settings.updated_at,
        version=settings.version,
    )


# =====================
# GET Endpoints
# =====================


@router.get("", response_model=TenantSettingsResponse)
async def get_settings(
    current_user: Annotated[User, Depends(require_roles(*MANAGEMENT_ROLES))],
    repo: Annotated[TenantSettingsRepository, Depends(get_settings_repository)],
) -> TenantSettingsResponse:
    """Get current tenant settings.
    
    Returns all settings including branding, currency, locale, tax, invoice, and theme.
    Creates default settings if none exist.
    """
    tenant_id = get_current_tenant_id()
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context required",
        )
    
    settings = await repo.get_or_create_default(tenant_id)
    return _settings_to_response(settings)


@router.get("/currencies", response_model=list[CurrencyListItem])
async def get_available_currencies(
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[CurrencyListItem]:
    """Get list of available currencies for dropdown selection."""
    return COMMON_CURRENCIES


@router.get("/timezones")
async def get_available_timezones(
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[dict]:
    """Get list of common timezones for dropdown selection."""
    # Common timezones with offsets
    return [
        {"name": "UTC", "offset": "UTC+00:00"},
        {"name": "America/New_York", "offset": "UTC-05:00"},
        {"name": "America/Chicago", "offset": "UTC-06:00"},
        {"name": "America/Denver", "offset": "UTC-07:00"},
        {"name": "America/Los_Angeles", "offset": "UTC-08:00"},
        {"name": "America/Toronto", "offset": "UTC-05:00"},
        {"name": "America/Vancouver", "offset": "UTC-08:00"},
        {"name": "America/Mexico_City", "offset": "UTC-06:00"},
        {"name": "America/Sao_Paulo", "offset": "UTC-03:00"},
        {"name": "Europe/London", "offset": "UTC+00:00"},
        {"name": "Europe/Paris", "offset": "UTC+01:00"},
        {"name": "Europe/Berlin", "offset": "UTC+01:00"},
        {"name": "Europe/Rome", "offset": "UTC+01:00"},
        {"name": "Europe/Madrid", "offset": "UTC+01:00"},
        {"name": "Europe/Amsterdam", "offset": "UTC+01:00"},
        {"name": "Europe/Moscow", "offset": "UTC+03:00"},
        {"name": "Asia/Tokyo", "offset": "UTC+09:00"},
        {"name": "Asia/Shanghai", "offset": "UTC+08:00"},
        {"name": "Asia/Hong_Kong", "offset": "UTC+08:00"},
        {"name": "Asia/Singapore", "offset": "UTC+08:00"},
        {"name": "Asia/Seoul", "offset": "UTC+09:00"},
        {"name": "Asia/Mumbai", "offset": "UTC+05:30"},
        {"name": "Asia/Dubai", "offset": "UTC+04:00"},
        {"name": "Asia/Jakarta", "offset": "UTC+07:00"},
        {"name": "Asia/Bangkok", "offset": "UTC+07:00"},
        {"name": "Australia/Sydney", "offset": "UTC+11:00"},
        {"name": "Australia/Melbourne", "offset": "UTC+11:00"},
        {"name": "Australia/Perth", "offset": "UTC+08:00"},
        {"name": "Pacific/Auckland", "offset": "UTC+13:00"},
        {"name": "Africa/Cairo", "offset": "UTC+02:00"},
        {"name": "Africa/Johannesburg", "offset": "UTC+02:00"},
        {"name": "Africa/Lagos", "offset": "UTC+01:00"},
        {"name": "Africa/Nairobi", "offset": "UTC+03:00"},
    ]


# =====================
# PUT Endpoints
# =====================


@router.put("", response_model=TenantSettingsResponse)
async def update_settings(
    request: UpdateSettingsRequest,
    current_user: Annotated[User, Depends(require_roles(*ADMIN_ONLY))],
    repo: Annotated[TenantSettingsRepository, Depends(get_settings_repository)],
) -> TenantSettingsResponse:
    """Update tenant settings.
    
    Only updates the sections provided in the request.
    """
    tenant_id = get_current_tenant_id()
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context required",
        )
    
    settings = await repo.get_or_create_default(tenant_id)
    
    # Update branding if provided
    if request.branding:
        settings.branding = BrandingConfig(
            logo_url=request.branding.logo_url,
            logo_dark_url=request.branding.logo_dark_url,
            favicon_url=request.branding.favicon_url,
            primary_color=request.branding.primary_color,
            secondary_color=request.branding.secondary_color,
            accent_color=request.branding.accent_color,
            background_color=request.branding.background_color,
            surface_color=request.branding.surface_color,
            company_name=request.branding.company_name,
            company_tagline=request.branding.company_tagline,
            company_address=request.branding.company_address,
            company_phone=request.branding.company_phone,
            company_email=request.branding.company_email,
            company_website=request.branding.company_website,
            business_registration_number=request.branding.business_registration_number,
            tax_registration_number=request.branding.tax_registration_number,
        )
    
    # Update currency if provided
    if request.currency:
        settings.currency = CurrencyConfig(
            currency_code=request.currency.currency_code,
            currency_symbol=request.currency.currency_symbol,
            currency_position=CurrencyPosition(request.currency.currency_position),
            decimal_places=request.currency.decimal_places,
            thousand_separator=request.currency.thousand_separator,
            decimal_separator=request.currency.decimal_separator,
        )
    
    # Update locale if provided
    if request.locale:
        settings.locale = LocaleConfig(
            timezone=request.locale.timezone,
            date_format=DateFormat(request.locale.date_format),
            time_format=TimeFormat(request.locale.time_format),
            first_day_of_week=request.locale.first_day_of_week,
            language=request.locale.language,
        )
    
    # Update tax if provided
    if request.tax:
        tax_rates = [
            TaxRate(
                name=rate.name,
                rate=Decimal(str(rate.rate)),
                is_default=rate.is_default,
                applies_to_shipping=rate.applies_to_shipping,
            )
            for rate in request.tax.tax_rates
        ]
        settings.tax = TaxConfig(
            default_tax_rate=Decimal(str(request.tax.default_tax_rate)),
            tax_inclusive_pricing=request.tax.tax_inclusive_pricing,
            show_tax_breakdown=request.tax.show_tax_breakdown,
            tax_rates=tax_rates,
        )
    
    # Update invoice if provided
    if request.invoice:
        settings.invoice = InvoiceConfig(
            invoice_prefix=request.invoice.invoice_prefix,
            invoice_number_length=request.invoice.invoice_number_length,
            invoice_header_text=request.invoice.invoice_header_text,
            invoice_footer_text=request.invoice.invoice_footer_text,
            receipt_footer_message=request.invoice.receipt_footer_message,
            show_logo_on_receipt=request.invoice.show_logo_on_receipt,
            show_logo_on_invoice=request.invoice.show_logo_on_invoice,
            show_tax_breakdown=request.invoice.show_tax_breakdown,
            show_payment_instructions=request.invoice.show_payment_instructions,
            payment_instructions=request.invoice.payment_instructions,
            terms_and_conditions=request.invoice.terms_and_conditions,
        )
    
    # Update theme if provided
    if request.theme:
        settings.theme = ThemeConfig(
            mode=ThemeMode(request.theme.mode),
            custom_css=request.theme.custom_css,
            font_family=request.theme.font_family,
            border_radius=request.theme.border_radius,
        )
    
    updated = await repo.save(settings)
    return _settings_to_response(updated)


@router.put("/branding", response_model=TenantSettingsResponse)
async def update_branding(
    request: UpdateBrandingRequest,
    current_user: Annotated[User, Depends(require_roles(*ADMIN_ONLY))],
    repo: Annotated[TenantSettingsRepository, Depends(get_settings_repository)],
) -> TenantSettingsResponse:
    """Update branding settings only."""
    tenant_id = get_current_tenant_id()
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context required",
        )
    
    settings = await repo.get_or_create_default(tenant_id)
    
    # Partial update - only update fields that are provided
    if request.logo_url is not None:
        settings.branding.logo_url = request.logo_url
    if request.logo_dark_url is not None:
        settings.branding.logo_dark_url = request.logo_dark_url
    if request.favicon_url is not None:
        settings.branding.favicon_url = request.favicon_url
    if request.primary_color is not None:
        settings.branding.primary_color = request.primary_color
    if request.secondary_color is not None:
        settings.branding.secondary_color = request.secondary_color
    if request.accent_color is not None:
        settings.branding.accent_color = request.accent_color
    if request.background_color is not None:
        settings.branding.background_color = request.background_color
    if request.surface_color is not None:
        settings.branding.surface_color = request.surface_color
    if request.company_name is not None:
        settings.branding.company_name = request.company_name
    if request.company_tagline is not None:
        settings.branding.company_tagline = request.company_tagline
    if request.company_address is not None:
        settings.branding.company_address = request.company_address
    if request.company_phone is not None:
        settings.branding.company_phone = request.company_phone
    if request.company_email is not None:
        settings.branding.company_email = request.company_email
    if request.company_website is not None:
        settings.branding.company_website = request.company_website
    if request.business_registration_number is not None:
        settings.branding.business_registration_number = request.business_registration_number
    if request.tax_registration_number is not None:
        settings.branding.tax_registration_number = request.tax_registration_number
    
    updated = await repo.save(settings)
    return _settings_to_response(updated)


@router.put("/currency", response_model=TenantSettingsResponse)
async def update_currency(
    request: UpdateCurrencyRequest,
    current_user: Annotated[User, Depends(require_roles(*ADMIN_ONLY))],
    repo: Annotated[TenantSettingsRepository, Depends(get_settings_repository)],
) -> TenantSettingsResponse:
    """Update currency settings only."""
    tenant_id = get_current_tenant_id()
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context required",
        )
    
    settings = await repo.get_or_create_default(tenant_id)
    
    if request.currency_code is not None:
        settings.currency.currency_code = request.currency_code
    if request.currency_symbol is not None:
        settings.currency.currency_symbol = request.currency_symbol
    if request.currency_position is not None:
        settings.currency.currency_position = CurrencyPosition(request.currency_position)
    if request.decimal_places is not None:
        settings.currency.decimal_places = request.decimal_places
    if request.thousand_separator is not None:
        settings.currency.thousand_separator = request.thousand_separator
    if request.decimal_separator is not None:
        settings.currency.decimal_separator = request.decimal_separator
    
    updated = await repo.save(settings)
    return _settings_to_response(updated)


@router.put("/tax", response_model=TenantSettingsResponse)
async def update_tax(
    request: UpdateTaxRequest,
    current_user: Annotated[User, Depends(require_roles(*ADMIN_ONLY))],
    repo: Annotated[TenantSettingsRepository, Depends(get_settings_repository)],
) -> TenantSettingsResponse:
    """Update tax settings only."""
    tenant_id = get_current_tenant_id()
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context required",
        )
    
    settings = await repo.get_or_create_default(tenant_id)
    
    if request.default_tax_rate is not None:
        settings.tax.default_tax_rate = Decimal(str(request.default_tax_rate))
    if request.tax_inclusive_pricing is not None:
        settings.tax.tax_inclusive_pricing = request.tax_inclusive_pricing
    if request.show_tax_breakdown is not None:
        settings.tax.show_tax_breakdown = request.show_tax_breakdown
    if request.tax_rates is not None:
        settings.tax.tax_rates = [
            TaxRate(
                name=rate.name,
                rate=Decimal(str(rate.rate)),
                is_default=rate.is_default,
                applies_to_shipping=rate.applies_to_shipping,
            )
            for rate in request.tax_rates
        ]
    
    updated = await repo.save(settings)
    return _settings_to_response(updated)


@router.put("/theme", response_model=TenantSettingsResponse)
async def update_theme(
    request: UpdateThemeRequest,
    current_user: Annotated[User, Depends(require_roles(*MANAGEMENT_ROLES))],
    repo: Annotated[TenantSettingsRepository, Depends(get_settings_repository)],
) -> TenantSettingsResponse:
    """Update theme settings.
    
    This endpoint is available to both ADMIN and MANAGER roles.
    """
    tenant_id = get_current_tenant_id()
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context required",
        )
    
    settings = await repo.get_or_create_default(tenant_id)
    
    if request.mode is not None:
        settings.theme.mode = ThemeMode(request.mode)
    if request.custom_css is not None:
        settings.theme.custom_css = request.custom_css
    if request.font_family is not None:
        settings.theme.font_family = request.font_family
    if request.border_radius is not None:
        settings.theme.border_radius = request.border_radius
    
    updated = await repo.save(settings)
    return _settings_to_response(updated)


# =====================
# Logo Upload
# =====================


@router.post("/logo", response_model=LogoUploadResponse)
async def upload_logo(
    file: UploadFile = File(...),
    logo_type: str = "primary",  # "primary" or "dark"
    current_user: User = Depends(require_roles(*ADMIN_ONLY)),
    repo: TenantSettingsRepository = Depends(get_settings_repository),
) -> LogoUploadResponse:
    """Upload a logo image.
    
    Accepts PNG, JPG, or WEBP images up to 2MB.
    """
    tenant_id = get_current_tenant_id()
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context required",
        )
    
    # Validate file type
    allowed_types = ["image/png", "image/jpeg", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_types)}",
        )
    
    # Validate file size (2MB max)
    content = await file.read()
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 2MB limit",
        )
    
    # TODO: In production, upload to cloud storage (S3, Azure Blob, etc.)
    # For now, we'll save locally and return a placeholder URL
    import base64
    
    # Create a data URL for demo purposes
    # In production, this should be replaced with actual cloud storage
    data_url = f"data:{file.content_type};base64,{base64.b64encode(content).decode()}"
    
    settings = await repo.get_or_create_default(tenant_id)
    
    if logo_type == "dark":
        settings.branding.logo_dark_url = data_url
    else:
        settings.branding.logo_url = data_url
    
    await repo.save(settings)
    
    return LogoUploadResponse(
        logo_url=data_url,
        message=f"Logo ({logo_type}) uploaded successfully",
    )
