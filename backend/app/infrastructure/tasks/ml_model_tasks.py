"""ML Model Training and Inference Tasks - Phase 23.

Celery tasks for:
- Training ML models (demand forecasting, churn, fraud, recommendations)
- Running inference/predictions
- Model management (save/load)

These tasks complement the data pipeline tasks in ml_data_pipeline.py.
"""

from __future__ import annotations

import json
import structlog
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import text

from app.infrastructure.db.session import async_session_factory
from app.infrastructure.tasks.celery_app import celery_app
from app.infrastructure.tasks.product_import_tasks import AsyncTask
from app.core.settings import get_settings

logger = structlog.get_logger(__name__)

# Model storage path
MODEL_STORAGE_PATH = Path("ml_models")


def _get_model_path(model_name: str, tenant_id: str | None = None) -> Path:
    """Get path for model storage."""
    base = MODEL_STORAGE_PATH / model_name
    if tenant_id:
        return base / tenant_id
    return base / "global"


# ==================== Demand Forecasting Tasks ====================

@celery_app.task(
    bind=True,
    base=AsyncTask,
    name="train_demand_forecast_model",
    max_retries=2,
)
def train_demand_forecast_model(
    self: AsyncTask,
    product_id: str,
    lookback_days: int = 180,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Train demand forecast model for a specific product.
    
    Args:
        product_id: Product to train model for
        lookback_days: Days of history to use
        tenant_id: Optional tenant filter
        
    Returns:
        Training metrics
    """
    return self(*[product_id, lookback_days, tenant_id])


@train_demand_forecast_model.run_async  # type: ignore
async def train_demand_forecast_model_async(
    product_id: str,
    lookback_days: int = 180,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Async implementation of demand forecast training."""
    from app.infrastructure.ml.demand_forecast import create_forecast_model
    
    logger.info(
        "train_demand_forecast_started",
        product_id=product_id,
        lookback_days=lookback_days,
    )
    
    session = None
    try:
        session = async_session_factory()
        now = datetime.now(UTC)
        lookback_start = now - timedelta(days=lookback_days)
        
        # Query daily sales data
        query = text("""
            SELECT 
                DATE(s.created_at) as sale_date,
                COALESCE(SUM(sl.quantity), 0) as quantity
            FROM sales s
            JOIN sale_lines sl ON sl.sale_id = s.id
            WHERE sl.product_id = :product_id
              AND s.created_at >= :lookback_start
              AND s.status = 'completed'
            GROUP BY DATE(s.created_at)
            ORDER BY sale_date
        """)
        
        params = {"product_id": product_id, "lookback_start": lookback_start}
        if tenant_id:
            query = text(str(query) + " AND s.tenant_id = :tenant_id")
            params["tenant_id"] = tenant_id
        
        result = await session.execute(query, params)
        rows = result.fetchall()
        
        if len(rows) < 30:
            return {
                "status": "insufficient_data",
                "data_points": len(rows),
                "required": 30,
            }
        
        # Create DataFrame for model
        df = pd.DataFrame([
            {"ds": row.sale_date, "y": float(row.quantity)}
            for row in rows
        ])
        
        # Fill missing dates with 0
        date_range = pd.date_range(start=df["ds"].min(), end=df["ds"].max())
        df = df.set_index("ds").reindex(date_range, fill_value=0).reset_index()
        df.columns = ["ds", "y"]
        
        # Train model
        model = create_forecast_model()
        
        # Try Prophet first
        prophet_metrics = model.train_prophet(df, product_id)
        
        # Also train XGBoost
        xgb_df = df.copy()
        xgb_df.columns = ["date", "quantity"]
        xgb_metrics = model.train_xgboost(xgb_df, product_id)
        
        # Save model
        model_path = _get_model_path("demand_forecast", tenant_id) / product_id
        model.save_model(model_path)
        
        return {
            "status": "success",
            "product_id": product_id,
            "data_points": len(df),
            "prophet_metrics": prophet_metrics,
            "xgboost_metrics": xgb_metrics,
            "model_path": str(model_path),
        }
        
    except Exception as e:
        logger.exception("train_demand_forecast_failed", product_id=product_id)
        return {"status": "error", "error": str(e)}
    finally:
        if session:
            await session.close()


@celery_app.task(
    bind=True,
    base=AsyncTask,
    name="predict_demand",
    max_retries=2,
)
def predict_demand(
    self: AsyncTask,
    product_id: str,
    periods: int = 30,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Generate demand predictions for a product.
    
    Args:
        product_id: Product to predict demand for
        periods: Number of days to forecast
        tenant_id: Optional tenant filter
        
    Returns:
        Forecast predictions
    """
    return self(*[product_id, periods, tenant_id])


@predict_demand.run_async  # type: ignore
async def predict_demand_async(
    product_id: str,
    periods: int = 30,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Async implementation of demand prediction."""
    from app.infrastructure.ml.demand_forecast import create_forecast_model
    
    model_path = _get_model_path("demand_forecast", tenant_id) / product_id
    
    if not model_path.exists():
        return {
            "status": "model_not_found",
            "message": "Run training first",
        }
    
    model = create_forecast_model()
    model.load_model(model_path)
    
    forecasts = model.predict_prophet(periods)
    
    return {
        "status": "success",
        "product_id": product_id,
        "periods": periods,
        "forecasts": [f.to_dict() for f in forecasts],
        "total_7d": sum(f.predicted_demand for f in forecasts[:7]),
        "total_30d": sum(f.predicted_demand for f in forecasts[:30]),
    }


# ==================== Churn Prediction Tasks ====================

@celery_app.task(
    bind=True,
    base=AsyncTask,
    name="train_churn_model",
    max_retries=2,
)
def train_churn_model(
    self: AsyncTask,
    lookback_days: int = 365,
    churn_threshold_days: int = 60,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Train customer churn prediction model.
    
    Args:
        lookback_days: Days of history for RFM calculation
        churn_threshold_days: Days inactive to define churn
        tenant_id: Optional tenant filter
        
    Returns:
        Training metrics
    """
    return self(*[lookback_days, churn_threshold_days, tenant_id])


@train_churn_model.run_async  # type: ignore
async def train_churn_model_async(
    lookback_days: int = 365,
    churn_threshold_days: int = 60,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Async implementation of churn model training."""
    from app.infrastructure.ml.churn_prediction import create_churn_model
    
    logger.info(
        "train_churn_model_started",
        lookback_days=lookback_days,
        churn_threshold=churn_threshold_days,
    )
    
    session = None
    try:
        session = async_session_factory()
        now = datetime.now(UTC)
        lookback_start = now - timedelta(days=lookback_days)
        
        # Query customer RFM features
        query = text("""
            SELECT 
                c.id as customer_id,
                c.created_at as registration_date,
                MAX(s.created_at) as last_purchase_date,
                COUNT(DISTINCT s.id) as frequency,
                COALESCE(SUM(s.total_amount), 0) as monetary,
                COALESCE(AVG(s.total_amount), 0) as avg_order_value
            FROM customers c
            LEFT JOIN sales s ON s.customer_id = c.id 
                AND s.created_at >= :lookback_start
                AND s.status = 'completed'
            WHERE c.is_active = true
            GROUP BY c.id, c.created_at
            HAVING COUNT(DISTINCT s.id) > 0
        """)
        
        result = await session.execute(query, {"lookback_start": lookback_start})
        rows = result.fetchall()
        
        if len(rows) < 100:
            return {
                "status": "insufficient_data",
                "customers": len(rows),
                "required": 100,
            }
        
        # Create DataFrame
        data = []
        for row in rows:
            recency_days = (now - row.last_purchase_date).days if row.last_purchase_date else lookback_days
            days_since_reg = (now - row.registration_date).days if row.registration_date else 365
            
            data.append({
                "customer_id": str(row.customer_id),
                "recency_days": recency_days,
                "frequency": row.frequency,
                "monetary": float(row.monetary),
                "avg_order_value": float(row.avg_order_value),
                "days_since_registration": days_since_reg,
                "return_rate": 0.0,  # TODO: Calculate from returns
            })
        
        df = pd.DataFrame(data)
        
        # Train model
        model = create_churn_model(churn_threshold_days=churn_threshold_days)
        metrics = model.train(df)
        
        # Save model
        model_path = _get_model_path("churn", tenant_id)
        model.save_model(model_path)
        
        return {
            "status": "success",
            "customers_trained": len(df),
            "auc_roc": metrics.auc_roc,
            "precision": metrics.precision,
            "recall": metrics.recall,
            "f1_score": metrics.f1_score,
            "model_path": str(model_path),
        }
        
    except Exception as e:
        logger.exception("train_churn_model_failed")
        return {"status": "error", "error": str(e)}
    finally:
        if session:
            await session.close()


@celery_app.task(
    bind=True,
    base=AsyncTask,
    name="predict_churn",
    max_retries=2,
)
def predict_churn(
    self: AsyncTask,
    customer_ids: list[str] | None = None,
    risk_threshold: float = 0.5,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Predict churn probability for customers.
    
    Args:
        customer_ids: Specific customers to predict (None = all)
        risk_threshold: Minimum churn probability to include
        tenant_id: Optional tenant filter
        
    Returns:
        Churn predictions
    """
    return self(*[customer_ids, risk_threshold, tenant_id])


@predict_churn.run_async  # type: ignore
async def predict_churn_async(
    customer_ids: list[str] | None = None,
    risk_threshold: float = 0.5,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Async implementation of churn prediction."""
    from app.infrastructure.ml.churn_prediction import create_churn_model
    
    model_path = _get_model_path("churn", tenant_id)
    
    if not model_path.exists():
        return {
            "status": "model_not_found",
            "message": "Run training first",
        }
    
    session = None
    try:
        session = async_session_factory()
        now = datetime.now(UTC)
        lookback_start = now - timedelta(days=365)
        
        # Build query
        query_str = """
            SELECT 
                c.id as customer_id,
                c.created_at as registration_date,
                MAX(s.created_at) as last_purchase_date,
                COUNT(DISTINCT s.id) as frequency,
                COALESCE(SUM(s.total_amount), 0) as monetary,
                COALESCE(AVG(s.total_amount), 0) as avg_order_value
            FROM customers c
            LEFT JOIN sales s ON s.customer_id = c.id 
                AND s.created_at >= :lookback_start
                AND s.status = 'completed'
            WHERE c.is_active = true
        """
        
        params = {"lookback_start": lookback_start}
        
        if customer_ids:
            query_str += " AND c.id = ANY(:customer_ids)"
            params["customer_ids"] = customer_ids
        
        query_str += " GROUP BY c.id, c.created_at"
        
        result = await session.execute(text(query_str), params)
        rows = result.fetchall()
        
        # Create DataFrame
        data = []
        for row in rows:
            recency_days = (now - row.last_purchase_date).days if row.last_purchase_date else 365
            days_since_reg = (now - row.registration_date).days if row.registration_date else 365
            
            data.append({
                "customer_id": str(row.customer_id),
                "recency_days": recency_days,
                "frequency": row.frequency,
                "monetary": float(row.monetary),
                "avg_order_value": float(row.avg_order_value),
                "days_since_registration": days_since_reg,
                "return_rate": 0.0,
            })
        
        df = pd.DataFrame(data)
        
        # Load model and predict
        model = create_churn_model()
        model.load_model(model_path)
        
        predictions = model.get_at_risk_customers(df, risk_threshold)
        
        return {
            "status": "success",
            "customers_analyzed": len(df),
            "at_risk_count": len(predictions),
            "predictions": [p.to_dict() for p in predictions[:100]],  # Limit response size
        }
        
    except Exception as e:
        logger.exception("predict_churn_failed")
        return {"status": "error", "error": str(e)}
    finally:
        if session:
            await session.close()


# ==================== Fraud Detection Tasks ====================

@celery_app.task(
    bind=True,
    base=AsyncTask,
    name="train_fraud_model",
    max_retries=2,
)
def train_fraud_model(
    self: AsyncTask,
    lookback_days: int = 90,
    contamination: float = 0.01,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Train fraud detection model.
    
    Args:
        lookback_days: Days of transaction history
        contamination: Expected fraud rate
        tenant_id: Optional tenant filter
        
    Returns:
        Training metrics
    """
    return self(*[lookback_days, contamination, tenant_id])


@train_fraud_model.run_async  # type: ignore
async def train_fraud_model_async(
    lookback_days: int = 90,
    contamination: float = 0.01,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Async implementation of fraud model training."""
    from app.infrastructure.ml.fraud_detection import create_fraud_model
    
    logger.info(
        "train_fraud_model_started",
        lookback_days=lookback_days,
        contamination=contamination,
    )
    
    session = None
    try:
        session = async_session_factory()
        now = datetime.now(UTC)
        lookback_start = now - timedelta(days=lookback_days)
        
        # Query transaction data
        query = text("""
            SELECT 
                s.id as transaction_id,
                s.total_amount as transaction_amount,
                (SELECT COUNT(*) FROM sale_lines sl WHERE sl.sale_id = s.id) as items_count,
                EXTRACT(HOUR FROM s.created_at) as hour_of_day,
                EXTRACT(DOW FROM s.created_at) as day_of_week,
                COALESCE(s.discount_amount, 0) as discount_amount,
                s.cashier_id,
                s.status
            FROM sales s
            WHERE s.created_at >= :lookback_start
        """)
        
        result = await session.execute(query, {"lookback_start": lookback_start})
        rows = result.fetchall()
        
        if len(rows) < 1000:
            return {
                "status": "insufficient_data",
                "transactions": len(rows),
                "required": 1000,
            }
        
        # Create DataFrame
        data = []
        for row in rows:
            discount_percent = 0
            if row.transaction_amount and row.transaction_amount > 0:
                discount_percent = (row.discount_amount / row.transaction_amount) * 100
            
            data.append({
                "transaction_id": str(row.transaction_id),
                "transaction_amount": float(row.transaction_amount or 0),
                "items_count": row.items_count or 1,
                "hour_of_day": int(row.hour_of_day or 12),
                "day_of_week": int(row.day_of_week or 3),
                "discount_percent": discount_percent,
                "is_void": 1 if row.status == "voided" else 0,
                "velocity_last_hour": 1,  # TODO: Calculate actual velocity
            })
        
        df = pd.DataFrame(data)
        
        # Train model
        model = create_fraud_model(contamination=contamination)
        metrics = model.train(df)
        
        # Save model
        model_path = _get_model_path("fraud", tenant_id)
        model.save_model(model_path)
        
        return {
            "status": "success",
            "transactions_trained": len(df),
            "anomalies_detected": metrics.anomalies_detected,
            "contamination_rate": metrics.contamination_rate,
            "model_path": str(model_path),
        }
        
    except Exception as e:
        logger.exception("train_fraud_model_failed")
        return {"status": "error", "error": str(e)}
    finally:
        if session:
            await session.close()


@celery_app.task(
    bind=True,
    base=AsyncTask,
    name="score_transaction_fraud",
    max_retries=2,
)
def score_transaction_fraud(
    self: AsyncTask,
    transaction_id: str,
    transaction_amount: float,
    items_count: int = 1,
    hour_of_day: int = 12,
    payment_method: str = "card",
    discount_percent: float = 0,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Score a single transaction for fraud in real-time."""
    return self(*[
        transaction_id, transaction_amount, items_count,
        hour_of_day, payment_method, discount_percent, tenant_id
    ])


@score_transaction_fraud.run_async  # type: ignore
async def score_transaction_fraud_async(
    transaction_id: str,
    transaction_amount: float,
    items_count: int = 1,
    hour_of_day: int = 12,
    payment_method: str = "card",
    discount_percent: float = 0,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Async implementation of fraud scoring."""
    from app.infrastructure.ml.fraud_detection import create_fraud_model
    
    model_path = _get_model_path("fraud", tenant_id)
    
    model = create_fraud_model()
    if model_path.exists():
        model.load_model(model_path)
    
    # Score the transaction
    score = model.score_single(
        transaction_id=transaction_id,
        transaction_amount=transaction_amount,
        items_count=items_count,
        hour_of_day=hour_of_day,
        payment_method=payment_method,
        discount_percent=discount_percent,
    )
    
    return {
        "status": "success",
        "score": score.to_dict() if score else None,
    }


# ==================== Recommendation Tasks ====================

@celery_app.task(
    bind=True,
    base=AsyncTask,
    name="train_recommendation_model",
    max_retries=2,
)
def train_recommendation_model(
    self: AsyncTask,
    lookback_days: int = 180,
    min_support: float = 0.01,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Train product recommendation model.
    
    Args:
        lookback_days: Days of transaction history
        min_support: Minimum support for association rules
        tenant_id: Optional tenant filter
        
    Returns:
        Training metrics
    """
    return self(*[lookback_days, min_support, tenant_id])


@train_recommendation_model.run_async  # type: ignore
async def train_recommendation_model_async(
    lookback_days: int = 180,
    min_support: float = 0.01,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Async implementation of recommendation model training."""
    from app.infrastructure.ml.recommendations import create_recommendation_engine
    
    logger.info(
        "train_recommendation_model_started",
        lookback_days=lookback_days,
        min_support=min_support,
    )
    
    session = None
    try:
        session = async_session_factory()
        now = datetime.now(UTC)
        lookback_start = now - timedelta(days=lookback_days)
        
        # Query transaction-product data
        query = text("""
            SELECT 
                s.id as transaction_id,
                s.customer_id,
                sl.product_id,
                p.name as product_name
            FROM sales s
            JOIN sale_lines sl ON sl.sale_id = s.id
            JOIN products p ON p.id = sl.product_id
            WHERE s.created_at >= :lookback_start
              AND s.status = 'completed'
        """)
        
        result = await session.execute(query, {"lookback_start": lookback_start})
        rows = result.fetchall()
        
        if len(rows) < 1000:
            return {
                "status": "insufficient_data",
                "transaction_lines": len(rows),
                "required": 1000,
            }
        
        # Create DataFrame
        df = pd.DataFrame([
            {
                "transaction_id": str(row.transaction_id),
                "customer_id": str(row.customer_id) if row.customer_id else None,
                "product_id": str(row.product_id),
            }
            for row in rows
        ])
        
        # Product names
        product_names = {
            str(row.product_id): row.product_name
            for row in rows
        }
        
        # Train model
        engine = create_recommendation_engine(min_support=min_support)
        metrics = engine.train_association_rules(df, product_names)
        
        # Also train collaborative filtering
        if df["customer_id"].notna().sum() > 100:
            engine.train_collaborative(df[df["customer_id"].notna()])
        
        # Save model
        model_path = _get_model_path("recommendations", tenant_id)
        engine.save_model(model_path)
        
        return {
            "status": "success",
            "baskets": metrics.total_baskets,
            "products": metrics.unique_products,
            "rules_generated": metrics.rules_generated,
            "avg_basket_size": round(metrics.avg_basket_size, 2),
            "model_path": str(model_path),
        }
        
    except Exception as e:
        logger.exception("train_recommendation_model_failed")
        return {"status": "error", "error": str(e)}
    finally:
        if session:
            await session.close()


@celery_app.task(
    bind=True,
    base=AsyncTask,
    name="get_recommendations",
    max_retries=2,
)
def get_recommendations(
    self: AsyncTask,
    cart_products: list[str],
    customer_id: str | None = None,
    n_recommendations: int = 5,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Get product recommendations for a cart."""
    return self(*[cart_products, customer_id, n_recommendations, tenant_id])


@get_recommendations.run_async  # type: ignore
async def get_recommendations_async(
    cart_products: list[str],
    customer_id: str | None = None,
    n_recommendations: int = 5,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    """Async implementation of recommendation generation."""
    from app.infrastructure.ml.recommendations import create_recommendation_engine
    
    model_path = _get_model_path("recommendations", tenant_id)
    
    if not model_path.exists():
        return {
            "status": "model_not_found",
            "message": "Run training first",
        }
    
    engine = create_recommendation_engine()
    engine.load_model(model_path)
    
    recommendations = engine.get_recommendations(
        cart_products=cart_products,
        customer_id=customer_id,
        n_recommendations=n_recommendations,
    )
    
    # Also get bundle suggestions
    bundles = engine.suggest_bundles(cart_products)
    
    return {
        "status": "success",
        "cart_size": len(cart_products),
        "recommendations": [r.to_dict() for r in recommendations],
        "bundles": bundles,
    }
