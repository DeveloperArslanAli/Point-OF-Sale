from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class LowStockInsightOut(BaseModel):
    product_id: str
    name: str
    sku: str
    quantity_on_hand: int
    reorder_point: int
    recommended_order: int
    daily_demand: Decimal = Field(decimal_places=2)
    last_movement_at: datetime | None


class DeadStockInsightOut(BaseModel):
    product_id: str
    name: str
    sku: str
    quantity_on_hand: int
    last_movement_at: datetime | None
    days_since_movement: int | None


class InventoryInsightsResponse(BaseModel):
    generated_at: datetime
    lookback_days: int
    lead_time_days: int
    safety_stock_days: int
    low_stock: list[LowStockInsightOut]
    dead_stock: list[DeadStockInsightOut]


class ABCClassificationOut(BaseModel):
    product_id: str
    name: str
    sku: str
    usage_quantity: int
    usage_value: Decimal = Field(decimal_places=2)
    cumulative_percent: Decimal = Field(decimal_places=2)
    abc_class: str


class InventoryABCResponse(BaseModel):
    generated_at: datetime
    lookback_days: int
    a_threshold_percent: Decimal = Field(decimal_places=2)
    b_threshold_percent: Decimal = Field(decimal_places=2)
    classifications: list[ABCClassificationOut]


class ForecastInsightOut(BaseModel):
    product_id: str
    name: str
    sku: str
    quantity_on_hand: int
    daily_demand: Decimal = Field(decimal_places=2)
    days_until_stockout: float
    projected_stockout_date: datetime
    recommended_reorder_date: datetime
    recommended_order: int


class InventoryForecastResponse(BaseModel):
    generated_at: datetime
    expires_at: datetime
    ttl_minutes: int
    stale: bool
    lookback_days: int
    lead_time_days: int
    safety_stock_days: int
    forecasts: list[ForecastInsightOut]


class VendorPerformanceOut(BaseModel):
    supplier_id: str
    name: str
    contact_email: str | None
    contact_phone: str | None
    currency: str | None
    total_orders: int
    open_orders: int
    total_amount: Decimal = Field(decimal_places=2)
    average_lead_time_hours: Decimal | None = Field(default=None, decimal_places=2)
    last_order_at: datetime | None


class VendorPerformanceResponse(BaseModel):
    vendors: list[VendorPerformanceOut]


class PurchaseSuggestionOut(BaseModel):
    product_id: str
    name: str
    sku: str
    quantity_on_hand: int
    reorder_point: int
    recommended_order: int
    daily_demand: Decimal = Field(decimal_places=2)
    lead_time_days: int
    purchase_price: Decimal = Field(decimal_places=2)
    estimated_cost: Decimal = Field(decimal_places=2)
    currency: str


class PurchaseSuggestionsResponse(BaseModel):
    generated_at: datetime
    lookback_days: int
    lead_time_days: int
    safety_stock_days: int
    suggestions: list[PurchaseSuggestionOut]


class PurchaseDraftLineOut(BaseModel):
    product_id: str
    name: str
    sku: str
    quantity: int
    unit_cost: Decimal = Field(decimal_places=2)
    estimated_cost: Decimal = Field(decimal_places=2)
    currency: str


class PurchaseDraftSupplierOut(BaseModel):
    id: str
    name: str
    contact_email: str | None
    contact_phone: str | None


class PurchaseDraftResponse(BaseModel):
    generated_at: datetime
    supplier: PurchaseDraftSupplierOut | None
    total_estimated: Decimal = Field(decimal_places=2)
    currency: str | None
    lines: list[PurchaseDraftLineOut]
    lookback_days: int
    lead_time_days: int
    safety_stock_days: int
    budget_cap: Decimal | None = Field(default=None, decimal_places=2)
    capped: bool


# =============================================================================
# Advanced Forecast v2 Schemas
# =============================================================================

class SeasonalityFactorsOut(BaseModel):
    """Day-of-week seasonality factors."""
    monday: Decimal = Field(decimal_places=2)
    tuesday: Decimal = Field(decimal_places=2)
    wednesday: Decimal = Field(decimal_places=2)
    thursday: Decimal = Field(decimal_places=2)
    friday: Decimal = Field(decimal_places=2)
    saturday: Decimal = Field(decimal_places=2)
    sunday: Decimal = Field(decimal_places=2)


class AdvancedForecastInsightOut(BaseModel):
    """Advanced forecast result for a single product."""
    product_id: str
    name: str
    sku: str
    quantity_on_hand: int
    
    # Basic metrics
    daily_demand: Decimal = Field(decimal_places=2)
    daily_demand_smoothed: Decimal = Field(decimal_places=2)
    
    # Forecast outputs
    days_until_stockout: float
    projected_stockout_date: datetime
    recommended_reorder_date: datetime
    recommended_order: int
    
    # Advanced metrics
    forecast_method: str  # simple_average, exponential_smoothing, seasonal_adjusted
    confidence: str  # high, medium, low
    coefficient_of_variation: Decimal = Field(decimal_places=3)
    standard_deviation: Decimal = Field(decimal_places=2)
    
    # Confidence intervals (95%)
    demand_lower_bound: Decimal = Field(decimal_places=2)
    demand_upper_bound: Decimal = Field(decimal_places=2)
    stockout_best_case_days: float
    stockout_worst_case_days: float
    
    # Seasonality
    seasonality_factors: SeasonalityFactorsOut | None = None
    data_points_count: int


class AdvancedForecastResponse(BaseModel):
    """Response for advanced forecasting endpoint."""
    generated_at: datetime
    expires_at: datetime
    ttl_minutes: int
    stale: bool
    lookback_days: int
    lead_time_days: int
    safety_stock_days: int
    smoothing_alpha: Decimal = Field(decimal_places=2)
    use_seasonality: bool
    
    # Summary statistics
    total_products_analyzed: int
    high_confidence_count: int
    medium_confidence_count: int
    low_confidence_count: int
    
    forecasts: list[AdvancedForecastInsightOut]

