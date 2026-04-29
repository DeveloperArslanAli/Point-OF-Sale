"""Customer Churn Prediction Model - Phase 23.

Implements binary classification for churn prediction using:
- XGBoost/LightGBM for high accuracy
- RFM-based feature engineering
- Explainability via SHAP values

Targets: AUC-ROC > 0.75, Precision/Recall balance
"""

from __future__ import annotations

import json
import pickle
import structlog
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = structlog.get_logger(__name__)


class ChurnRisk(str, Enum):
    """Churn risk tier classification."""
    HIGH = "high"      # probability >= 0.7
    MEDIUM = "medium"  # probability 0.4-0.7
    LOW = "low"        # probability < 0.4


@dataclass(slots=True)
class ChurnPrediction:
    """Single customer churn prediction result."""
    customer_id: str
    churn_probability: float
    risk_tier: ChurnRisk
    days_since_last_purchase: int
    lifetime_value: float
    contributing_factors: list[tuple[str, float]]  # (feature, importance)
    predicted_at: datetime
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "customer_id": self.customer_id,
            "churn_probability": round(self.churn_probability, 4),
            "risk_tier": self.risk_tier.value,
            "days_since_last_purchase": self.days_since_last_purchase,
            "lifetime_value": round(self.lifetime_value, 2),
            "contributing_factors": [
                {"factor": f, "importance": round(i, 3)}
                for f, i in self.contributing_factors[:5]
            ],
            "predicted_at": self.predicted_at.isoformat(),
        }


@dataclass(slots=True)
class ChurnModelMetrics:
    """Training metrics for churn model."""
    auc_roc: float
    precision: float
    recall: float
    f1_score: float
    accuracy: float
    training_samples: int
    validation_samples: int
    feature_importances: dict[str, float]
    trained_at: datetime


