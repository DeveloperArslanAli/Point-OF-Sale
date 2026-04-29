"""ML Data Pipeline Tasks - Phase 23.

Celery tasks for extracting, transforming, and storing ML training data.
Supports feature engineering for:
- Demand forecasting
- Customer churn prediction
- Fraud detection
- Product recommendations

Data is extracted from production tables and stored in Redis feature store
and optionally exported to Parquet files for batch training.
"""

from __future__ import annotations

import json
import structlog
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from dataclasses import dataclass, asdict

import redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text

from app.infrastructure.db.session import async_session_factory
from app.infrastructure.db.models.sale_model import SaleModel, SaleLineModel
from app.infrastructure.db.models.customer_model import CustomerModel
from app.infrastructure.db.models.product_model import ProductModel
from app.infrastructure.db.models.return_model import ReturnModel
from app.infrastructure.tasks.celery_app import celery_app
from app.infrastructure.tasks.product_import_tasks import AsyncTask
from app.core.settings import get_settings

logger = structlog.get_logger(__name__)

# Redis keys for feature store
FEATURE_STORE_PREFIX = "ml:features"
CUSTOMER_FEATURES_KEY = f"{FEATURE_STORE_PREFIX}:customer"
PRODUCT_FEATURES_KEY = f"{FEATURE_STORE_PREFIX}:product"
TRAINING_DATA_KEY = f"{FEATURE_STORE_PREFIX}:training"

# Feature TTL (7 days)
FEATURE_TTL_SECONDS = 7 * 24 * 3600


def _get_redis_client() -> redis.Redis | None:
    """Get Redis client for feature store."""
    settings = get_settings()
    if not settings.CELERY_BROKER_URL:
        return None
    try:
        return redis.from_url(
            settings.CELERY_BROKER_URL,
            decode_responses=True,
            socket_timeout=10,
        )
    except Exception as e:
        logger.warning("redis_ml_connection_failed", error=str(e))
        return None


# ==================== Data Classes ====================

@dataclass
class CustomerFeatures:
    """Customer features for ML models."""
    customer_id: str
    recency_days: int  # Days since last purchase
    frequency: int  # Total number of orders
    monetary: float  # Total lifetime value
    avg_order_value: float
    avg_basket_size: float
    preferred_categories: list[str]
    loyalty_points: int
    loyalty_tier: str | None
    days_since_registration: int
    return_rate: float
    churn_probability: float | None = None
    updated_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ProductFeatures:
    """Product features for ML models."""
    product_id: str
    sku: str
    category_id: str | None
    abc_class: str
    daily_velocity: float  # Average units sold per day
    demand_forecast_7d: float
    demand_forecast_30d: float
    seasonality_index: float
    coefficient_of_variation: float
    days_of_stock: float
    is_slow_mover: bool
    updated_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass 
class SalesDataPoint:
    """Single sales data point for training."""
    sale_id: str
    sale_date: str
    customer_id: str | None
    product_id: str
    product_sku: str
    category_id: str | None
    quantity: int
    unit_price: float
    line_total: float
    hour_of_day: int
    day_of_week: int
    is_weekend: bool
    payment_method: str
    cashier_id: str | None


# ==================== Feature Extraction Tasks ====================

@celery_app.task(
    bind=True,
    base=AsyncTask,
    name="extract_customer_features",
    max_retries=3,
)
def extract_customer_features(
    self: AsyncTask,
    lookback_days: int = 365,
    churn_threshold_days: int = 60,
) -> dict[str, Any]:
    """Extract and store customer features for ML models.
    
    Computes RFM (Recency, Frequency, Monetary) features and additional
    behavioral features for churn prediction.
    
    Args:
        lookback_days: Days of history to analyze
        churn_threshold_days: Days inactive to consider churned
        
    Returns:
        Summary of extraction results
    """
    return self(*[lookback_days, churn_threshold_days])


