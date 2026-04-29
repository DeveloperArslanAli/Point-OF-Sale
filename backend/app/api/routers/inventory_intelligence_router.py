from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import INVENTORY_ROLES, MANAGEMENT_ROLES, require_roles
from app.api.schemas.inventory_intelligence import (
    ABCClassificationOut,
    DeadStockInsightOut,
    ForecastInsightOut,
    InventoryABCResponse,
    InventoryForecastResponse,
    InventoryInsightsResponse,
    LowStockInsightOut,
    VendorPerformanceOut,
    VendorPerformanceResponse,
    PurchaseSuggestionOut,
    PurchaseSuggestionsResponse,
    PurchaseDraftResponse,
    PurchaseDraftLineOut,
    PurchaseDraftSupplierOut,
    AdvancedForecastResponse,
    AdvancedForecastInsightOut,
    SeasonalityFactorsOut,
)
from app.application.inventory.use_cases.get_inventory_insights import (
    GetInventoryInsightsUseCase,
    InventoryInsightsInput,
)
from app.application.inventory.use_cases.get_inventory_abc import (
    GetInventoryABCUseCase,
    InventoryABCInput,
)
from app.application.inventory.use_cases.get_inventory_forecast import (
    GetInventoryForecastUseCase,
    InventoryForecastInput,
)
from app.application.inventory.use_cases.get_advanced_forecast import (
    GetAdvancedForecastUseCase,
    AdvancedForecastInput,
)
from app.application.inventory.use_cases.get_vendor_performance import GetVendorPerformanceUseCase
from app.application.inventory.use_cases.get_purchase_suggestions import (
    GetPurchaseSuggestionsUseCase,
    PurchaseSuggestionsInput,
)
from app.application.inventory.use_cases.generate_purchase_drafts import (
    GeneratePurchaseDraftsUseCase,
    PurchaseDraftResult,
)
from app.application.suppliers.ports import SupplierRepository
from app.infrastructure.db.repositories.purchase_repository import SqlAlchemyPurchaseRepository
from app.infrastructure.db.repositories.supplier_repository import SqlAlchemySupplierRepository
from app.infrastructure.db.repositories.inventory_movement_repository import (
    SqlAlchemyInventoryMovementRepository,
)
from app.infrastructure.db.repositories.inventory_repository import SqlAlchemyProductRepository
from app.infrastructure.db.session import get_session

router = APIRouter(prefix="/inventory/intelligence", tags=["inventory"])


# ==================== Request/Response Models for Tasks ====================

class ForecastRefreshRequest(BaseModel):
    """Request to trigger forecast recomputation."""
    smoothing_alpha: float = Field(0.3, ge=0.1, le=0.9, description="Exponential smoothing factor")
    seasonality: bool = Field(False, description="Enable seasonal adjustment")
    lookback_days: int = Field(90, ge=30, le=365, description="Days of historical data")


class TaskSubmittedResponse(BaseModel):
    """Response when a background task is submitted."""
    status: str
    task_id: str | None = None
    message: str


class AlertConfigRequest(BaseModel):
    """Request to configure and trigger low-stock alerts."""
    threshold_days: int = Field(7, ge=1, le=30, description="Alert threshold in days")
    email_recipients: list[str] = Field(default_factory=list, description="Email addresses to notify")
    enable_sms: bool = Field(False, description="Enable SMS notifications")


# ==================== Main Endpoints ====================


def _build_purchase_suggestions_response(result: Any) -> PurchaseSuggestionsResponse:
    return PurchaseSuggestionsResponse(
        generated_at=result.generated_at,
        lookback_days=result.lookback_days,
        lead_time_days=result.lead_time_days,
        safety_stock_days=result.safety_stock_days,
        suggestions=[
            PurchaseSuggestionOut(
                product_id=item.product.id,
                name=item.product.name,
                sku=item.product.sku,
                quantity_on_hand=item.stock.quantity_on_hand,
                reorder_point=item.reorder_point,
                recommended_order=item.recommended_order,
                daily_demand=item.daily_demand.quantize(Decimal("0.01")),
                lead_time_days=item.lead_time_days,
                purchase_price=item.unit_cost.quantize(Decimal("0.01")),
                estimated_cost=item.estimated_cost.quantize(Decimal("0.01")),
                currency=item.currency,
            )
            for item in result.suggestions
        ],
    )


