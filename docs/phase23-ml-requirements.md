# Phase 23: AI/ML Requirements & Architecture

## Overview

This document defines the machine learning models, data pipelines, and infrastructure requirements for the Retail POS AI/ML initiative. The goal is to leverage historical transactional data to improve business operations through predictive analytics.

---

## 1. ML Model Specifications

### 1.1 Demand Forecasting Model

**Business Objective**: Predict future product demand to optimize inventory levels and reduce stockouts/overstocking.

**Model Type**: Time Series Forecasting

**Algorithms to Evaluate**:
- Prophet (Facebook) - Good for seasonality, holidays
- SARIMA - Statistical approach with seasonality
- XGBoost with lag features - Handles complex patterns
- LSTM Neural Networks - Deep learning for complex sequences

**Input Features**:
| Feature | Type | Source |
|---------|------|--------|
| product_id | categorical | products table |
| historical_sales (daily) | time series | sales table |
| day_of_week | categorical | derived |
| month | categorical | derived |
| is_holiday | binary | external calendar |
| is_promotion | binary | campaigns table |
| price | numeric | products table |
| category_id | categorical | products table |
| weather (optional) | categorical | external API |

**Output**:
- Daily demand forecast (next 7, 14, 30 days)
- Prediction intervals (80%, 95% confidence)

**Training Data Requirements**:
- Minimum 90 days of historical sales
- Aggregated at daily granularity per product
- At least 1000 transactions for initial training

**Evaluation Metrics**:
- MAPE (Mean Absolute Percentage Error) < 20%
- RMSE (Root Mean Square Error)
- Forecast Bias

**Update Frequency**: Daily retraining with incremental data

---

### 1.2 Customer Churn Prediction

**Business Objective**: Identify customers at risk of churning to enable proactive retention campaigns.

**Model Type**: Binary Classification

**Algorithms to Evaluate**:
- Gradient Boosting (XGBoost, LightGBM)
- Random Forest
- Logistic Regression (baseline)

**Input Features**:
| Feature | Type | Source |
|---------|------|--------|
| customer_id | categorical | customers table |
| days_since_last_purchase | numeric | derived from sales |
| purchase_frequency | numeric | derived (orders/lifetime) |
| avg_order_value | numeric | derived from sales |
| total_lifetime_value | numeric | derived from sales |
| loyalty_points_balance | numeric | loyalty table |
| loyalty_tier | categorical | loyalty table |
| preferred_categories | list | derived from sales |
| return_rate | numeric | derived from returns |
| days_since_registration | numeric | customers table |

**Churn Definition**:
- No purchase in last 60 days (configurable threshold)
- Alternative: RFM-based segmentation

**Output**:
- Churn probability (0-1)
- Risk tier (High/Medium/Low)
- Top contributing factors

**Training Data Requirements**:
- Minimum 6 months of customer transaction history
- Labeled churn events (historical)
- At least 500 customers with complete purchase history

**Evaluation Metrics**:
- AUC-ROC > 0.75
- Precision/Recall at optimal threshold
- F1-Score

**Update Frequency**: Weekly retraining

---

### 1.3 Fraud Detection

**Business Objective**: Detect potentially fraudulent transactions in real-time.

**Model Type**: Anomaly Detection / Binary Classification

**Algorithms to Evaluate**:
- Isolation Forest (unsupervised)
- One-Class SVM
- Autoencoders (deep learning)
- XGBoost (supervised, if labeled data available)

**Input Features**:
| Feature | Type | Source |
|---------|------|--------|
| transaction_amount | numeric | sales table |
| items_count | numeric | sale_lines table |
| hour_of_day | numeric | derived |
| is_weekend | binary | derived |
| payment_method | categorical | payments table |
| cashier_id | categorical | sales table |
| customer_is_new | binary | derived |
| discount_amount | numeric | sales table |
| return_within_hour | binary | derived from returns |
| velocity_last_hour | numeric | derived (transactions/hr) |

**Fraud Indicators to Detect**:
- Unusual high-value cash transactions
- Excessive returns/voids by same cashier
- Rapid successive transactions
- After-hours transactions
- Price overrides without authorization

**Output**:
- Anomaly score (0-1)
- Fraud probability
- Rule-based triggers

