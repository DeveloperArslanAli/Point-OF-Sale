"""Pydantic schemas for supplier ranking weights API."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class SupplierRankingWeightsOut(BaseModel):
    """Response schema for supplier ranking weights."""
    
    id: str
    tenant_id: str
    
    # Ranking weights
    price_weight: Decimal = Field(description="Weight for price factor (0-1)")
    lead_time_weight: Decimal = Field(description="Weight for lead time factor (0-1)")
    quality_weight: Decimal = Field(description="Weight for quality score factor (0-1)")
    reliability_weight: Decimal = Field(description="Weight for reliability factor (0-1)")
    fill_rate_weight: Decimal = Field(description="Weight for fill rate factor (0-1)")
    
    # Thresholds
    min_quality_score: Decimal = Field(description="Minimum quality score threshold (0-100)")
    min_reliability_score: Decimal = Field(description="Minimum reliability score threshold (0-100)")
    max_lead_time_days: int | None = Field(None, description="Maximum acceptable lead time in days")
    
    # Bonus
    preferred_supplier_bonus: Decimal = Field(
        description="Bonus score for preferred suppliers (0-1)"
    )
    
    # Metadata
    created_at: datetime
    updated_at: datetime
    version: int
    
    model_config = {"from_attributes": True}


class SupplierRankingWeightsUpdate(BaseModel):
    """Request schema for updating supplier ranking weights."""
    
    price_weight: Decimal | None = Field(
        None, ge=0, le=1, description="Weight for price factor (0-1)"
    )
    lead_time_weight: Decimal | None = Field(
        None, ge=0, le=1, description="Weight for lead time factor (0-1)"
    )
    quality_weight: Decimal | None = Field(
        None, ge=0, le=1, description="Weight for quality score factor (0-1)"
    )
    reliability_weight: Decimal | None = Field(
        None, ge=0, le=1, description="Weight for reliability factor (0-1)"
    )
    fill_rate_weight: Decimal | None = Field(
        None, ge=0, le=1, description="Weight for fill rate factor (0-1)"
    )
    
    min_quality_score: Decimal | None = Field(
        None, ge=0, le=100, description="Minimum quality score threshold (0-100)"
    )
    min_reliability_score: Decimal | None = Field(
        None, ge=0, le=100, description="Minimum reliability score threshold (0-100)"
    )
    max_lead_time_days: int | None = Field(
        None, ge=1, description="Maximum acceptable lead time in days"
    )
    
    preferred_supplier_bonus: Decimal | None = Field(
        None, ge=0, le=1, description="Bonus score for preferred suppliers (0-1)"
    )
    
    auto_normalize: bool = Field(
        True, description="Automatically normalize weights to sum to 1.0"
    )


class SupplierRankingWeightsCreate(BaseModel):
    """Request schema for creating supplier ranking weights (for admin)."""
    
    price_weight: Decimal = Field(
        Decimal("0.30"), ge=0, le=1, description="Weight for price factor (0-1)"
    )
    lead_time_weight: Decimal = Field(
        Decimal("0.20"), ge=0, le=1, description="Weight for lead time factor (0-1)"
    )
    quality_weight: Decimal = Field(
        Decimal("0.20"), ge=0, le=1, description="Weight for quality score factor (0-1)"
    )
    reliability_weight: Decimal = Field(
        Decimal("0.15"), ge=0, le=1, description="Weight for reliability factor (0-1)"
    )
    fill_rate_weight: Decimal = Field(
        Decimal("0.15"), ge=0, le=1, description="Weight for fill rate factor (0-1)"
    )
    
    min_quality_score: Decimal = Field(
        Decimal("0"), ge=0, le=100, description="Minimum quality score threshold (0-100)"
    )
    min_reliability_score: Decimal = Field(
        Decimal("0"), ge=0, le=100, description="Minimum reliability score threshold (0-100)"
    )
    max_lead_time_days: int | None = Field(
        None, ge=1, description="Maximum acceptable lead time in days"
    )
    
    preferred_supplier_bonus: Decimal = Field(
        Decimal("0.10"), ge=0, le=1, description="Bonus score for preferred suppliers (0-1)"
    )


class RankedSupplierOut(BaseModel):
    """A supplier with calculated ranking score."""
    
    supplier_id: str
    supplier_name: str
    
    # Raw metrics
    unit_cost: Decimal
    lead_time_days: int
    quality_score: Decimal = Field(description="Quality score (0-100)")
    reliability_score: Decimal = Field(description="On-time delivery rate (0-100)")
    fill_rate: Decimal = Field(description="Order fill rate (0-100)")
    
    # Calculated scores
    price_score: Decimal = Field(description="Normalized price score (0-1)")
    lead_time_score: Decimal = Field(description="Normalized lead time score (0-1)")
    ranking_score: Decimal = Field(description="Final weighted ranking score (0-1)")
    
    is_preferred: bool = Field(description="Whether this is the preferred supplier")
    is_eligible: bool = Field(description="Whether supplier meets minimum thresholds")
    
    model_config = {"from_attributes": True}


class RankedSuppliersResponse(BaseModel):
    """Response with ranked suppliers for a product."""
    
    product_id: str
    suppliers: list[RankedSupplierOut]
    weights_applied: SupplierRankingWeightsOut