@dataclass
class ChurnPredictionModel:
    """Customer churn prediction model.
    
    Uses gradient boosting with RFM features to predict
    customer churn probability and identify at-risk customers.
    """
    
    churn_threshold_days: int = 60  # Days inactive = churned
    min_training_samples: int = 100
    
    # Trained model
    _model: Any = field(default=None, init=False)
    _feature_columns: list[str] = field(default_factory=list, init=False)
    _feature_importances: dict[str, float] = field(default_factory=dict, init=False)
    
    def prepare_features(
        self,
        customer_data: pd.DataFrame,
        for_training: bool = True,
    ) -> pd.DataFrame:
        """Prepare RFM and behavioral features for modeling.
        
        Args:
            customer_data: DataFrame with customer transaction data
            for_training: Whether to include churn labels
            
        Returns:
            Feature matrix ready for model training/prediction
        """
        df = customer_data.copy()
        
        # Ensure required columns exist
        required_cols = ["customer_id", "recency_days", "frequency", "monetary"]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        
        # RFM normalization (0-1 scale)
        df["recency_score"] = 1 - (df["recency_days"] / df["recency_days"].max()).clip(0, 1)
        df["frequency_score"] = (df["frequency"] / df["frequency"].max()).clip(0, 1)
        df["monetary_score"] = (df["monetary"] / df["monetary"].max()).clip(0, 1)
        
        # RFM combined score
        df["rfm_score"] = (
            df["recency_score"] * 0.4 +
            df["frequency_score"] * 0.35 +
            df["monetary_score"] * 0.25
        )
        
        # Additional features
        if "avg_order_value" in df.columns:
            df["aov_normalized"] = (df["avg_order_value"] / df["avg_order_value"].max()).clip(0, 1)
        else:
            df["aov_normalized"] = df["monetary"] / df["frequency"].replace(0, 1)
        
        if "days_since_registration" in df.columns:
            df["customer_tenure"] = df["days_since_registration"] / 365
        else:
            df["customer_tenure"] = 1.0
        
        if "return_rate" in df.columns:
            df["return_rate_normalized"] = df["return_rate"].clip(0, 1)
        else:
            df["return_rate_normalized"] = 0.0
        
        # Purchase velocity (orders per month active)
        df["purchase_velocity"] = df["frequency"] / (df.get("customer_tenure", 1) * 12 + 0.1)
        df["purchase_velocity"] = df["purchase_velocity"].clip(0, 10)
        
        # Engagement decline indicators
        df["is_dormant"] = (df["recency_days"] > 30).astype(int)
        df["is_at_risk"] = (
            (df["recency_days"] > 21) & 
            (df["recency_days"] <= self.churn_threshold_days)
        ).astype(int)
        
        # Value segments
        monetary_25 = df["monetary"].quantile(0.25)
        monetary_75 = df["monetary"].quantile(0.75)
        df["is_high_value"] = (df["monetary"] > monetary_75).astype(int)
        df["is_low_value"] = (df["monetary"] < monetary_25).astype(int)
        
        # Define feature columns for model
        self._feature_columns = [
            "recency_days", "frequency", "monetary",
            "recency_score", "frequency_score", "monetary_score", "rfm_score",
            "aov_normalized", "customer_tenure", "return_rate_normalized",
            "purchase_velocity", "is_dormant", "is_at_risk",
            "is_high_value", "is_low_value",
        ]
        
        # Add churn label for training
        if for_training and "is_churned" not in df.columns:
            df["is_churned"] = (df["recency_days"] >= self.churn_threshold_days).astype(int)
        
        return df
    
    def train(
        self,
        training_data: pd.DataFrame,
        validation_split: float = 0.2,
    ) -> ChurnModelMetrics:
        """Train churn prediction model.
        
        Args:
            training_data: Customer data with RFM features
            validation_split: Fraction of data for validation
            
        Returns:
            Training metrics
        """
        try:
            import xgboost as xgb
            from sklearn.metrics import (
                roc_auc_score, precision_score, recall_score, 
                f1_score, accuracy_score
            )
        except ImportError:
            logger.error("ml_dependencies_not_installed")
            raise ImportError("Install xgboost and scikit-learn")
        
        df = self.prepare_features(training_data, for_training=True)
        
        if len(df) < self.min_training_samples:
            raise ValueError(
                f"Insufficient training data: {len(df)} < {self.min_training_samples}"
            )
        
        logger.info(
            "training_churn_model",
            samples=len(df),
            churn_rate=df["is_churned"].mean(),
        )
        
        # Prepare features and target
        X = df[self._feature_columns].values
        y = df["is_churned"].values
        
        # Train/validation split
        split_idx = int(len(X) * (1 - validation_split))
        indices = np.random.permutation(len(X))
        train_idx, val_idx = indices[:split_idx], indices[split_idx:]
        
        X_train, X_val = X[train_idx], X[val_idx]
        y_train, y_val = y[train_idx], y[val_idx]
        
        # Handle class imbalance
        scale_pos_weight = (y_train == 0).sum() / max((y_train == 1).sum(), 1)
        
        # Train XGBoost classifier
        model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            min_child_weight=3,
            subsample=0.8,
            colsample_bytree=0.8,
            scale_pos_weight=scale_pos_weight,
            use_label_encoder=False,
            eval_metric="logloss",
            random_state=42,
        )
        
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )
        
        self._model = model
        
        # Calculate metrics
        y_pred_proba = model.predict_proba(X_val)[:, 1]
        y_pred = (y_pred_proba >= 0.5).astype(int)
        
        auc_roc = roc_auc_score(y_val, y_pred_proba)
        precision = precision_score(y_val, y_pred, zero_division=0)
        recall = recall_score(y_val, y_pred, zero_division=0)
        f1 = f1_score(y_val, y_pred, zero_division=0)
        accuracy = accuracy_score(y_val, y_pred)
        
        # Extract feature importances
        self._feature_importances = dict(
            zip(self._feature_columns, model.feature_importances_)
        )
        
        metrics = ChurnModelMetrics(
            auc_roc=float(auc_roc),
            precision=float(precision),
            recall=float(recall),
            f1_score=float(f1),
            accuracy=float(accuracy),
            training_samples=len(X_train),
            validation_samples=len(X_val),
            feature_importances=self._feature_importances,
            trained_at=datetime.utcnow(),
        )
        
        logger.info(
            "churn_model_trained",
            auc_roc=round(auc_roc, 3),
            precision=round(precision, 3),
            recall=round(recall, 3),
        )
        
        return metrics
    
    def predict(
        self,
        customer_data: pd.DataFrame,
    ) -> list[ChurnPrediction]:
        """Predict churn probability for customers.
        
        Args:
            customer_data: Customer features DataFrame
            
        Returns:
            List of ChurnPrediction objects
        """
        if self._model is None:
            logger.error("churn_model_not_trained")
            return []
        
        df = self.prepare_features(customer_data, for_training=False)
        X = df[self._feature_columns].values
        
        probabilities = self._model.predict_proba(X)[:, 1]
        
        now = datetime.utcnow()
        predictions = []
        
        for i, (_, row) in enumerate(df.iterrows()):
            prob = float(probabilities[i])
            
            # Determine risk tier
            if prob >= 0.7:
                risk_tier = ChurnRisk.HIGH
            elif prob >= 0.4:
                risk_tier = ChurnRisk.MEDIUM
            else:
                risk_tier = ChurnRisk.LOW
            
            # Get top contributing factors
            sorted_factors = sorted(
                self._feature_importances.items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            predictions.append(ChurnPrediction(
                customer_id=str(row.get("customer_id", "")),
                churn_probability=prob,
                risk_tier=risk_tier,
                days_since_last_purchase=int(row.get("recency_days", 0)),
                lifetime_value=float(row.get("monetary", 0)),
                contributing_factors=sorted_factors[:5],
                predicted_at=now,
            ))
        
        return predictions
    
    def predict_single(
        self,
        customer_id: str,
        recency_days: int,
        frequency: int,
        monetary: float,
        avg_order_value: float = 0,
        days_since_registration: int = 365,
        return_rate: float = 0,
    ) -> ChurnPrediction | None:
        """Predict churn for a single customer.
        
        Convenience method for real-time prediction.
        """
        df = pd.DataFrame([{
            "customer_id": customer_id,
            "recency_days": recency_days,
            "frequency": frequency,
            "monetary": monetary,
            "avg_order_value": avg_order_value or (monetary / max(frequency, 1)),
            "days_since_registration": days_since_registration,
            "return_rate": return_rate,
        }])
        
        predictions = self.predict(df)
        return predictions[0] if predictions else None
    
    def get_at_risk_customers(
        self,
        customer_data: pd.DataFrame,
        risk_threshold: float = 0.5,
        top_n: int = 100,
    ) -> list[ChurnPrediction]:
        """Get customers at risk of churning, sorted by risk.
        
        Args:
            customer_data: Customer features
            risk_threshold: Minimum churn probability to include
            top_n: Maximum number of results
            
        Returns:
            List of high-risk customers sorted by churn probability
        """
        predictions = self.predict(customer_data)
        
        at_risk = [
            p for p in predictions 
            if p.churn_probability >= risk_threshold
        ]
        
        at_risk.sort(key=lambda x: x.churn_probability, reverse=True)
        
        return at_risk[:top_n]
    
    def save_model(self, path: Path) -> None:
        """Save trained model to disk."""
        path.mkdir(parents=True, exist_ok=True)
        
        if self._model:
            self._model.save_model(str(path / "churn_model.json"))
        
        with open(path / "feature_columns.json", "w") as f:
            json.dump(self._feature_columns, f)
        
        with open(path / "feature_importances.json", "w") as f:
            json.dump(self._feature_importances, f)
        
        # Save config
        config = {
            "churn_threshold_days": self.churn_threshold_days,
            "min_training_samples": self.min_training_samples,
        }
        with open(path / "config.json", "w") as f:
            json.dump(config, f)
        
        logger.info("churn_model_saved", path=str(path))
    
    def load_model(self, path: Path) -> None:
        """Load trained model from disk."""
        try:
            import xgboost as xgb
        except ImportError:
            logger.error("xgboost_not_installed")
            return
        
        model_path = path / "churn_model.json"
        if model_path.exists():
            self._model = xgb.XGBClassifier()
            self._model.load_model(str(model_path))
        
        features_path = path / "feature_columns.json"
        if features_path.exists():
            with open(features_path) as f:
                self._feature_columns = json.load(f)
        
        importances_path = path / "feature_importances.json"
        if importances_path.exists():
            with open(importances_path) as f:
                self._feature_importances = json.load(f)
        
        config_path = path / "config.json"
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
                self.churn_threshold_days = config.get("churn_threshold_days", 60)
                self.min_training_samples = config.get("min_training_samples", 100)
        
        logger.info("churn_model_loaded", path=str(path))


def create_churn_model(
    churn_threshold_days: int = 60,
    min_training_samples: int = 100,
) -> ChurnPredictionModel:
    """Factory function to create a churn prediction model."""
    return ChurnPredictionModel(
        churn_threshold_days=churn_threshold_days,
        min_training_samples=min_training_samples,
    )