async def _execute_purchase_suggestions(
    session: AsyncSession,
    lookback_days: int,
    lead_time_days: int,
    safety_stock_days: int,
    include_zero_demand: bool,
) -> PurchaseSuggestionsResponse:
    product_repo = SqlAlchemyProductRepository(session)
    inventory_repo = SqlAlchemyInventoryMovementRepository(session)
    use_case = GetPurchaseSuggestionsUseCase(product_repo, inventory_repo)

    result = await use_case.execute(
        PurchaseSuggestionsInput(
            lookback_days=lookback_days,
            lead_time_days=lead_time_days,
            safety_stock_days=safety_stock_days,
            include_zero_demand=include_zero_demand,
        )
    )

    return _build_purchase_suggestions_response(result)


@router.get("/purchase-suggestions", response_model=PurchaseSuggestionsResponse)
async def get_purchase_suggestions_legacy(
    lookback_days: int = Query(30, ge=7, le=365),
    lead_time_days: int = Query(7, ge=1, le=120),
    safety_stock_days: int = Query(2, ge=0, le=120),
    include_zero_demand: bool = Query(False),
    session: AsyncSession = Depends(get_session),
    _user=Depends(require_roles(*INVENTORY_ROLES)),
) -> PurchaseSuggestionsResponse:
    """Backward-compatible alias for older clients hitting /purchase-suggestions."""
    return await _execute_purchase_suggestions(
        session=session,
        lookback_days=lookback_days,
        lead_time_days=lead_time_days,
        safety_stock_days=safety_stock_days,
        include_zero_demand=include_zero_demand,
    )


@router.get("", response_model=InventoryInsightsResponse)
async def get_inventory_insights(
    lookback_days: int = Query(30, ge=1, le=180),
    lead_time_days: int = Query(7, ge=1, le=60),
    safety_stock_days: int = Query(2, ge=0, le=60),
    dead_stock_days: int = Query(90, ge=30, le=365),
    session: AsyncSession = Depends(get_session),
    _user=Depends(require_roles(*INVENTORY_ROLES)),
) -> InventoryInsightsResponse:
    product_repo = SqlAlchemyProductRepository(session)
    inventory_repo = SqlAlchemyInventoryMovementRepository(session)
    use_case = GetInventoryInsightsUseCase(product_repo, inventory_repo)

    result = await use_case.execute(
        InventoryInsightsInput(
            lookback_days=lookback_days,
            lead_time_days=lead_time_days,
            safety_stock_days=safety_stock_days,
            dead_stock_days=dead_stock_days,
        )
    )

    return InventoryInsightsResponse(
        generated_at=result.generated_at,
        lookback_days=result.lookback_days,
        lead_time_days=result.lead_time_days,
        safety_stock_days=result.safety_stock_days,
        low_stock=[
            LowStockInsightOut(
                product_id=ins.product.id,
                name=ins.product.name,
                sku=ins.product.sku,
                quantity_on_hand=ins.stock.quantity_on_hand,
                reorder_point=ins.reorder_point,
                recommended_order=ins.recommended_order,
                daily_demand=ins.daily_demand.quantize(Decimal("0.01")),
                last_movement_at=ins.last_movement_at,
            )
            for ins in result.low_stock
        ],
        dead_stock=[
            DeadStockInsightOut(
                product_id=ins.product.id,
                name=ins.product.name,
                sku=ins.product.sku,
                quantity_on_hand=ins.stock.quantity_on_hand,
                last_movement_at=ins.last_movement_at,
                days_since_movement=ins.days_since_movement,
            )
            for ins in result.dead_stock
        ],
    )