**Training Data Requirements**:
- 3+ months of transaction data
- Labeled fraud cases (if available) or unsupervised approach
- Real-time inference capability

**Evaluation Metrics**:
- Precision > 80% (minimize false positives)
- Recall > 60% (catch majority of fraud)
- False positive rate < 5%

**Update Frequency**: Weekly batch retraining, real-time inference

---

### 1.4 Product Recommendations

**Business Objective**: Suggest complementary products to increase basket size.

**Model Type**: Collaborative Filtering / Association Rules

**Algorithms to Evaluate**:
- Market Basket Analysis (Apriori, FP-Growth)
- Matrix Factorization (ALS)
- Item-Item Collaborative Filtering
- Neural Collaborative Filtering

**Input Features**:
| Feature | Type | Source |
|---------|------|--------|
| product_id | categorical | products table |
| customer_id | categorical | sales table |
| basket_contents | list | sale_lines table |
| product_category | categorical | products table |
| product_price_tier | categorical | derived |
| purchase_timestamp | datetime | sales table |

**Association Mining**:
- Minimum support: 0.01 (1% of baskets)
- Minimum confidence: 0.5 (50% co-occurrence)
- Lift threshold: > 1.5

**Output**:
- "Frequently bought together" recommendations
- "Customers also bought" suggestions
- Bundle suggestions with discount impact

**Training Data Requirements**:
- Minimum 10,000 multi-item transactions
- 3+ months of transaction history
- Basket size > 2 items (for association rules)

**Evaluation Metrics**:
- Hit Rate @ K
- Mean Reciprocal Rank (MRR)
- Coverage (% of products recommendable)

**Update Frequency**: Weekly batch retraining

---

## 2. Data Pipeline Architecture

### 2.1 ETL Pipeline

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Production DB  │────▶│  ETL Processor   │────▶│  Feature Store  │
│   (PostgreSQL)  │     │    (Celery)      │     │    (Redis)      │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                               ▼
                     ┌──────────────────┐
                     │  Training Data   │
                     │   (Parquet/S3)   │
                     └──────────────────┘
```

### 2.2 Data Extraction Tasks

**Sales Data Extraction**:
```python
# Extract daily sales for training
SELECT 
    s.id as sale_id,
    s.customer_id,
    s.tenant_id,
    s.created_at,
    s.total_amount,
    s.currency,
    sl.product_id,
    sl.quantity,
    sl.unit_price,
    sl.line_total,
    p.category_id,
    p.sku
FROM sales s
JOIN sale_lines sl ON sl.sale_id = s.id
JOIN products p ON p.id = sl.product_id
WHERE s.created_at >= :start_date
  AND s.created_at < :end_date
  AND s.status = 'completed'
```

**Customer Features Extraction**:
```python
# RFM-style customer features
SELECT 
    c.id as customer_id,
    c.created_at as registration_date,
    MAX(s.created_at) as last_purchase_date,
    COUNT(DISTINCT s.id) as total_orders,
    SUM(s.total_amount) as lifetime_value,
    AVG(s.total_amount) as avg_order_value,
    lm.points as loyalty_points,
    lm.tier as loyalty_tier
FROM customers c
LEFT JOIN sales s ON s.customer_id = c.id
LEFT JOIN loyalty_memberships lm ON lm.customer_id = c.id
GROUP BY c.id, lm.points, lm.tier
```

### 2.3 Feature Store Schema

**Stored in Redis with TTL**:
```
ml:features:customer:{customer_id} -> {
    "recency_days": 5,
    "frequency": 12,
    "monetary": 450.00,
    "avg_basket_size": 3.5,
    "preferred_categories": ["BEVERAGE", "SNACKS"],
    "churn_probability": 0.23,
    "updated_at": "2024-01-15T10:30:00Z"
}

