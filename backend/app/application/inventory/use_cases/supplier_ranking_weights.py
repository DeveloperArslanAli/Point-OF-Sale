"""Use cases for managing supplier ranking weights."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.common.errors import ValidationError
from app.domain.inventory.ranking_weights import SupplierRankingWeights
from app.infrastructure.db.repositories.supplier_ranking_weights_repository import (
    SqlAlchemySupplierRankingWeightsRepository,
)


@dataclass
class UpdateWeightsInput:
    """Input for updating ranking weights."""
    
    price_weight: Decimal | None = None
    lead_time_weight: Decimal | None = None
    quality_weight: Decimal | None = None
    reliability_weight: Decimal | None = None
    fill_rate_weight: Decimal | None = None
    min_quality_score: Decimal | None = None
    min_reliability_score: Decimal | None = None
    max_lead_time_days: int | None = None
    preferred_supplier_bonus: Decimal | None = None
    auto_normalize: bool = True


class GetSupplierRankingWeightsUseCase:
    """Get supplier ranking weights for the current tenant."""
    
    def __init__(self, repo: SqlAlchemySupplierRankingWeightsRepository) -> None:
        self._repo = repo
    
    async def execute(self) -> SupplierRankingWeights:
        """Get or create default ranking weights for current tenant.
        
        Returns:
            SupplierRankingWeights for the current tenant.
        """
        return await self._repo.get_or_create_default()


class UpdateSupplierRankingWeightsUseCase:
    """Update supplier ranking weights for the current tenant."""
    
    def __init__(self, repo: SqlAlchemySupplierRankingWeightsRepository) -> None:
        self._repo = repo
    
    async def execute(self, input_data: UpdateWeightsInput) -> SupplierRankingWeights:
        """Update ranking weights configuration.
        
        Args:
            input_data: Weight update parameters.
            
        Returns:
            Updated SupplierRankingWeights.
            
        Raises:
            ValidationError: If weight configuration is invalid.
        """
        weights = await self._repo.get_or_create_default()
        
        weights.update(
            price_weight=input_data.price_weight,
            lead_time_weight=input_data.lead_time_weight,
            quality_weight=input_data.quality_weight,
            reliability_weight=input_data.reliability_weight,
            fill_rate_weight=input_data.fill_rate_weight,
            min_quality_score=input_data.min_quality_score,
            min_reliability_score=input_data.min_reliability_score,
            max_lead_time_days=input_data.max_lead_time_days,
            preferred_supplier_bonus=input_data.preferred_supplier_bonus,
            auto_normalize=input_data.auto_normalize,
        )
        
        errors = weights.validate_weights()
        if errors:
            raise ValidationError(
                "; ".join(errors),
                code="supplier.ranking.invalid_weights",
            )
        
        return await self._repo.save(weights)


class ResetSupplierRankingWeightsUseCase:
    """Reset supplier ranking weights to defaults."""
    
    def __init__(self, repo: SqlAlchemySupplierRankingWeightsRepository) -> None:
        self._repo = repo
    
    async def execute(self) -> SupplierRankingWeights:
        """Reset ranking weights to default values.
        
        Returns:
            Reset SupplierRankingWeights with default values.
        """
        weights = await self._repo.get_or_create_default()
        
        # Reset to defaults
        weights.update(
            price_weight=Decimal("0.30"),
            lead_time_weight=Decimal("0.20"),
            quality_weight=Decimal("0.20"),
            reliability_weight=Decimal("0.15"),
            fill_rate_weight=Decimal("0.15"),
            min_quality_score=Decimal("0.0"),
            min_reliability_score=Decimal("0.0"),
            max_lead_time_days=None,
            preferred_supplier_bonus=Decimal("0.10"),
            auto_normalize=False,  # Already using exact defaults
        )
        
        return await self._repo.save(weights)