@router.get("/abc", response_model=InventoryABCResponse)
async def get_inventory_abc(
    lookback_days: int = Query(90, ge=30, le=365),
    a_threshold_percent: float = Query(70.0, ge=50.0, le=85.0),
    b_threshold_percent: float = Query(90.0, ge=80.0, le=98.0),
    session: AsyncSession = Depends(get_session),
    _user=Depends(require_roles(*INVENTORY_ROLES)),
) -> InventoryABCResponse:
    product_repo = SqlAlchemyProductRepository(session)
    inventory_repo = SqlAlchemyInventoryMovementRepository(session)
    use_case = GetInventoryABCUseCase(product_repo, inventory_repo)

    result = await use_case.execute(
        InventoryABCInput(
            lookback_days=lookback_days,
            a_threshold_percent=Decimal(a_threshold_percent),
            b_threshold_percent=Decimal(b_threshold_percent),
        )
    )

    return InventoryABCResponse(
        generated_at=result.generated_at,
        lookback_days=result.lookback_days,
        a_threshold_percent=result.a_threshold_percent,
        b_threshold_percent=result.b_threshold_percent,
        classifications=[
            ABCClassificationOut(
                product_id=item.product.id,
                name=item.product.name,
                sku=item.product.sku,
                usage_quantity=item.usage_quantity,
                usage_value=item.usage_value.quantize(Decimal("0.01")),
                cumulative_percent=item.cumulative_percent,
                abc_class=item.abc_class,
            )
            for item in result.classifications
        ],
    )


@router.get("/forecast", response_model=InventoryForecastResponse)
async def get_inventory_forecast(
    lookback_days: int = Query(60, ge=30, le=365),
    lead_time_days: int = Query(7, ge=1, le=90),
    safety_stock_days: int = Query(2, ge=0, le=90),
    include_zero_demand: bool = Query(False),
    ttl_minutes: int = Query(360, ge=30, le=1440),
    session: AsyncSession = Depends(get_session),
    _user=Depends(require_roles(*INVENTORY_ROLES)),
) -> InventoryForecastResponse:
    product_repo = SqlAlchemyProductRepository(session)
    inventory_repo = SqlAlchemyInventoryMovementRepository(session)
    use_case = GetInventoryForecastUseCase(product_repo, inventory_repo)

    result = await use_case.execute(
        InventoryForecastInput(
            lookback_days=lookback_days,
            lead_time_days=lead_time_days,
            safety_stock_days=safety_stock_days,
            include_zero_demand=include_zero_demand,
            ttl_minutes=ttl_minutes,
        )
    )

    return InventoryForecastResponse(
        generated_at=result.generated_at,
        expires_at=result.expires_at,
        ttl_minutes=result.ttl_minutes,
        stale=datetime.now(UTC) >= result.expires_at,
        lookback_days=result.lookback_days,
        lead_time_days=result.lead_time_days,
        safety_stock_days=result.safety_stock_days,
        forecasts=[
            ForecastInsightOut(
                product_id=item.product.id,
                name=item.product.name,
                sku=item.product.sku,
                quantity_on_hand=item.stock.quantity_on_hand,
                daily_demand=item.daily_demand.quantize(Decimal("0.01")),
                days_until_stockout=item.days_until_stockout,
                projected_stockout_date=item.projected_stockout_date,
                recommended_reorder_date=item.recommended_reorder_date,
                recommended_order=item.recommended_order,
            )
            for item in result.forecasts
        ],
    )


