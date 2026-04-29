"""Supplier ranking weights domain entity.

Configurable weights for ranking suppliers when auto-selecting for purchase orders.
Each tenant can customize these weights to prioritize different factors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC
from decimal import Decimal

from app.domain.common.identifiers import new_ulid


@dataclass
class SupplierRankingWeights:
    """Configuration for supplier selection ranking weights.
    
    Weights are normalized (should sum to 1.0) and applied to supplier metrics:
    - price_weight: Lower unit cost is better
    - lead_time_weight: Faster delivery is better
    - quality_weight: Higher quality score is better (based on receiving exceptions)
    - reliability_weight: Higher on-time delivery rate is better
    - fill_rate_weight: Higher order fill rate is better
    """
    
    id: str = field(default_factory=new_ulid)
    tenant_id: str = ""
    
    # Ranking weights (should sum to 1.0)
    price_weight: Decimal = Decimal("0.30")
    lead_time_weight: Decimal = Decimal("0.20")
    quality_weight: Decimal = Decimal("0.20")
    reliability_weight: Decimal = Decimal("0.15")
    fill_rate_weight: Decimal = Decimal("0.15")
    
    # Minimum thresholds for supplier eligibility
    min_quality_score: Decimal = Decimal("0.0")  # 0-100
    min_reliability_score: Decimal = Decimal("0.0")  # 0-100
    max_lead_time_days: int | None = None
    
    # Preferred supplier bonus (added to ranking score if supplier is preferred)
    preferred_supplier_bonus: Decimal = Decimal("0.10")
    
    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    version: int = 0
    
    @classmethod
    def default(cls, tenant_id: str) -> "SupplierRankingWeights":
        """Create default ranking weights for a tenant."""
        return cls(tenant_id=tenant_id)
    
    def normalize_weights(self) -> None:
        """Normalize weights to sum to 1.0."""
        total = (
            self.price_weight
            + self.lead_time_weight
            + self.quality_weight
            + self.reliability_weight
            + self.fill_rate_weight
        )
        if total > 0:
            self.price_weight = self.price_weight / total
            self.lead_time_weight = self.lead_time_weight / total
            self.quality_weight = self.quality_weight / total
            self.reliability_weight = self.reliability_weight / total
            self.fill_rate_weight = self.fill_rate_weight / total
        self.updated_at = datetime.now(UTC)
        self.version += 1
    
    def validate_weights(self) -> list[str]:
        """Validate weight configuration and return list of errors."""
        errors: list[str] = []
        
        weights = [
            ("price_weight", self.price_weight),
            ("lead_time_weight", self.lead_time_weight),
            ("quality_weight", self.quality_weight),
            ("reliability_weight", self.reliability_weight),
            ("fill_rate_weight", self.fill_rate_weight),
        ]
        
        for name, value in weights:
            if value < 0:
                errors.append(f"{name} cannot be negative")
            if value > 1:
                errors.append(f"{name} cannot exceed 1.0")
        
        if self.min_quality_score < 0 or self.min_quality_score > 100:
            errors.append("min_quality_score must be between 0 and 100")
        
        if self.min_reliability_score < 0 or self.min_reliability_score > 100:
            errors.append("min_reliability_score must be between 0 and 100")
        
        if self.max_lead_time_days is not None and self.max_lead_time_days < 0:
            errors.append("max_lead_time_days cannot be negative")
        
        if self.preferred_supplier_bonus < 0:
            errors.append("preferred_supplier_bonus cannot be negative")
        
        return errors
    
    def update(
        self,
        *,
        price_weight: Decimal | None = None,
        lead_time_weight: Decimal | None = None,
        quality_weight: Decimal | None = None,
        reliability_weight: Decimal | None = None,
        fill_rate_weight: Decimal | None = None,
        min_quality_score: Decimal | None = None,
        min_reliability_score: Decimal | None = None,
        max_lead_time_days: int | None = None,
        preferred_supplier_bonus: Decimal | None = None,
        auto_normalize: bool = True,
    ) -> None:
        """Update ranking weight configuration.
        
        Args:
            price_weight: Weight for price factor
            lead_time_weight: Weight for lead time factor
            quality_weight: Weight for quality score factor
            reliability_weight: Weight for reliability factor
            fill_rate_weight: Weight for fill rate factor
            min_quality_score: Minimum quality score threshold (0-100)
            min_reliability_score: Minimum reliability score threshold (0-100)
            max_lead_time_days: Maximum acceptable lead time in days
            preferred_supplier_bonus: Bonus score for preferred suppliers
            auto_normalize: Whether to auto-normalize weights to sum to 1.0
        """
        if price_weight is not None:
            self.price_weight = price_weight
        if lead_time_weight is not None:
            self.lead_time_weight = lead_time_weight
        if quality_weight is not None:
            self.quality_weight = quality_weight
        if reliability_weight is not None:
            self.reliability_weight = reliability_weight
        if fill_rate_weight is not None:
            self.fill_rate_weight = fill_rate_weight
        if min_quality_score is not None:
            self.min_quality_score = min_quality_score
        if min_reliability_score is not None:
            self.min_reliability_score = min_reliability_score
        if max_lead_time_days is not None:
            self.max_lead_time_days = max_lead_time_days
        if preferred_supplier_bonus is not None:
            self.preferred_supplier_bonus = preferred_supplier_bonus
        
        if auto_normalize:
            self.normalize_weights()
        else:
            self.updated_at = datetime.now(UTC)
            self.version += 1
