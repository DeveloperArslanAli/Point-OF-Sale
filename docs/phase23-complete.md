# Phase 23: AI/ML Models - Complete

## Overview

Phase 23 implements machine learning capabilities for the Retail POS system, including:
- Demand Forecasting (Prophet/XGBoost)
- Customer Churn Prediction
- Fraud Detection
- Product Recommendations

## Completed Components

### 1. ML Model Implementations

#### Demand Forecasting (`app/infrastructure/ml/demand_forecast.py`)
- **Prophet Model**: Time series forecasting with seasonality
- **XGBoost Model**: Gradient boosting with lag features
- **Ensemble Mode**: Combines both for optimal accuracy
- Features:
  - Day-of-week seasonality
  - Monthly patterns
  - Confidence intervals (95%)
  - MAPE/RMSE metrics
  - Model persistence (pickle/JSON)

#### Churn Prediction (`app/infrastructure/ml/churn_prediction.py`)
- **Algorithm**: XGBoost Classifier
- **Features**: RFM (Recency, Frequency, Monetary) + behavioral
- Risk tiers: High (≥70%), Medium (40-70%), Low (<40%)
- Outputs:
  - Churn probability
  - Contributing factors
  - Recommended actions
- Metrics: AUC-ROC, Precision, Recall, F1

#### Fraud Detection (`app/infrastructure/ml/fraud_detection.py`)
- **Algorithm**: Isolation Forest (unsupervised)
- **Hybrid Approach**: ML + rule-based triggers
- Fraud indicators:
  - High-value cash transactions
  - After-hours activity
  - Excessive discounts
  - Rapid transaction velocity
- Severity levels: Critical, High, Medium, Low

#### Recommendations (`app/infrastructure/ml/recommendations.py`)
- **Algorithm**: Association Rules Mining + Collaborative Filtering
- Features:
  - "Frequently bought together"
  - Customer-based personalization
  - Bundle suggestions with discount impact
- Metrics: Lift, Confidence, Support

### 2. Celery Tasks

#### Training Tasks (`app/infrastructure/tasks/ml_model_tasks.py`)
```python
# Training
train_demand_forecast_model  # Per-product forecast model
train_churn_model            # Customer churn classifier
train_fraud_model            # Anomaly detection model
train_recommendation_model   # Association rules

# Prediction
predict_demand               # Generate forecasts
predict_churn                # Batch churn prediction
score_transaction_fraud      # Real-time fraud scoring
get_recommendations          # Product recommendations
```

#### Scheduled Training (Celery Beat)
| Task | Schedule | Purpose |
|------|----------|---------|
| train_churn_model | Sunday 3 AM | Weekly churn model refresh |
| train_fraud_model | Sunday 3:30 AM | Weekly fraud model refresh |
| train_recommendation_model | Sunday 4 AM | Weekly association rules |
| predict_churn | Monday 8 AM | Weekly at-risk customer report |

### 3. API Endpoints (`app/api/routers/ml_router.py`)

#### Training Endpoints (Management Roles)
```
POST /api/v1/ml/train/demand-forecast  # Train demand model
POST /api/v1/ml/train/churn            # Train churn model
POST /api/v1/ml/train/fraud            # Train fraud model
POST /api/v1/ml/train/recommendations  # Train recommendation model
```

#### Prediction Endpoints
```
POST /api/v1/ml/predict/demand         # Demand forecast (async)
POST /api/v1/ml/predict/churn          # Churn prediction (async)
POST /api/v1/ml/score/fraud            # Fraud scoring (real-time)
POST /api/v1/ml/recommendations        # Product recommendations (real-time)
```

#### Status Endpoints
```
GET /api/v1/ml/status/{model_name}     # Check model status
GET /api/v1/ml/task/{task_id}          # Check async task status
```

### 4. Dependencies Added

```toml
# Required dependencies (pyproject.toml)
pandas = "^2.2.0"
numpy = "^1.26.0"
scikit-learn = "^1.4.0"
xgboost = "^2.0.0"

# Optional ML group
[tool.poetry.group.ml.dependencies]
prophet = "^1.1.0"
lightgbm = "^4.0.0"
mlxtend = "^0.23.0"
```