@router.get("/forecast/advanced", response_model=AdvancedForecastResponse)
async def get_advanced_forecast(
    lookback_days: int = Query(90, ge=30, le=365),
    lead_time_days: int = Query(7, ge=1, le=90),
    safety_stock_days: int = Query(3, ge=0, le=90),
    include_zero_demand: bool = Query(False),
    ttl_minutes: int = Query(360, ge=30, le=1440),
    smoothing_alpha: float = Query(0.3, ge=0.1, le=0.9),
    use_seasonality: bool = Query(True),
    min_data_points: int = Query(14, ge=7, le=90),
    session: AsyncSession = Depends(get_session),
    _user=Depends(require_roles(*INVENTORY_ROLES)),
) -> AdvancedForecastResponse:
    """Advanced forecasting with exponential smoothing and seasonality detection.
    
    Features:
    - Exponential smoothing for trend detection
    - Day-of-week seasonality factors
    - Confidence intervals (95%)
    - Coefficient of variation for forecast confidence assessment
    """
    product_repo = SqlAlchemyProductRepository(session)
    inventory_repo = SqlAlchemyInventoryMovementRepository(session)
    use_case = GetAdvancedForecastUseCase(product_repo, inventory_repo)

    result = await use_case.execute(
        AdvancedForecastInput(
            lookback_days=lookback_days,
            lead_time_days=lead_time_days,
            safety_stock_days=safety_stock_days,
            include_zero_demand=include_zero_demand,
            ttl_minutes=ttl_minutes,
            smoothing_alpha=Decimal(str(smoothing_alpha)),
            use_seasonality=use_seasonality,
            min_data_points=min_data_points,
        )
    )

    return AdvancedForecastResponse(
        generated_at=result.generated_at,
        expires_at=result.expires_at,
        ttl_minutes=result.ttl_minutes,
        stale=datetime.now(UTC) >= result.expires_at,
        lookback_days=result.lookback_days,
        lead_time_days=result.lead_time_days,
        safety_stock_days=result.safety_stock_days,
        smoothing_alpha=result.smoothing_alpha,
        use_seasonality=result.use_seasonality,
        total_products_analyzed=result.total_products_analyzed,
        high_confidence_count=result.high_confidence_count,
        medium_confidence_count=result.medium_confidence_count,
        low_confidence_count=result.low_confidence_count,
        forecasts=[
            AdvancedForecastInsightOut(
                product_id=item.product.id,
                name=item.product.name,
                sku=item.product.sku,
                quantity_on_hand=item.stock.quantity_on_hand,
                daily_demand=item.daily_demand.quantize(Decimal("0.01")),
                daily_demand_smoothed=item.daily_demand_smoothed.quantize(Decimal("0.01")),
                days_until_stockout=item.days_until_stockout,
                projected_stockout_date=item.projected_stockout_date,
                recommended_reorder_date=item.recommended_reorder_date,
                recommended_order=item.recommended_order,
                forecast_method=item.forecast_method.value,
                confidence=item.confidence.value,
                coefficient_of_variation=item.coefficient_of_variation,
                standard_deviation=item.standard_deviation,
                demand_lower_bound=item.demand_lower_bound,
                demand_upper_bound=item.demand_upper_bound,
                stockout_best_case_days=item.stockout_best_case_days,
                stockout_worst_case_days=item.stockout_worst_case_days,
                seasonality_factors=(
                    SeasonalityFactorsOut(
                        monday=item.seasonality_factors.monday,
                        tuesday=item.seasonality_factors.tuesday,
                        wednesday=item.seasonality_factors.wednesday,
                        thursday=item.seasonality_factors.thursday,
                        friday=item.seasonality_factors.friday,
                        saturday=item.seasonality_factors.saturday,
                        sunday=item.seasonality_factors.sunday,
                    )
                    if item.seasonality_factors else None
                ),
                data_points_count=item.data_points_count,
            )
            for item in result.forecasts
        ],
    )


