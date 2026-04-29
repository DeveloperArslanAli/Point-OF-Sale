"""ML Models API Router - Phase 23.

Provides REST endpoints for:
- Demand forecasting (training + prediction)
- Customer churn prediction
- Fraud detection/scoring
- Product recommendations

All ML operations are async via Celery tasks.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.dependencies.auth import MANAGEMENT_ROLES, SALES_ROLES, require_roles
from app.domain.auth.entities import User


router = APIRouter(prefix="/ml", tags=["Machine Learning"])


# ==================== Request/Response Models ====================

class TrainModelRequest(BaseModel):
    """Request to train an ML model."""
    lookback_days: int = Field(default=180, ge=30, le=730)
    tenant_id: str | None = None


class TrainDemandForecastRequest(TrainModelRequest):
    """Request to train demand forecast model."""
    product_id: str


class TrainChurnModelRequest(TrainModelRequest):
    """Request to train churn prediction model."""
    churn_threshold_days: int = Field(default=60, ge=14, le=180)


class TrainFraudModelRequest(TrainModelRequest):
    """Request to train fraud detection model."""
    contamination: float = Field(default=0.01, ge=0.001, le=0.1)


class TrainRecommendationRequest(TrainModelRequest):
    """Request to train recommendation model."""
    min_support: float = Field(default=0.01, ge=0.001, le=0.1)


class PredictDemandRequest(BaseModel):
    """Request for demand prediction."""
    product_id: str
    periods: int = Field(default=30, ge=1, le=90)


class PredictChurnRequest(BaseModel):
    """Request for churn prediction."""
    customer_ids: list[str] | None = None
    risk_threshold: float = Field(default=0.5, ge=0.1, le=0.9)


class ScoreFraudRequest(BaseModel):
    """Request for fraud scoring."""
    transaction_id: str
    transaction_amount: float = Field(ge=0)
    items_count: int = Field(default=1, ge=1)
    hour_of_day: int = Field(default=12, ge=0, le=23)
    payment_method: str = "card"
    discount_percent: float = Field(default=0, ge=0, le=100)


class GetRecommendationsRequest(BaseModel):
    """Request for product recommendations."""
    cart_products: list[str] = Field(min_length=1)
    customer_id: str | None = None
    n_recommendations: int = Field(default=5, ge=1, le=20)


class TaskResponse(BaseModel):
    """Response for async task submission."""
    task_id: str
    status: str
    message: str


class ModelStatusResponse(BaseModel):
    """Response for model status check."""
    ml_model_name: str
    is_trained: bool
    last_trained: datetime | None = None
    metrics: dict[str, Any] = {}


class ForecastResult(BaseModel):
    """Single forecast prediction."""
    date: datetime
    predicted_demand: float
    lower_bound: float
    upper_bound: float
    confidence: float


class DemandForecastResponse(BaseModel):
    """Response for demand forecast."""
    product_id: str
    periods: int
    forecasts: list[ForecastResult]
    total_7d: float
    total_30d: float


class ChurnPrediction(BaseModel):
    """Single churn prediction."""
    customer_id: str
    churn_probability: float
    risk_tier: str
    days_since_last_purchase: int
    lifetime_value: float
    contributing_factors: list[dict[str, Any]]


class ChurnPredictionResponse(BaseModel):
    """Response for churn prediction."""
    customers_analyzed: int
    at_risk_count: int
    predictions: list[ChurnPrediction]


class FraudScore(BaseModel):
    """Fraud detection score."""
    transaction_id: str
    anomaly_score: float
    is_fraud: bool
    severity: str
    indicators: list[str]
    rule_triggers: list[str]
    recommended_action: str


class FraudScoreResponse(BaseModel):
    """Response for fraud scoring."""
    score: FraudScore


class ProductRecommendation(BaseModel):
    """Single product recommendation."""
    product_id: str
    product_name: str
    confidence: float
    support: float
    lift: float
    reason: str


class BundleSuggestion(BaseModel):
    """Bundle suggestion."""
    products: list[ProductRecommendation]
    bundle_strength: float
    purchase_probability: float
    suggested_discount_percent: int


class RecommendationResponse(BaseModel):
    """Response for product recommendations."""
    cart_size: int
    recommendations: list[ProductRecommendation]
    bundles: list[BundleSuggestion]


# ==================== Training Endpoints ====================

@router.post(
    "/train/demand-forecast",
    response_model=TaskResponse,
    summary="Train demand forecast model for a product",
)
async def train_demand_forecast(
    request: TrainDemandForecastRequest,
    _: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> TaskResponse:
    """Train Prophet/XGBoost demand forecasting model for a specific product.
    
    Requires at least 30 days of sales history.
    Training runs asynchronously via Celery.
    """
    from app.infrastructure.tasks.ml_model_tasks import train_demand_forecast_model
    
    task = train_demand_forecast_model.delay(
        product_id=request.product_id,
        lookback_days=request.lookback_days,
        tenant_id=request.tenant_id,
    )
    
    return TaskResponse(
        task_id=task.id,
        status="submitted",
        message=f"Training demand forecast model for product {request.product_id}",
    )


@router.post(
    "/train/churn",
    response_model=TaskResponse,
    summary="Train customer churn prediction model",
)
async def train_churn_model(
    request: TrainChurnModelRequest,
    _: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> TaskResponse:
    """Train XGBoost churn prediction model.
    
    Uses RFM (Recency, Frequency, Monetary) features.
    Requires at least 100 customers with purchase history.
    """
    from app.infrastructure.tasks.ml_model_tasks import train_churn_model
    
    task = train_churn_model.delay(
        lookback_days=request.lookback_days,
        churn_threshold_days=request.churn_threshold_days,
        tenant_id=request.tenant_id,
    )
    
    return TaskResponse(
        task_id=task.id,
        status="submitted",
        message="Training churn prediction model",
    )


@router.post(
    "/train/fraud",
    response_model=TaskResponse,
    summary="Train fraud detection model",
)
async def train_fraud_model(
    request: TrainFraudModelRequest,
    _: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> TaskResponse:
    """Train Isolation Forest fraud detection model.
    
    Uses transaction patterns to detect anomalies.
    Requires at least 1000 transactions.
    """
    from app.infrastructure.tasks.ml_model_tasks import train_fraud_model
    
    task = train_fraud_model.delay(
        lookback_days=request.lookback_days,
        contamination=request.contamination,
        tenant_id=request.tenant_id,
    )
    
    return TaskResponse(
        task_id=task.id,
        status="submitted",
        message="Training fraud detection model",
    )


@router.post(
    "/train/recommendations",
    response_model=TaskResponse,
    summary="Train product recommendation model",
)
async def train_recommendation_model(
    request: TrainRecommendationRequest,
    _: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> TaskResponse:
    """Train association rules recommendation model.
    
    Uses market basket analysis for "frequently bought together".
    Requires at least 1000 multi-item transactions.
    """
    from app.infrastructure.tasks.ml_model_tasks import train_recommendation_model
    
    task = train_recommendation_model.delay(
        lookback_days=request.lookback_days,
        min_support=request.min_support,
        tenant_id=request.tenant_id,
    )
    
    return TaskResponse(
        task_id=task.id,
        status="submitted",
        message="Training recommendation model",
    )


# ==================== Prediction Endpoints ====================

@router.post(
    "/predict/demand",
    response_model=TaskResponse,
    summary="Predict demand for a product",
)
async def predict_demand(
    request: PredictDemandRequest,
    _: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> TaskResponse:
    """Generate demand forecasts for a product.
    
    Requires trained model (call /train/demand-forecast first).
    Returns forecasts for specified number of periods (days).
    """
    from app.infrastructure.tasks.ml_model_tasks import predict_demand
    
    task = predict_demand.delay(
        product_id=request.product_id,
        periods=request.periods,
    )
    
    return TaskResponse(
        task_id=task.id,
        status="submitted",
        message=f"Generating {request.periods}-day demand forecast",
    )


@router.post(
    "/predict/churn",
    response_model=TaskResponse,
    summary="Predict customer churn",
)
async def predict_churn(
    request: PredictChurnRequest,
    _: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> TaskResponse:
    """Predict churn probability for customers.
    
    Returns customers above risk threshold, sorted by churn probability.
    If customer_ids not provided, analyzes all customers.
    """
    from app.infrastructure.tasks.ml_model_tasks import predict_churn
    
    task = predict_churn.delay(
        customer_ids=request.customer_ids,
        risk_threshold=request.risk_threshold,
    )
    
    return TaskResponse(
        task_id=task.id,
        status="submitted",
        message="Analyzing customer churn risk",
    )


@router.post(
    "/score/fraud",
    response_model=FraudScoreResponse,
    summary="Score transaction for fraud (real-time)",
)
async def score_fraud(
    request: ScoreFraudRequest,
    _: User = Depends(require_roles(*SALES_ROLES)),
) -> FraudScoreResponse:
    """Score a transaction for fraud in real-time.
    
    Combines ML-based anomaly detection with rule-based triggers.
    Returns immediately (synchronous for POS integration).
    """
    from app.infrastructure.ml.fraud_detection import create_fraud_model
    from pathlib import Path
    
    model_path = Path("ml_models/fraud/global")
    
    model = create_fraud_model()
    if model_path.exists():
        model.load_model(model_path)
    
    score = model.score_single(
        transaction_id=request.transaction_id,
        transaction_amount=request.transaction_amount,
        items_count=request.items_count,
        hour_of_day=request.hour_of_day,
        payment_method=request.payment_method,
        discount_percent=request.discount_percent,
    )
    
    if not score:
        raise HTTPException(status_code=500, detail="Failed to score transaction")
    
    return FraudScoreResponse(
        score=FraudScore(
            transaction_id=score.transaction_id,
            anomaly_score=score.anomaly_score,
            is_fraud=score.is_fraud,
            severity=score.severity.value,
            indicators=[i.value for i in score.indicators],
            rule_triggers=score.rule_triggers,
            recommended_action=score.recommended_action,
        )
    )


@router.post(
    "/recommendations",
    response_model=RecommendationResponse,
    summary="Get product recommendations",
)
async def get_recommendations(
    request: GetRecommendationsRequest,
    _: User = Depends(require_roles(*SALES_ROLES)),
) -> RecommendationResponse:
    """Get product recommendations based on cart contents.
    
    Returns "frequently bought together" suggestions.
    Synchronous for POS integration.
    """
    from app.infrastructure.ml.recommendations import create_recommendation_engine
    from pathlib import Path
    
    model_path = Path("ml_models/recommendations/global")
    
    if not model_path.exists():
        # Return empty recommendations if model not trained
        return RecommendationResponse(
            cart_size=len(request.cart_products),
            recommendations=[],
            bundles=[],
        )
    
    engine = create_recommendation_engine()
    engine.load_model(model_path)
    
    recs = engine.get_recommendations(
        cart_products=request.cart_products,
        customer_id=request.customer_id,
        n_recommendations=request.n_recommendations,
    )
    
    bundles = engine.suggest_bundles(request.cart_products)
    
    return RecommendationResponse(
        cart_size=len(request.cart_products),
        recommendations=[
            ProductRecommendation(
                product_id=r.product_id,
                product_name=r.product_name,
                confidence=r.confidence,
                support=r.support,
                lift=r.lift,
                reason=r.reason,
            )
            for r in recs
        ],
        bundles=[
            BundleSuggestion(
                products=[
                    ProductRecommendation(**p) for p in b["products"]
                ],
                bundle_strength=b["bundle_strength"],
                purchase_probability=b["purchase_probability"],
                suggested_discount_percent=b["suggested_discount_percent"],
            )
            for b in bundles
        ],
    )


# ==================== Status Endpoints ====================

@router.get(
    "/status/{model_name}",
    response_model=ModelStatusResponse,
    summary="Get model training status",
)
async def get_model_status(
    model_name: str,
    _: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> ModelStatusResponse:
    """Check if a model is trained and get its metrics.
    
    Valid model names: demand-forecast, churn, fraud, recommendations
    """
    from pathlib import Path
    import json
    
    valid_models = ["demand-forecast", "churn", "fraud", "recommendations"]
    if model_name not in valid_models:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model name. Valid: {valid_models}",
        )
    
    # Map model name to directory
    model_dirs = {
        "demand-forecast": "demand_forecast",
        "churn": "churn",
        "fraud": "fraud",
        "recommendations": "recommendations",
    }
    
    model_path = Path("ml_models") / model_dirs[model_name] / "global"
    
    is_trained = model_path.exists()
    last_trained = None
    metrics = {}
    
    if is_trained:
        config_path = model_path / "config.json"
        if config_path.exists():
            last_trained = datetime.fromtimestamp(config_path.stat().st_mtime)
            with open(config_path) as f:
                metrics = json.load(f)
    
    return ModelStatusResponse(
        ml_model_name=model_name,
        is_trained=is_trained,
        last_trained=last_trained,
        metrics=metrics,
    )


@router.get(
    "/task/{task_id}",
    summary="Get async task status",
)
async def get_task_status(
    task_id: str,
    _: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> dict[str, Any]:
    """Check the status of an async ML task.
    
    Returns task state and result when complete.
    """
    from celery.result import AsyncResult
    from app.infrastructure.tasks.celery_app import celery_app
    
    result = AsyncResult(task_id, app=celery_app)
    
    response = {
        "task_id": task_id,
        "status": result.status,
        "ready": result.ready(),
    }
    
    if result.ready():
        if result.successful():
            response["result"] = result.result
        elif result.failed():
            response["error"] = str(result.result)
    
    return response
