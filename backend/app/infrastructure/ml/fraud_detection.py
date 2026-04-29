"""Fraud Detection Model - Phase 23.

Implements anomaly detection for fraud identification using:
- Isolation Forest for unsupervised anomaly detection
- Rule-based triggers for known patterns
- Real-time scoring capability

Targets: Precision > 80%, False Positive Rate < 5%
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


class FraudSeverity(str, Enum):
    """Fraud severity classification."""
    CRITICAL = "critical"  # Immediate action required
    HIGH = "high"          # Review within 1 hour
    MEDIUM = "medium"      # Review within 24 hours
    LOW = "low"            # Monitor/log only


class FraudIndicator(str, Enum):
    """Types of fraud indicators detected."""
    HIGH_VALUE_CASH = "high_value_cash"
    EXCESSIVE_VOIDS = "excessive_voids"
    RAPID_TRANSACTIONS = "rapid_transactions"
    AFTER_HOURS = "after_hours"
    PRICE_OVERRIDE = "price_override"
    UNUSUAL_DISCOUNT = "unusual_discount"
    RETURN_PATTERN = "return_pattern"
    VELOCITY_ANOMALY = "velocity_anomaly"
    AMOUNT_ANOMALY = "amount_anomaly"
    PATTERN_ANOMALY = "pattern_anomaly"


@dataclass(slots=True)
class FraudScore:
    """Fraud detection result for a single transaction."""
    transaction_id: str
    anomaly_score: float  # 0-1, higher = more anomalous
    is_fraud: bool
    severity: FraudSeverity
    indicators: list[FraudIndicator]
    contributing_factors: dict[str, float]  # factor -> contribution
    rule_triggers: list[str]  # Rule-based triggers hit
    recommended_action: str
    scored_at: datetime
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "anomaly_score": round(self.anomaly_score, 4),
            "is_fraud": self.is_fraud,
            "severity": self.severity.value,
            "indicators": [i.value for i in self.indicators],
            "contributing_factors": {
                k: round(v, 3) for k, v in self.contributing_factors.items()
            },
            "rule_triggers": self.rule_triggers,
            "recommended_action": self.recommended_action,
            "scored_at": self.scored_at.isoformat(),
        }


@dataclass(slots=True)
class FraudModelMetrics:
    """Training/evaluation metrics for fraud model."""
    contamination_rate: float  # Assumed fraud rate in training data
    threshold: float  # Anomaly score threshold
    samples_analyzed: int
    anomalies_detected: int
    trained_at: datetime


@dataclass
class FraudDetectionModel:
    """Fraud detection model using Isolation Forest and rule-based triggers.
    
    Combines unsupervised anomaly detection with domain-specific
    rules for comprehensive fraud identification.
    """
    
    # Model parameters
    contamination: float = 0.01  # Expected fraud rate
    anomaly_threshold: float = 0.5  # Score threshold for fraud flag
    
    # Rule thresholds
    high_value_threshold: float = 500.0  # High-value transaction threshold
    rapid_transaction_window_minutes: int = 5
    rapid_transaction_count: int = 5
    after_hours_start: int = 22  # 10 PM
    after_hours_end: int = 6     # 6 AM
    max_discount_percent: float = 50.0
    max_void_rate: float = 0.2  # 20% void rate is suspicious
    
    # Trained model
    _model: Any = field(default=None, init=False)
    _scaler: Any = field(default=None, init=False)
    _feature_columns: list[str] = field(default_factory=list, init=False)
    _feature_means: dict[str, float] = field(default_factory=dict, init=False)
    _feature_stds: dict[str, float] = field(default_factory=dict, init=False)
    
    def prepare_features(
        self,
        transaction_data: pd.DataFrame,
    ) -> pd.DataFrame:
        """Prepare features for fraud detection.
        
        Args:
            transaction_data: DataFrame with transaction details
            
        Returns:
            Feature matrix for anomaly detection
        """
        df = transaction_data.copy()
        
        # Core transaction features
        if "transaction_amount" not in df.columns and "total_amount" in df.columns:
            df["transaction_amount"] = df["total_amount"]
        
        # Time-based features
        if "transaction_time" in df.columns:
            df["hour_of_day"] = pd.to_datetime(df["transaction_time"]).dt.hour
        elif "hour_of_day" not in df.columns:
            df["hour_of_day"] = 12  # Default to noon
        
        df["is_after_hours"] = (
            (df["hour_of_day"] >= self.after_hours_start) |
            (df["hour_of_day"] < self.after_hours_end)
        ).astype(int)
        
        if "day_of_week" not in df.columns:
            if "transaction_time" in df.columns:
                df["day_of_week"] = pd.to_datetime(df["transaction_time"]).dt.dayofweek
            else:
                df["day_of_week"] = 2  # Default to Wednesday
        
        df["is_weekend"] = (df["day_of_week"].isin([5, 6])).astype(int)
        
        # Amount features
        if "items_count" not in df.columns:
            df["items_count"] = 1
        
        df["amount_per_item"] = df["transaction_amount"] / df["items_count"].replace(0, 1)
        df["is_high_value"] = (df["transaction_amount"] > self.high_value_threshold).astype(int)
        
        # Discount features
        if "discount_amount" not in df.columns:
            df["discount_amount"] = 0
        if "discount_percent" not in df.columns:
            df["discount_percent"] = (
                df["discount_amount"] / df["transaction_amount"].replace(0, 1) * 100
            )
        df["has_large_discount"] = (df["discount_percent"] > self.max_discount_percent).astype(int)
        
        # Payment method features
        if "payment_method" in df.columns:
            df["is_cash"] = (df["payment_method"].str.lower() == "cash").astype(int)
        else:
            df["is_cash"] = 0
        
        df["high_value_cash"] = (df["is_cash"] == 1) & (df["is_high_value"] == 1)
        df["high_value_cash"] = df["high_value_cash"].astype(int)
        
        # Velocity features (if available)
        if "velocity_last_hour" not in df.columns:
            df["velocity_last_hour"] = 1
        
        # Void/return indicators
        if "is_void" not in df.columns:
            df["is_void"] = 0
        if "has_return" not in df.columns:
            df["has_return"] = 0
        
        # Define feature columns
        self._feature_columns = [
            "transaction_amount", "items_count", "hour_of_day",
            "is_after_hours", "is_weekend", "amount_per_item",
            "is_high_value", "discount_percent", "has_large_discount",
            "is_cash", "high_value_cash", "velocity_last_hour",
            "is_void", "has_return",
        ]
        
        # Fill missing with 0
        for col in self._feature_columns:
            if col not in df.columns:
                df[col] = 0
        
        return df
    
    def train(
        self,
        transaction_data: pd.DataFrame,
    ) -> FraudModelMetrics:
        """Train Isolation Forest on historical transactions.
        
        Args:
            transaction_data: Historical transaction data
            
        Returns:
            Training metrics
        """
        try:
            from sklearn.ensemble import IsolationForest
            from sklearn.preprocessing import StandardScaler
        except ImportError:
            logger.error("sklearn_not_installed")
            raise ImportError("Install scikit-learn: pip install scikit-learn")
        
        df = self.prepare_features(transaction_data)
        X = df[self._feature_columns].values
        
        # Store feature statistics for later normalization
        for i, col in enumerate(self._feature_columns):
            self._feature_means[col] = float(np.mean(X[:, i]))
            self._feature_stds[col] = float(np.std(X[:, i])) or 1.0
        
        # Scale features
        self._scaler = StandardScaler()
        X_scaled = self._scaler.fit_transform(X)
        
        logger.info(
            "training_fraud_model",
            samples=len(X),
            contamination=self.contamination,
        )
        
        # Train Isolation Forest
        model = IsolationForest(
            n_estimators=100,
            max_samples="auto",
            contamination=self.contamination,
            max_features=1.0,
            bootstrap=False,
            random_state=42,
            n_jobs=-1,
        )
        
        model.fit(X_scaled)
        self._model = model
        
        # Get predictions on training data
        scores = model.decision_function(X_scaled)
        predictions = model.predict(X_scaled)
        
        # Convert to 0-1 anomaly scores (lower decision_function = more anomalous)
        anomaly_scores = 1 - (scores - scores.min()) / (scores.max() - scores.min() + 1e-10)
        
        anomalies_detected = (predictions == -1).sum()
        
        metrics = FraudModelMetrics(
            contamination_rate=self.contamination,
            threshold=self.anomaly_threshold,
            samples_analyzed=len(X),
            anomalies_detected=int(anomalies_detected),
            trained_at=datetime.utcnow(),
        )
        
        logger.info(
            "fraud_model_trained",
            samples=len(X),
            anomalies=anomalies_detected,
            anomaly_rate=round(anomalies_detected / len(X), 4),
        )
        
        return metrics
    
    def _apply_rules(
        self,
        transaction: pd.Series,
    ) -> tuple[list[FraudIndicator], list[str]]:
        """Apply rule-based fraud detection.
        
        Returns:
            Tuple of (indicators, rule_triggers)
        """
        indicators = []
        triggers = []
        
        # High-value cash transaction
        if (
            transaction.get("is_cash", 0) == 1 and
            transaction.get("transaction_amount", 0) > self.high_value_threshold
        ):
            indicators.append(FraudIndicator.HIGH_VALUE_CASH)
            triggers.append(f"Cash transaction > ${self.high_value_threshold}")
        
        # After-hours transaction
        if transaction.get("is_after_hours", 0) == 1:
            indicators.append(FraudIndicator.AFTER_HOURS)
            triggers.append("Transaction outside business hours")
        
        # Large discount
        if transaction.get("discount_percent", 0) > self.max_discount_percent:
            indicators.append(FraudIndicator.UNUSUAL_DISCOUNT)
            triggers.append(f"Discount > {self.max_discount_percent}%")
        
        # Rapid transactions
        if transaction.get("velocity_last_hour", 0) > self.rapid_transaction_count:
            indicators.append(FraudIndicator.RAPID_TRANSACTIONS)
            triggers.append(f">{self.rapid_transaction_count} transactions in last hour")
        
        # Void transaction
        if transaction.get("is_void", 0) == 1:
            indicators.append(FraudIndicator.EXCESSIVE_VOIDS)
            triggers.append("Transaction voided")
        
        return indicators, triggers
    
    def score(
        self,
        transaction_data: pd.DataFrame,
    ) -> list[FraudScore]:
        """Score transactions for fraud probability.
        
        Args:
            transaction_data: Transactions to score
            
        Returns:
            List of FraudScore objects
        """
        if self._model is None:
            logger.warning("fraud_model_not_trained_using_rules_only")
        
        df = self.prepare_features(transaction_data)
        now = datetime.utcnow()
        
        results = []
        
        for idx, row in df.iterrows():
            # ML-based scoring
            if self._model is not None:
                X = row[self._feature_columns].values.reshape(1, -1)
                X_scaled = self._scaler.transform(X)
                
                decision = self._model.decision_function(X_scaled)[0]
                # Convert to 0-1 score (lower decision = more anomalous)
                # Isolation Forest: anomalies have negative decision function values
                anomaly_score = 1 / (1 + np.exp(decision))  # Sigmoid transformation
            else:
                anomaly_score = 0.0
            
            # Rule-based indicators
            indicators, triggers = self._apply_rules(row)
            
            # Boost anomaly score based on rule triggers
            rule_boost = len(triggers) * 0.15
            combined_score = min(1.0, anomaly_score + rule_boost)
            
            # Add ML-based indicators
            if anomaly_score > 0.7:
                indicators.append(FraudIndicator.PATTERN_ANOMALY)
            if (
                abs(row.get("transaction_amount", 0) - self._feature_means.get("transaction_amount", 0))
                > 3 * self._feature_stds.get("transaction_amount", 1)
            ):
                indicators.append(FraudIndicator.AMOUNT_ANOMALY)
            
            # Determine if fraud
            is_fraud = combined_score >= self.anomaly_threshold or len(triggers) >= 2
            
            # Determine severity
            if combined_score >= 0.8 or len(triggers) >= 3:
                severity = FraudSeverity.CRITICAL
            elif combined_score >= 0.6 or len(triggers) >= 2:
                severity = FraudSeverity.HIGH
            elif combined_score >= 0.4 or len(triggers) >= 1:
                severity = FraudSeverity.MEDIUM
            else:
                severity = FraudSeverity.LOW
            
            # Recommended action
            if severity == FraudSeverity.CRITICAL:
                action = "Immediately halt transaction and alert supervisor"
            elif severity == FraudSeverity.HIGH:
                action = "Flag for manager review within 1 hour"
            elif severity == FraudSeverity.MEDIUM:
                action = "Add to daily fraud review queue"
            else:
                action = "Log for monitoring"
            
            # Contributing factors
            factors = {}
            if self._model is not None and hasattr(self._model, "feature_importances_"):
                for i, col in enumerate(self._feature_columns):
                    factors[col] = abs(row[col] - self._feature_means.get(col, 0)) / (
                        self._feature_stds.get(col, 1) + 1e-10
                    )
            
            results.append(FraudScore(
                transaction_id=str(row.get("transaction_id", idx)),
                anomaly_score=combined_score,
                is_fraud=is_fraud,
                severity=severity,
                indicators=indicators,
                contributing_factors=factors,
                rule_triggers=triggers,
                recommended_action=action,
                scored_at=now,
            ))
        
        return results
    
    def score_single(
        self,
        transaction_id: str,
        transaction_amount: float,
        items_count: int = 1,
        hour_of_day: int = 12,
        payment_method: str = "card",
        discount_percent: float = 0,
        velocity_last_hour: int = 1,
        is_void: bool = False,
    ) -> FraudScore:
        """Score a single transaction in real-time.
        
        Convenience method for real-time fraud detection.
        """
        df = pd.DataFrame([{
            "transaction_id": transaction_id,
            "transaction_amount": transaction_amount,
            "items_count": items_count,
            "hour_of_day": hour_of_day,
            "payment_method": payment_method,
            "discount_percent": discount_percent,
            "velocity_last_hour": velocity_last_hour,
            "is_void": int(is_void),
            "has_return": 0,
        }])
        
        results = self.score(df)
        return results[0] if results else None
    
    def save_model(self, path: Path) -> None:
        """Save trained model to disk."""
        path.mkdir(parents=True, exist_ok=True)
        
        if self._model:
            with open(path / "isolation_forest.pkl", "wb") as f:
                pickle.dump(self._model, f)
        
        if self._scaler:
            with open(path / "scaler.pkl", "wb") as f:
                pickle.dump(self._scaler, f)
        
        with open(path / "feature_columns.json", "w") as f:
            json.dump(self._feature_columns, f)
        
        with open(path / "feature_stats.json", "w") as f:
            json.dump({
                "means": self._feature_means,
                "stds": self._feature_stds,
            }, f)
        
        config = {
            "contamination": self.contamination,
            "anomaly_threshold": self.anomaly_threshold,
            "high_value_threshold": self.high_value_threshold,
            "after_hours_start": self.after_hours_start,
            "after_hours_end": self.after_hours_end,
            "max_discount_percent": self.max_discount_percent,
        }
        with open(path / "config.json", "w") as f:
            json.dump(config, f)
        
        logger.info("fraud_model_saved", path=str(path))
    
    def load_model(self, path: Path) -> None:
        """Load trained model from disk."""
        model_path = path / "isolation_forest.pkl"
        if model_path.exists():
            with open(model_path, "rb") as f:
                self._model = pickle.load(f)
        
        scaler_path = path / "scaler.pkl"
        if scaler_path.exists():
            with open(scaler_path, "rb") as f:
                self._scaler = pickle.load(f)
        
        features_path = path / "feature_columns.json"
        if features_path.exists():
            with open(features_path) as f:
                self._feature_columns = json.load(f)
        
        stats_path = path / "feature_stats.json"
        if stats_path.exists():
            with open(stats_path) as f:
                stats = json.load(f)
                self._feature_means = stats.get("means", {})
                self._feature_stds = stats.get("stds", {})
        
        config_path = path / "config.json"
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
                self.contamination = config.get("contamination", 0.01)
                self.anomaly_threshold = config.get("anomaly_threshold", 0.5)
                self.high_value_threshold = config.get("high_value_threshold", 500.0)
        
        logger.info("fraud_model_loaded", path=str(path))


def create_fraud_model(
    contamination: float = 0.01,
    anomaly_threshold: float = 0.5,
) -> FraudDetectionModel:
    """Factory function to create a fraud detection model."""
    return FraudDetectionModel(
        contamination=contamination,
        anomaly_threshold=anomaly_threshold,
    )