@router.get("/vendors", response_model=VendorPerformanceResponse)
async def get_vendor_performance(
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    _user=Depends(require_roles(*INVENTORY_ROLES)),
) -> VendorPerformanceResponse:
    supplier_repo: SupplierRepository = SqlAlchemySupplierRepository(session)
    purchase_repo = SqlAlchemyPurchaseRepository(session)
    use_case = GetVendorPerformanceUseCase(supplier_repo, purchase_repo)
    results = await use_case.execute(limit=limit)

    return VendorPerformanceResponse(
        vendors=[
            VendorPerformanceOut(
                supplier_id=result.supplier.id,
                name=result.supplier.name,
                contact_email=result.supplier.contact_email,
                contact_phone=result.supplier.contact_phone,
                currency=result.performance.currency,
                total_orders=result.performance.total_orders,
                open_orders=result.performance.open_orders,
                total_amount=result.performance.total_amount.quantize(Decimal("0.01")),
                average_lead_time_hours=(
                    result.performance.average_lead_time_hours.quantize(Decimal("0.01"))
                    if result.performance.average_lead_time_hours is not None
                    else None
                ),
                last_order_at=result.performance.last_order_at,
            )
            for result in results
        ]
    )


@router.get("/po-suggestions", response_model=PurchaseSuggestionsResponse)
async def get_purchase_suggestions(
    lookback_days: int = Query(30, ge=7, le=365),
    lead_time_days: int = Query(7, ge=1, le=120),
    safety_stock_days: int = Query(2, ge=0, le=120),
    include_zero_demand: bool = Query(False),
    session: AsyncSession = Depends(get_session),
    _user=Depends(require_roles(*INVENTORY_ROLES)),
) -> PurchaseSuggestionsResponse:
    return await _execute_purchase_suggestions(
        session=session,
        lookback_days=lookback_days,
        lead_time_days=lead_time_days,
        safety_stock_days=safety_stock_days,
        include_zero_demand=include_zero_demand,
    )


@router.get("/po-drafts", response_model=PurchaseDraftResponse)
async def get_purchase_drafts(
    lookback_days: int = Query(30, ge=7, le=365),
    lead_time_days: int = Query(7, ge=1, le=120),
    safety_stock_days: int = Query(2, ge=0, le=120),
    include_zero_demand: bool = Query(False),
    supplier_id: str | None = Query(None, min_length=1, max_length=26),
    budget_cap: Decimal | None = Query(None, gt=0),
    session: AsyncSession = Depends(get_session),
    _user=Depends(require_roles(*INVENTORY_ROLES)),
) -> PurchaseDraftResponse:
    product_repo = SqlAlchemyProductRepository(session)
    inventory_repo = SqlAlchemyInventoryMovementRepository(session)
    supplier_repo: SupplierRepository = SqlAlchemySupplierRepository(session)
    purchase_repo = SqlAlchemyPurchaseRepository(session)
    use_case = GeneratePurchaseDraftsUseCase(product_repo, inventory_repo, supplier_repo, purchase_repo)

    result: PurchaseDraftResult = await use_case.execute(
        supplier_id=supplier_id,
        suggestions_input=PurchaseSuggestionsInput(
            lookback_days=lookback_days,
            lead_time_days=lead_time_days,
            safety_stock_days=safety_stock_days,
            include_zero_demand=include_zero_demand,
        ),
        budget_cap=budget_cap,
    )

    supplier_out = (
        PurchaseDraftSupplierOut(
            id=result.supplier.id,
            name=result.supplier.name,
            contact_email=result.supplier.contact_email,
            contact_phone=result.supplier.contact_phone,
        )
        if result.supplier
        else None
    )

    return PurchaseDraftResponse(
        generated_at=result.generated_at,
        supplier=supplier_out,
        total_estimated=result.total_estimated.quantize(Decimal("0.01")),
        currency=result.currency,
        lines=[
            PurchaseDraftLineOut(
                product_id=line.product_id,
                name=line.name,
                sku=line.sku,
                quantity=line.quantity,
                unit_cost=line.unit_cost.quantize(Decimal("0.01")),
                estimated_cost=line.estimated_cost.quantize(Decimal("0.01")),
                currency=line.currency,
            )
            for line in result.lines
        ],
        lookback_days=result.suggestions_meta.lookback_days,
        lead_time_days=result.suggestions_meta.lead_time_days,
        safety_stock_days=result.suggestions_meta.safety_stock_days,
        budget_cap=result.budget_cap.quantize(Decimal("0.01")) if result.budget_cap is not None else None,
        capped=result.capped,
    )


