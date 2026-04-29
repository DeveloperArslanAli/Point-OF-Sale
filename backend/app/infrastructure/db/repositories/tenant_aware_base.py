"""
Tenant-aware base repository for multi-tenant data isolation.

Provides automatic tenant_id filtering for all queries when
tenant context is set via TenantContextMiddleware.

Usage:
    class ProductRepository(TenantAwareBaseRepository[ProductModel, Product]):
        model_class = ProductModel
        
        async def get_all(self) -> list[Product]:
            query = select(self.model_class)
            query = self._apply_tenant_filter(query)
            # ... rest of implementation
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import get_current_tenant_id

ModelT = TypeVar("ModelT")
EntityT = TypeVar("EntityT")


class TenantAwareBaseRepository(Generic[ModelT, EntityT]):
    """
    Base repository with automatic tenant filtering.
    
    Subclasses must set `model_class` to the SQLAlchemy model
    and the model must have a `tenant_id` column.
    """
    
    model_class: type[ModelT]
    
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
    
    def _apply_tenant_filter(self, query: Select[Any]) -> Select[Any]:
        """
        Apply tenant filter to query if tenant context is set.
        
        This method checks if:
        1. A tenant context is currently set
        2. The model has a tenant_id column
        
        If both conditions are true, adds WHERE tenant_id = :tenant_id
        """
        tenant_id = get_current_tenant_id()
        
        if tenant_id and hasattr(self.model_class, "tenant_id"):
            return query.where(self.model_class.tenant_id == tenant_id)  # type: ignore
        
        return query
    
    def _get_tenant_id_for_insert(self) -> str | None:
        """
        Get tenant_id to use for new records.
        
        Returns the current tenant context, or None if not set.
        """
        return get_current_tenant_id()
    
    def _set_tenant_on_model(self, model: ModelT) -> ModelT:
        """
        Set tenant_id on a model if context is available.
        
        Call this before adding new records to ensure
        they're associated with the correct tenant.
        """
        tenant_id = get_current_tenant_id()
        
        if tenant_id and hasattr(model, "tenant_id"):
            setattr(model, "tenant_id", tenant_id)
        
        return model


class TenantFilterMixin:
    """
    Mixin for existing repositories to add tenant filtering.
    
    Usage:
        class MyRepository(TenantFilterMixin):
            def __init__(self, session: AsyncSession):
                self._session = session
                
            async def get_all(self) -> list[Entity]:
                query = select(Model)
                query = self.apply_tenant_filter(query, Model)
                ...
    """
    
    def apply_tenant_filter(self, query: Select[Any], model_class: type) -> Select[Any]:
        """Apply tenant filter if context is set."""
        tenant_id = get_current_tenant_id()
        
        if tenant_id and hasattr(model_class, "tenant_id"):
            return query.where(model_class.tenant_id == tenant_id)  # type: ignore
        
        return query
    
    def get_current_tenant(self) -> str | None:
        """Get current tenant from context."""
        return get_current_tenant_id()