@extract_customer_features.run_async  # type: ignore
async def extract_customer_features_async(
    lookback_days: int = 365,
    churn_threshold_days: int = 60,
) -> dict[str, Any]:
    """Async implementation of customer feature extraction."""
    logger.info(
        "extract_customer_features_started",
        lookback_days=lookback_days,
        churn_threshold_days=churn_threshold_days,
    )
    
    session: AsyncSession | None = None
    redis_client = _get_redis_client()
    
    try:
        session = async_session_factory()
        now = datetime.now(UTC)
        lookback_start = now - timedelta(days=lookback_days)
        churn_cutoff = now - timedelta(days=churn_threshold_days)
        
        # Query customer purchase summaries
        query = text("""
            SELECT 
                c.id as customer_id,
                c.created_at as registration_date,
                MAX(s.created_at) as last_purchase_date,
                COUNT(DISTINCT s.id) as total_orders,
                COALESCE(SUM(s.total_amount), 0) as lifetime_value,
                COALESCE(AVG(s.total_amount), 0) as avg_order_value,
                COALESCE(AVG(
                    (SELECT COUNT(*) FROM sale_lines sl WHERE sl.sale_id = s.id)
                ), 0) as avg_basket_size
            FROM customers c
            LEFT JOIN sales s ON s.customer_id = c.id 
                AND s.created_at >= :lookback_start
                AND s.status = 'completed'
            WHERE c.is_active = true
            GROUP BY c.id, c.created_at
        """)
        
        result = await session.execute(
            query,
            {"lookback_start": lookback_start}
        )
        rows = result.fetchall()
        
        # Query return rates per customer
        return_query = text("""
            SELECT 
                s.customer_id,
                COUNT(DISTINCT r.id)::float / NULLIF(COUNT(DISTINCT s.id), 0) as return_rate
            FROM sales s
            LEFT JOIN returns r ON r.sale_id = s.id
            WHERE s.customer_id IS NOT NULL
                AND s.created_at >= :lookback_start
            GROUP BY s.customer_id
        """)
        
        return_result = await session.execute(
            return_query,
            {"lookback_start": lookback_start}
        )
        return_rates = {
            row.customer_id: row.return_rate or 0.0 
            for row in return_result.fetchall()
        }
        
        features_stored = 0
        
        for row in rows:
            # Calculate recency
            if row.last_purchase_date:
                recency_days = (now - row.last_purchase_date).days
            else:
                recency_days = lookback_days  # Never purchased
            
            # Calculate days since registration
            days_since_reg = (now - row.registration_date).days if row.registration_date else 0
            
            features = CustomerFeatures(
                customer_id=str(row.customer_id),
                recency_days=recency_days,
                frequency=row.total_orders or 0,
                monetary=float(row.lifetime_value or 0),
                avg_order_value=float(row.avg_order_value or 0),
                avg_basket_size=float(row.avg_basket_size or 0),
                preferred_categories=[],  # TODO: Extract from purchase history
                loyalty_points=0,  # TODO: Join with loyalty table
                loyalty_tier=None,
                days_since_registration=days_since_reg,
                return_rate=return_rates.get(row.customer_id, 0.0),
                churn_probability=None,  # To be filled by ML model
                updated_at=now.isoformat(),
            )
            
            # Store in Redis
            if redis_client:
                key = f"{CUSTOMER_FEATURES_KEY}:{row.customer_id}"
                redis_client.setex(
                    key,
                    FEATURE_TTL_SECONDS,
                    json.dumps(features.to_dict()),
                )
                features_stored += 1
        
        logger.info(
            "extract_customer_features_completed",
            customers_processed=len(rows),
            features_stored=features_stored,
        )
        
        return {
            "customers_processed": len(rows),
            "features_stored": features_stored,
            "lookback_days": lookback_days,
        }
        
    except Exception as e:
        logger.exception("extract_customer_features_failed")
        raise
    finally:
        if session:
            await session.close()


