"""Machine Learning Models Package - Phase 23.

This package provides ML model implementations for:
- Demand Forecasting (Prophet/XGBoost)
- Customer Churn Prediction
- Fraud Detection
- Product Recommendations
"""

from app.infrastructure.ml.demand_forecast import (
    DemandForecastModel,
    ForecastResult,
)
from app.infrastructure.ml.churn_prediction import (
    ChurnPredictionModel,
    ChurnPrediction,
)
from app.infrastructure.ml.fraud_detection import (
    FraudDetectionModel,
    FraudScore,
)
from app.infrastructure.ml.recommendations import (
    RecommendationEngine,
    ProductRecommendation,
)

__all__ = [
    "DemandForecastModel",
    "ForecastResult",
    "ChurnPredictionModel",
    "ChurnPrediction",
    "FraudDetectionModel",
    "FraudScore",
    "RecommendationEngine",
    "ProductRecommendation",
]
