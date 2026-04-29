"""Pydantic schemas for product-supplier links API."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProductSupplierLinkCreate(BaseModel):
    """Schema for creating a product-supplier link."""

    product_id: str = Field(min_length=1, max_length=26)
    supplier_id: str = Field(min_length=1, max_length=26)
    unit_cost: Decimal = Field(ge=0, decimal_places=2)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    minimum_order_quantity: int = Field(default=1, ge=1)
    lead_time_days: int = Field(default=7, ge=1, le=365)
    priority: int = Field(default=1, ge=1, le=100)
    is_preferred: bool = Field(default=False)
    notes: str | None = Field(default=None, max_length=500)


class ProductSupplierLinkUpdate(BaseModel):
    """Schema for updating a product-supplier link."""

    unit_cost: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    minimum_order_quantity: int | None = Field(default=None, ge=1)
    lead_time_days: int | None = Field(default=None, ge=1, le=365)
    priority: int | None = Field(default=None, ge=1, le=100)
    is_preferred: bool | None = None
    is_active: bool | None = None
    notes: str | None = Field(default=None, max_length=500)


class ProductSupplierLinkOut(BaseModel):
    """Schema for product-supplier link output."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    product_id: str
    supplier_id: str
    unit_cost: Decimal
    currency: str
    minimum_order_quantity: int
    lead_time_days: int
    priority: int
    is_preferred: bool
    is_active: bool
    notes: str | None
    created_at: datetime | None
    updated_at: datetime | None


class ProductSupplierLinkWithDetailsOut(BaseModel):
    """Schema for product-supplier link with product/supplier details."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    product_id: str
    product_name: str
    product_sku: str
    supplier_id: str
    supplier_name: str
    unit_cost: Decimal
    currency: str
    minimum_order_quantity: int
    lead_time_days: int
    priority: int
    is_preferred: bool
    is_active: bool
    notes: str | None
    created_at: datetime | None
    updated_at: datetime | None


class ProductSupplierLinksListOut(BaseModel):
    """Schema for listing product-supplier links."""

    items: list[ProductSupplierLinkOut]
    total: int


class PreferredSupplierOut(BaseModel):
    """Schema for preferred supplier response."""

    link: ProductSupplierLinkOut | None
    product_id: str
    has_preferred: bool


class BulkLinkCreate(BaseModel):
    """Schema for bulk creating product-supplier links."""

    links: list[ProductSupplierLinkCreate] = Field(min_length=1, max_length=100)


class BulkLinkResult(BaseModel):
    """Schema for bulk operation result."""

    created: int
    failed: int
    errors: list[str]