@celery_app.task(
    bind=True,
    base=AsyncTask,
    name="extract_product_features",
    max_retries=3,
)
def extract_product_features(
    self: AsyncTask,
    lookback_days: int = 90,
) -> dict[str, Any]:
    """Extract and store product features for ML models.
    
    Computes velocity, seasonality, and demand metrics.
    
    Args:
        lookback_days: Days of sales history to analyze
        
    Returns:
        Summary of extraction results
    """
    return self(*[lookback_days])


@extract_product_features.run_async  # type: ignore
async def extract_product_features_async(
    lookback_days: int = 90,
) -> dict[str, Any]:
    """Async implementation of product feature extraction."""
    logger.info(
        "extract_product_features_started",
        lookback_days=lookback_days,
    )
    
    session: AsyncSession | None = None
    redis_client = _get_redis_client()
    
    try:
        session = async_session_factory()
        now = datetime.now(UTC)
        lookback_start = now - timedelta(days=lookback_days)
        
        # Query product sales summaries
        query = text("""
            SELECT 
                p.id as product_id,
                p.sku,
                p.category_id,
                COALESCE(SUM(sl.quantity), 0) as total_sold,
                COALESCE(AVG(sl.quantity), 0) as avg_quantity_per_sale,
                COALESCE(STDDEV(sl.quantity), 0) as stddev_quantity,
                COUNT(DISTINCT s.id) as sale_count,
                COUNT(DISTINCT DATE(s.created_at)) as unique_sale_days
            FROM products p
            LEFT JOIN sale_lines sl ON sl.product_id = p.id
            LEFT JOIN sales s ON s.id = sl.sale_id
                AND s.created_at >= :lookback_start
                AND s.status = 'completed'
            WHERE p.is_active = true
            GROUP BY p.id, p.sku, p.category_id
        """)
        
        result = await session.execute(
            query,
            {"lookback_start": lookback_start}
        )
        rows = result.fetchall()
        
        # Get current stock levels
        stock_query = text("""
            SELECT 
                product_id,
                SUM(CASE WHEN direction = 'in' THEN quantity ELSE -quantity END) as quantity_on_hand
            FROM inventory_movements
            GROUP BY product_id
        """)
        stock_result = await session.execute(stock_query)
        stock_levels = {
            row.product_id: row.quantity_on_hand or 0
            for row in stock_result.fetchall()
        }
        
        features_stored = 0
        
        for row in rows:
            total_sold = row.total_sold or 0
            daily_velocity = total_sold / lookback_days if lookback_days > 0 else 0
            
            # Calculate coefficient of variation
            mean = row.avg_quantity_per_sale or 0
            std = row.stddev_quantity or 0
            cv = std / mean if mean > 0 else 0
            
            # ABC classification (simplified)
            if daily_velocity > 5:
                abc_class = "A"
            elif daily_velocity > 1:
                abc_class = "B"
            else:
                abc_class = "C"
            
            # Days of stock
            stock = stock_levels.get(row.product_id, 0)
            days_of_stock = stock / daily_velocity if daily_velocity > 0 else float("inf")
            
            features = ProductFeatures(
                product_id=str(row.product_id),
                sku=row.sku or "",
                category_id=str(row.category_id) if row.category_id else None,
                abc_class=abc_class,
                daily_velocity=round(daily_velocity, 2),
                demand_forecast_7d=round(daily_velocity * 7, 1),
                demand_forecast_30d=round(daily_velocity * 30, 1),
                seasonality_index=1.0,  # TODO: Calculate from weekly patterns
                coefficient_of_variation=round(cv, 3),
                days_of_stock=min(round(days_of_stock, 1), 9999),
                is_slow_mover=daily_velocity < 0.1,
                updated_at=now.isoformat(),
            )
            
            # Store in Redis
            if redis_client:
                key = f"{PRODUCT_FEATURES_KEY}:{row.product_id}"
                redis_client.setex(
                    key,
                    FEATURE_TTL_SECONDS,
                    json.dumps(features.to_dict()),
                )
                features_stored += 1
        
        logger.info(
            "extract_product_features_completed",
            products_processed=len(rows),
            features_stored=features_stored,
        )
        
        return {
            "products_processed": len(rows),
            "features_stored": features_stored,
            "lookback_days": lookback_days,
        }
        
    except Exception as e:
        logger.exception("extract_product_features_failed")
        raise
    finally:
        if session:
            await session.close()


