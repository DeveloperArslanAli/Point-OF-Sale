"""API router for supplier ranking weights configuration.

Provides endpoints for managing tenant-specific supplier selection weights.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import MANAGEMENT_ROLES, require_roles
from app.api.schemas.supplier_ranking_weights import (
    SupplierRankingWeightsOut,
    SupplierRankingWeightsUpdate,
)
from app.application.inventory.use_cases.supplier_ranking_weights import (
    GetSupplierRankingWeightsUseCase,
    UpdateSupplierRankingWeightsUseCase,
    ResetSupplierRankingWeightsUseCase,
    UpdateWeightsInput,
)
from app.domain.auth.entities import User
from app.infrastructure.db.repositories.supplier_ranking_weights_repository import (
    SqlAlchemySupplierRankingWeightsRepository,
)
from app.infrastructure.db.session import get_session


router = APIRouter(
    prefix="/supplier-ranking-weights",
    tags=["supplier-ranking-weights"],
)


@router.get("", response_model=SupplierRankingWeightsOut)
async def get_ranking_weights(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> SupplierRankingWeightsOut:
    """Get supplier ranking weights configuration for the current tenant.
    
    Returns default weights if no custom configuration exists.
    """
    repo = SqlAlchemySupplierRankingWeightsRepository(session)
    use_case = GetSupplierRankingWeightsUseCase(repo)
    
    weights = await use_case.execute()
    
    return SupplierRankingWeightsOut(
        id=weights.id,
        tenant_id=weights.tenant_id,
        price_weight=weights.price_weight,
        lead_time_weight=weights.lead_time_weight,
        quality_weight=weights.quality_weight,
        reliability_weight=weights.reliability_weight,
        fill_rate_weight=weights.fill_rate_weight,
        min_quality_score=weights.min_quality_score,
        min_reliability_score=weights.min_reliability_score,
        max_lead_time_days=weights.max_lead_time_days,
        preferred_supplier_bonus=weights.preferred_supplier_bonus,
        created_at=weights.created_at,
        updated_at=weights.updated_at,
        version=weights.version,
    )


@router.put("", response_model=SupplierRankingWeightsOut)
async def update_ranking_weights(
    payload: SupplierRankingWeightsUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> SupplierRankingWeightsOut:
    """Update supplier ranking weights configuration.
    
    Weights are used when auto-selecting suppliers for purchase orders.
    By default, weights are normalized to sum to 1.0.
    
    Weight factors:
    - **price_weight**: Lower unit cost results in higher score
    - **lead_time_weight**: Faster delivery results in higher score
    - **quality_weight**: Higher quality score (fewer receiving exceptions)
    - **reliability_weight**: Higher on-time delivery rate
    - **fill_rate_weight**: Higher order fill rate
    
    Threshold settings:
    - **min_quality_score**: Suppliers below this score are excluded
    - **min_reliability_score**: Suppliers below this are excluded
    - **max_lead_time_days**: Suppliers exceeding this lead time are excluded
    """
    repo = SqlAlchemySupplierRankingWeightsRepository(session)
    use_case = UpdateSupplierRankingWeightsUseCase(repo)
    
    weights = await use_case.execute(
        UpdateWeightsInput(
            price_weight=payload.price_weight,
            lead_time_weight=payload.lead_time_weight,
            quality_weight=payload.quality_weight,
            reliability_weight=payload.reliability_weight,
            fill_rate_weight=payload.fill_rate_weight,
            min_quality_score=payload.min_quality_score,
            min_reliability_score=payload.min_reliability_score,
            max_lead_time_days=payload.max_lead_time_days,
            preferred_supplier_bonus=payload.preferred_supplier_bonus,
            auto_normalize=payload.auto_normalize,
        )
    )
    
    return SupplierRankingWeightsOut(
        id=weights.id,
        tenant_id=weights.tenant_id,
        price_weight=weights.price_weight,
        lead_time_weight=weights.lead_time_weight,
        quality_weight=weights.quality_weight,
        reliability_weight=weights.reliability_weight,
        fill_rate_weight=weights.fill_rate_weight,
        min_quality_score=weights.min_quality_score,
        min_reliability_score=weights.min_reliability_score,
        max_lead_time_days=weights.max_lead_time_days,
        preferred_supplier_bonus=weights.preferred_supplier_bonus,
        created_at=weights.created_at,
        updated_at=weights.updated_at,
        version=weights.version,
    )


@router.post("/reset", response_model=SupplierRankingWeightsOut)
async def reset_ranking_weights(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*MANAGEMENT_ROLES)),
) -> SupplierRankingWeightsOut:
    """Reset supplier ranking weights to default values.
    
    Resets all weights to their original defaults:
    - price_weight: 0.30
    - lead_time_weight: 0.20
    - quality_weight: 0.20
    - reliability_weight: 0.15
    - fill_rate_weight: 0.15
    - preferred_supplier_bonus: 0.10
    - All thresholds: disabled
    """
    repo = SqlAlchemySupplierRankingWeightsRepository(session)
    use_case = ResetSupplierRankingWeightsUseCase(repo)
    
    weights = await use_case.execute()
    
    return SupplierRankingWeightsOut(
        id=weights.id,
        tenant_id=weights.tenant_id,
        price_weight=weights.price_weight,
        lead_time_weight=weights.lead_time_weight,
        quality_weight=weights.quality_weight,
        reliability_weight=weights.reliability_weight,
        fill_rate_weight=weights.fill_rate_weight,
        min_quality_score=weights.min_quality_score,
        min_reliability_score=weights.min_reliability_score,
        max_lead_time_days=weights.max_lead_time_days,
        preferred_supplier_bonus=weights.preferred_supplier_bonus,
        created_at=weights.created_at,
        updated_at=weights.updated_at,
        version=weights.version,
    )