ml:features:product:{product_id} -> {
    "abc_class": "A",
    "demand_forecast_7d": 45,
    "demand_forecast_30d": 180,
    "velocity": 6.5,
    "seasonality_index": 1.2,
    "updated_at": "2024-01-15T02:00:00Z"
}
```

---

## 3. Infrastructure Requirements

### 3.1 Training Infrastructure

| Component | Specification | Purpose |
|-----------|--------------|---------|
| CPU | 8+ cores | Feature engineering, sklearn models |
| RAM | 32GB+ | Large dataset processing |
| GPU (optional) | NVIDIA T4/A10 | Deep learning models |
| Storage | 100GB SSD | Training data, model artifacts |

### 3.2 Serving Infrastructure

| Component | Specification | Purpose |
|-----------|--------------|---------|
| Model Server | FastAPI / TorchServe | Real-time inference |
| Cache | Redis | Feature store, predictions |
| Queue | Celery + Redis | Batch processing |

### 3.3 Monitoring

- **Model Performance**: Track prediction accuracy over time
- **Data Drift**: Monitor feature distributions
- **Latency**: < 100ms p99 for real-time predictions
- **Throughput**: 1000+ predictions/second

---

## 4. Technology Stack

### 4.1 Core Libraries

```toml
[ml-dependencies]
# Data Processing
pandas = "^2.0"
numpy = "^1.24"
polars = "^0.19"  # Fast DataFrame alternative

# Machine Learning
scikit-learn = "^1.3"
xgboost = "^2.0"
lightgbm = "^4.0"

# Time Series
prophet = "^1.1"
statsmodels = "^0.14"

# Deep Learning (optional)
torch = "^2.0"
tensorflow = "^2.14"

# Feature Engineering
feature-engine = "^1.6"
category-encoders = "^2.6"

# Association Rules
mlxtend = "^0.23"

# Experiment Tracking
mlflow = "^2.8"
optuna = "^3.4"  # Hyperparameter tuning
```

### 4.2 Data Storage

- **Training Data**: Parquet files (S3/Azure Blob)
- **Feature Store**: Redis with JSON encoding
- **Model Registry**: MLflow + Azure ML / S3

---

## 5. Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)
- [ ] Set up MLflow experiment tracking
- [ ] Create data extraction Celery tasks
- [ ] Implement feature store (Redis)
- [ ] Build training data pipeline

### Phase 2: Demand Forecasting (Weeks 3-4)
- [ ] Implement Prophet baseline model
- [ ] Add XGBoost ensemble
- [ ] Integrate with inventory intelligence
- [ ] Deploy via Celery scheduled task

### Phase 3: Customer Churn (Weeks 5-6)
- [ ] Build RFM feature pipeline
- [ ] Train XGBoost classifier
- [ ] Create churn risk API endpoint
- [ ] Integrate with loyalty campaigns

### Phase 4: Fraud Detection (Weeks 7-8)
- [ ] Implement Isolation Forest baseline
- [ ] Add rule-based triggers
- [ ] Real-time scoring endpoint
- [ ] Alert integration with WebSocket

### Phase 5: Recommendations (Weeks 9-10)
- [ ] Association rules mining
- [ ] Collaborative filtering model
- [ ] POS integration (suggest at checkout)
- [ ] A/B testing framework

---

## 6. Data Privacy & Compliance

### 6.1 GDPR Considerations
- Customer features must respect erasure requests
- Right to explanation for automated decisions
- Opt-out mechanism for personalized recommendations

### 6.2 Data Retention
- Training data: 2 years rolling window
- Predictions: 90 days
- Model artifacts: Keep last 5 versions

### 6.3 Anonymization
- Use customer_id hash for training (not PII)
- Aggregate sensitive features (income bands, not exact values)
- No storage of raw payment data

---

## 7. Success Metrics

| Model | KPI | Target | Business Impact |
|-------|-----|--------|-----------------|
| Demand Forecast | MAPE | < 20% | Reduce stockouts by 30% |
| Churn Prediction | AUC-ROC | > 0.75 | Increase retention by 15% |
| Fraud Detection | Precision | > 80% | Prevent $X loss/month |
| Recommendations | Basket Size | +10% | Increase revenue by 5% |

---

## 8. Next Steps

1. **Data Audit**: Verify data quality and completeness in production DB
2. **Baseline Models**: Implement simple heuristic baselines for comparison
3. **A/B Testing**: Set up experimentation framework
4. **Monitoring**: Implement data drift and model performance dashboards

---

*Document Version: 1.0*  
*Last Updated: Phase 23 Planning*