# ==================== Task Trigger Endpoints ====================

@router.post("/forecast/refresh", response_model=TaskSubmittedResponse)
async def trigger_forecast_refresh(
    request: ForecastRefreshRequest,
    _user=Depends(require_roles(*MANAGEMENT_ROLES)),
) -> TaskSubmittedResponse:
    """Trigger background task to recompute forecast model.
    
    Requires ADMIN or MANAGER role.
    
    The task runs asynchronously via Celery if available,
    otherwise returns a synchronous placeholder response.
    """
    try:
        from app.infrastructure.tasks.celery_app import CELERY_ENABLED
        
        if CELERY_ENABLED:
            from app.infrastructure.tasks.inventory_tasks import recompute_forecast_model
            
            task = recompute_forecast_model.apply_async(
                kwargs={
                    "smoothing_alpha": request.smoothing_alpha,
                    "seasonality": request.seasonality,
                    "lookback_days": request.lookback_days,
                }
            )
            
            return TaskSubmittedResponse(
                status="queued",
                task_id=task.id,
                message=f"Forecast recomputation queued with smoothing_alpha={request.smoothing_alpha}",
            )
        else:
            # Celery not available - return placeholder
            return TaskSubmittedResponse(
                status="skipped",
                task_id=None,
                message="Background tasks not available. Forecast data refreshes on GET requests.",
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to queue forecast refresh: {str(e)}"
        )


@router.post("/alerts/low-stock", response_model=TaskSubmittedResponse)
async def trigger_low_stock_alert(
    request: AlertConfigRequest,
    _user=Depends(require_roles(*MANAGEMENT_ROLES)),
) -> TaskSubmittedResponse:
    """Trigger low-stock alert check and notification.
    
    Requires ADMIN or MANAGER role.
    
    Sends email/SMS notifications for items below threshold.
    """
    try:
        from app.infrastructure.tasks.celery_app import CELERY_ENABLED
        
        if CELERY_ENABLED:
            from app.infrastructure.tasks.inventory_tasks import check_low_stock_alerts
            
            task = check_low_stock_alerts.apply_async(
                kwargs={
                    "threshold_days": request.threshold_days,
                    "email_recipients": request.email_recipients,
                    "enable_sms": request.enable_sms,
                }
            )
            
            return TaskSubmittedResponse(
                status="queued",
                task_id=task.id,
                message=f"Low stock alert check queued for {len(request.email_recipients)} recipients",
            )
        else:
            return TaskSubmittedResponse(
                status="skipped",
                task_id=None,
                message="Background tasks not available. Check /inventory/intelligence for low stock data.",
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to queue low stock alert: {str(e)}"
        )


@router.post("/alerts/dead-stock", response_model=TaskSubmittedResponse)
async def trigger_dead_stock_alert(
    days_inactive: int = Query(90, ge=30, le=365),
    email_recipients: list[str] = Query(default=[]),
    _user=Depends(require_roles(*MANAGEMENT_ROLES)),
) -> TaskSubmittedResponse:
    """Trigger dead stock report generation and notification.
    
    Requires ADMIN or MANAGER role.
    """
    try:
        from app.infrastructure.tasks.celery_app import CELERY_ENABLED
        
        if CELERY_ENABLED:
            from app.infrastructure.tasks.inventory_tasks import check_dead_stock_alerts
            
            task = check_dead_stock_alerts.apply_async(
                kwargs={
                    "days_inactive": days_inactive,
                    "email_recipients": email_recipients,
                }
            )
            
            return TaskSubmittedResponse(
                status="queued",
                task_id=task.id,
                message=f"Dead stock report queued (>{days_inactive} days inactive)",
            )
        else:
            return TaskSubmittedResponse(
                status="skipped",
                task_id=None,
                message="Background tasks not available. Check /inventory/intelligence for dead stock data.",
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to queue dead stock alert: {str(e)}"
        )