## Usage Examples

### Train Models
```python
# Via API
POST /api/v1/ml/train/churn
{
    "lookback_days": 365,
    "churn_threshold_days": 60
}

# Via Celery task
from app.infrastructure.tasks.ml_model_tasks import train_churn_model
task = train_churn_model.delay(lookback_days=365, churn_threshold_days=60)
```

### Real-time Fraud Scoring
```python
POST /api/v1/ml/score/fraud
{
    "transaction_id": "txn_123",
    "transaction_amount": 599.99,
    "items_count": 3,
    "hour_of_day": 23,
    "payment_method": "cash",
    "discount_percent": 0
}

# Response
{
    "score": {
        "transaction_id": "txn_123",
        "anomaly_score": 0.72,
        "is_fraud": true,
        "severity": "high",
        "indicators": ["high_value_cash", "after_hours"],
        "recommended_action": "Flag for manager review within 1 hour"
    }
}
```

### Product Recommendations
```python
POST /api/v1/ml/recommendations
{
    "cart_products": ["prod_123", "prod_456"],
    "customer_id": "cust_789",
    "n_recommendations": 5
}

# Response
{
    "cart_size": 2,
    "recommendations": [
        {
            "product_id": "prod_999",
            "product_name": "Chips Variety Pack",
            "confidence": 0.85,
            "lift": 3.2,
            "reason": "frequently_bought_together"
        }
    ],
    "bundles": [...]
}
```

## Model Storage

Models are stored in the `ml_models/` directory:
```
ml_models/
├── demand_forecast/
│   └── {product_id}/
│       ├── prophet_model.pkl
│       ├── xgboost_model.json
│       └── feature_columns.json
├── churn/
│   └── global/
│       ├── churn_model.json
│       └── feature_importances.json
├── fraud/
│   └── global/
│       ├── isolation_forest.pkl
│       └── scaler.pkl
└── recommendations/
    └── global/
        ├── association_rules.pkl
        └── product_data.json
```

## Integration Points

### POS Integration
1. **Fraud Detection**: Score transactions at checkout
2. **Recommendations**: Show "frequently bought together" on POS screen
3. **Churn Alerts**: Flag high-risk customers during checkout

### Inventory Integration
1. **Demand Forecast**: Feed into purchase order suggestions
2. **ABC Classification**: Uses ML-derived velocity metrics

### Marketing Integration
1. **Churn Prediction**: Trigger retention campaigns
2. **Customer Segments**: Based on RFM scores

## Success Metrics (Targets)

| Model | Metric | Target | Purpose |
|-------|--------|--------|---------|
| Demand Forecast | MAPE | < 20% | Reduce stockouts by 30% |
| Churn Prediction | AUC-ROC | > 0.75 | Increase retention by 15% |
| Fraud Detection | Precision | > 80% | Minimize false positives |
| Recommendations | Basket Size | +10% | Increase revenue by 5% |

## Next Steps

1. **Install ML dependencies**: `poetry install --with ml`
2. **Run initial training**: Use API or Celery tasks
3. **Set up monitoring**: Track model performance over time
4. **A/B testing**: Measure recommendation impact
5. **Data drift detection**: Monitor feature distributions

## Files Created/Modified

### New Files
- `app/infrastructure/ml/__init__.py`
- `app/infrastructure/ml/demand_forecast.py`
- `app/infrastructure/ml/churn_prediction.py`
- `app/infrastructure/ml/fraud_detection.py`
- `app/infrastructure/ml/recommendations.py`
- `app/infrastructure/tasks/ml_model_tasks.py`
- `app/api/routers/ml_router.py`

### Modified Files
- `app/api/main.py` - Added ml_router
- `app/infrastructure/tasks/celery_app.py` - Added ML task schedules
- `app/infrastructure/tasks/scheduled_tasks.py` - Added ML scheduled tasks
- `backend/pyproject.toml` - Added ML dependencies

---
*Phase 23 Complete - AI/ML Models Implemented*