@celery_app.task(
    bind=True,
    base=AsyncTask,
    name="extract_sales_training_data",
    max_retries=3,
)
def extract_sales_training_data(
    self: AsyncTask,
    start_date: str | None = None,
    end_date: str | None = None,
    output_format: str = "json",
) -> dict[str, Any]:
    """Extract sales data for ML model training.
    
    Generates training dataset with features suitable for:
    - Demand forecasting
    - Fraud detection
    - Association rules mining
    
    Args:
        start_date: Start date (ISO format), defaults to 90 days ago
        end_date: End date (ISO format), defaults to today
        output_format: 'json' or 'csv'
        
    Returns:
        Summary with row count and storage location
    """
    return self(*[start_date, end_date, output_format])


@extract_sales_training_data.run_async  # type: ignore
async def extract_sales_training_data_async(
    start_date: str | None = None,
    end_date: str | None = None,
    output_format: str = "json",
) -> dict[str, Any]:
    """Async implementation of sales training data extraction."""
    logger.info(
        "extract_sales_training_data_started",
        start_date=start_date,
        end_date=end_date,
        output_format=output_format,
    )
    
    session: AsyncSession | None = None
    redis_client = _get_redis_client()
    
    try:
        session = async_session_factory()
        now = datetime.now(UTC)
        
        # Parse dates
        if end_date:
            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        else:
            end_dt = now
            
        if start_date:
            start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        else:
            start_dt = end_dt - timedelta(days=90)
        
        # Query sales data
        query = text("""
            SELECT 
                s.id as sale_id,
                s.created_at as sale_date,
                s.customer_id,
                sl.product_id,
                p.sku as product_sku,
                p.category_id,
                sl.quantity,
                sl.unit_price,
                sl.line_total,
                EXTRACT(HOUR FROM s.created_at) as hour_of_day,
                EXTRACT(DOW FROM s.created_at) as day_of_week,
                s.cashier_id
            FROM sales s
            JOIN sale_lines sl ON sl.sale_id = s.id
            JOIN products p ON p.id = sl.product_id
            WHERE s.created_at >= :start_date
              AND s.created_at < :end_date
              AND s.status = 'completed'
            ORDER BY s.created_at
        """)
        
        result = await session.execute(
            query,
            {"start_date": start_dt, "end_date": end_dt}
        )
        rows = result.fetchall()
        
        # Convert to training data format
        training_data = []
        for row in rows:
            day_of_week = int(row.day_of_week or 0)
            
            data_point = SalesDataPoint(
                sale_id=str(row.sale_id),
                sale_date=row.sale_date.isoformat() if row.sale_date else "",
                customer_id=str(row.customer_id) if row.customer_id else None,
                product_id=str(row.product_id),
                product_sku=row.product_sku or "",
                category_id=str(row.category_id) if row.category_id else None,
                quantity=int(row.quantity or 0),
                unit_price=float(row.unit_price or 0),
                line_total=float(row.line_total or 0),
                hour_of_day=int(row.hour_of_day or 0),
                day_of_week=day_of_week,
                is_weekend=day_of_week in (0, 6),  # Sunday=0, Saturday=6
                payment_method="unknown",  # TODO: Join with payments
                cashier_id=str(row.cashier_id) if row.cashier_id else None,
            )
            training_data.append(asdict(data_point))
        
        # Store in Redis (chunked for large datasets)
        rows_stored = 0
        if redis_client and training_data:
            # Store metadata
            metadata = {
                "start_date": start_dt.isoformat(),
                "end_date": end_dt.isoformat(),
                "row_count": len(training_data),
                "extracted_at": now.isoformat(),
            }
            redis_client.setex(
                f"{TRAINING_DATA_KEY}:sales:metadata",
                FEATURE_TTL_SECONDS,
                json.dumps(metadata),
            )
            
            # Store data in chunks
            chunk_size = 1000
            for i in range(0, len(training_data), chunk_size):
                chunk = training_data[i:i + chunk_size]
                chunk_key = f"{TRAINING_DATA_KEY}:sales:chunk:{i // chunk_size}"
                redis_client.setex(
                    chunk_key,
                    FEATURE_TTL_SECONDS,
                    json.dumps(chunk),
                )
                rows_stored += len(chunk)
        
        logger.info(
            "extract_sales_training_data_completed",
            rows_extracted=len(training_data),
            rows_stored=rows_stored,
            start_date=start_dt.isoformat(),
            end_date=end_dt.isoformat(),
        )
        
        return {
            "rows_extracted": len(training_data),
            "rows_stored": rows_stored,
            "start_date": start_dt.isoformat(),
            "end_date": end_dt.isoformat(),
            "storage_key": f"{TRAINING_DATA_KEY}:sales",
        }
        
    except Exception as e:
        logger.exception("extract_sales_training_data_failed")
        raise
    finally:
        if session:
            await session.close()


