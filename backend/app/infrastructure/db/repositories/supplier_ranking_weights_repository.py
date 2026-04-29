"""Repository for supplier ranking weights."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.inventory.ranking_weights import SupplierRankingWeights
from app.infrastructure.db.models.supplier_ranking_weights_model import (
    SupplierRankingWeightsModel,
)
from app.core.tenant import get_current_tenant_id


class SqlAlchemySupplierRankingWeightsRepository:
    """Repository for supplier ranking weight configuration."""
    
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
    
    def _model_to_entity(self, model: SupplierRankingWeightsModel) -> SupplierRankingWeights:
        """Convert database model to domain entity."""
        return SupplierRankingWeights(
            id=model.id,
            tenant_id=model.tenant_id,
            price_weight=model.price_weight,
            lead_time_weight=model.lead_time_weight,
            quality_weight=model.quality_weight,
            reliability_weight=model.reliability_weight,
            fill_rate_weight=model.fill_rate_weight,
            min_quality_score=model.min_quality_score,
            min_reliability_score=model.min_reliability_score,
            max_lead_time_days=model.max_lead_time_days,
            preferred_supplier_bonus=model.preferred_supplier_bonus,
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )
    
    def _entity_to_model(self, entity: SupplierRankingWeights) -> SupplierRankingWeightsModel:
        """Convert domain entity to database model."""
        return SupplierRankingWeightsModel(
            id=entity.id,
            tenant_id=entity.tenant_id,
            price_weight=entity.price_weight,
            lead_time_weight=entity.lead_time_weight,
            quality_weight=entity.quality_weight,
            reliability_weight=entity.reliability_weight,
            fill_rate_weight=entity.fill_rate_weight,
            min_quality_score=entity.min_quality_score,
            min_reliability_score=entity.min_reliability_score,
            max_lead_time_days=entity.max_lead_time_days,
            preferred_supplier_bonus=entity.preferred_supplier_bonus,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            version=entity.version,
        )
    
    async def get_for_tenant(self, tenant_id: str | None = None) -> SupplierRankingWeights | None:
        """Get ranking weights for a tenant.
        
        Args:
            tenant_id: Optional tenant ID. Uses current tenant context if not provided.
            
        Returns:
            SupplierRankingWeights if found, None otherwise.
        """
        tid = tenant_id or get_current_tenant_id()
        stmt = select(SupplierRankingWeightsModel).where(
            SupplierRankingWeightsModel.tenant_id == tid
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        
        if model is None:
            return None
        
        return self._model_to_entity(model)
    
    async def get_or_create_default(self, tenant_id: str | None = None) -> SupplierRankingWeights:
        """Get ranking weights for a tenant, creating defaults if not found.
        
        Args:
            tenant_id: Optional tenant ID. Uses current tenant context if not provided.
            
        Returns:
            SupplierRankingWeights for the tenant.
        """
        tid = tenant_id or get_current_tenant_id()
        
        weights = await self.get_for_tenant(tid)
        if weights is not None:
            return weights
        
        # Create default weights
        weights = SupplierRankingWeights.default(tid)
        model = self._entity_to_model(weights)
        self._session.add(model)
        await self._session.flush()
        
        return weights
    
    async def save(self, weights: SupplierRankingWeights) -> SupplierRankingWeights:
        """Save ranking weights configuration.
        
        Creates if new, updates if existing.
        
        Args:
            weights: SupplierRankingWeights entity to save.
            
        Returns:
            Saved SupplierRankingWeights entity.
        """
        stmt = select(SupplierRankingWeightsModel).where(
            SupplierRankingWeightsModel.id == weights.id
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing is None:
            model = self._entity_to_model(weights)
            self._session.add(model)
        else:
            existing.price_weight = weights.price_weight
            existing.lead_time_weight = weights.lead_time_weight
            existing.quality_weight = weights.quality_weight
            existing.reliability_weight = weights.reliability_weight
            existing.fill_rate_weight = weights.fill_rate_weight
            existing.min_quality_score = weights.min_quality_score
            existing.min_reliability_score = weights.min_reliability_score
            existing.max_lead_time_days = weights.max_lead_time_days
            existing.preferred_supplier_bonus = weights.preferred_supplier_bonus
            existing.version = weights.version
        
        await self._session.flush()
        return weights