# ==================== Feature Retrieval ====================

def get_customer_features(customer_id: str) -> CustomerFeatures | None:
    """Retrieve customer features from Redis feature store.
    
    Args:
        customer_id: Customer identifier
        
    Returns:
        CustomerFeatures or None if not found
    """
    redis_client = _get_redis_client()
    if not redis_client:
        return None
    
    try:
        key = f"{CUSTOMER_FEATURES_KEY}:{customer_id}"
        data = redis_client.get(key)
        if data:
            return CustomerFeatures(**json.loads(data))
        return None
    except Exception as e:
        logger.warning("get_customer_features_failed", error=str(e))
        return None


def get_product_features(product_id: str) -> ProductFeatures | None:
    """Retrieve product features from Redis feature store.
    
    Args:
        product_id: Product identifier
        
    Returns:
        ProductFeatures or None if not found
    """
    redis_client = _get_redis_client()
    if not redis_client:
        return None
    
    try:
        key = f"{PRODUCT_FEATURES_KEY}:{product_id}"
        data = redis_client.get(key)
        if data:
            return ProductFeatures(**json.loads(data))
        return None
    except Exception as e:
        logger.warning("get_product_features_failed", error=str(e))
        return None


def get_training_data(data_type: str = "sales") -> list[dict] | None:
    """Retrieve training data from Redis.
    
    Args:
        data_type: Type of training data ('sales')
        
    Returns:
        List of training data dicts or None
    """
    redis_client = _get_redis_client()
    if not redis_client:
        return None
    
    try:
        # Get metadata
        meta_key = f"{TRAINING_DATA_KEY}:{data_type}:metadata"
        metadata = redis_client.get(meta_key)
        if not metadata:
            return None
        
        meta = json.loads(metadata)
        row_count = meta.get("row_count", 0)
        
        # Retrieve chunks
        training_data = []
        chunk_idx = 0
        while len(training_data) < row_count:
            chunk_key = f"{TRAINING_DATA_KEY}:{data_type}:chunk:{chunk_idx}"
            chunk_data = redis_client.get(chunk_key)
            if not chunk_data:
                break
            training_data.extend(json.loads(chunk_data))
            chunk_idx += 1
        
        return training_data
        
    except Exception as e:
        logger.warning("get_training_data_failed", error=str(e))
        return None
