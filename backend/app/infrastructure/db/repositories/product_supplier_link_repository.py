"""Repository for managing product-supplier links."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Sequence

from sqlalchemy import Select, select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import get_current_tenant_id
from app.domain.inventory import ProductSupplierLink
from app.infrastructure.db.models.product_supplier_link_model import ProductSupplierLinkModel


class SqlAlchemyProductSupplierLinkRepository:
    """SQLAlchemy implementation of ProductSupplierLinkRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _apply_tenant_filter(self, stmt: Select[Any]) -> Select[Any]:
        """Apply tenant filter if context is set."""
        tenant_id = get_current_tenant_id()
        if tenant_id:
            return stmt.where(ProductSupplierLinkModel.tenant_id == tenant_id)
        return stmt

    async def add(self, link: ProductSupplierLink) -> None:
        """Add a new product-supplier link."""
        model = ProductSupplierLinkModel(
            id=link.id,
            tenant_id=get_current_tenant_id(),
            product_id=link.product_id,
            supplier_id=link.supplier_id,
            unit_cost=link.unit_cost,
            currency=link.currency,
            minimum_order_quantity=link.minimum_order_quantity,
            lead_time_days=link.lead_time_days,
            priority=link.priority,
            is_preferred=link.is_preferred,
            is_active=link.is_active,
            notes=link.notes,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self._session.add(model)
        await self._session.flush()

    async def update(self, link: ProductSupplierLink) -> None:
        """Update an existing product-supplier link."""
        stmt = select(ProductSupplierLinkModel).where(ProductSupplierLinkModel.id == link.id)
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        
        if model:
            model.unit_cost = link.unit_cost
            model.currency = link.currency
            model.minimum_order_quantity = link.minimum_order_quantity
            model.lead_time_days = link.lead_time_days
            model.priority = link.priority
            model.is_preferred = link.is_preferred
            model.is_active = link.is_active
            model.notes = link.notes
            model.updated_at = datetime.now(UTC)
            await self._session.flush()

    async def delete(self, link_id: str) -> bool:
        """Delete a product-supplier link."""
        stmt = select(ProductSupplierLinkModel).where(ProductSupplierLinkModel.id == link_id)
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        
        if model:
            await self._session.delete(model)
            await self._session.flush()
            return True
        return False

    async def get_by_id(self, link_id: str) -> ProductSupplierLink | None:
        """Get a product-supplier link by ID."""
        stmt = select(ProductSupplierLinkModel).where(ProductSupplierLinkModel.id == link_id)
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_product_and_supplier(
        self, product_id: str, supplier_id: str
    ) -> ProductSupplierLink | None:
        """Get a specific product-supplier link."""
        stmt = select(ProductSupplierLinkModel).where(
            and_(
                ProductSupplierLinkModel.product_id == product_id,
                ProductSupplierLinkModel.supplier_id == supplier_id,
            )
        )
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_by_product(
        self,
        product_id: str,
        *,
        active_only: bool = True,
    ) -> Sequence[ProductSupplierLink]:
        """List all suppliers for a product, ordered by priority."""
        stmt = select(ProductSupplierLinkModel).where(
            ProductSupplierLinkModel.product_id == product_id
        )
        stmt = self._apply_tenant_filter(stmt)
        if active_only:
            stmt = stmt.where(ProductSupplierLinkModel.is_active == True)
        stmt = stmt.order_by(
            ProductSupplierLinkModel.is_preferred.desc(),
            ProductSupplierLinkModel.priority.asc(),
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def list_by_supplier(
        self,
        supplier_id: str,
        *,
        active_only: bool = True,
    ) -> Sequence[ProductSupplierLink]:
        """List all products for a supplier."""
        stmt = select(ProductSupplierLinkModel).where(
            ProductSupplierLinkModel.supplier_id == supplier_id
        )
        stmt = self._apply_tenant_filter(stmt)
        if active_only:
            stmt = stmt.where(ProductSupplierLinkModel.is_active == True)
        stmt = stmt.order_by(ProductSupplierLinkModel.created_at.desc())
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def get_preferred_supplier(
        self, product_id: str
    ) -> ProductSupplierLink | None:
        """Get the preferred supplier for a product."""
        stmt = (
            select(ProductSupplierLinkModel)
            .where(
                and_(
                    ProductSupplierLinkModel.product_id == product_id,
                    ProductSupplierLinkModel.is_active == True,
                )
            )
            .order_by(
                ProductSupplierLinkModel.is_preferred.desc(),
                ProductSupplierLinkModel.priority.asc(),
            )
            .limit(1)
        )
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_best_suppliers_for_products(
        self, product_ids: Sequence[str]
    ) -> dict[str, ProductSupplierLink]:
        """Get the best (preferred/lowest priority) supplier for each product."""
        if not product_ids:
            return {}
        
        # Get all active links for the products
        stmt = (
            select(ProductSupplierLinkModel)
            .where(
                and_(
                    ProductSupplierLinkModel.product_id.in_(product_ids),
                    ProductSupplierLinkModel.is_active == True,
                )
            )
            .order_by(
                ProductSupplierLinkModel.is_preferred.desc(),
                ProductSupplierLinkModel.priority.asc(),
            )
        )
        result = await self._session.execute(stmt)
        
        # Group by product_id, take first (best) for each
        best_by_product: dict[str, ProductSupplierLink] = {}
        for model in result.scalars().all():
            if model.product_id not in best_by_product:
                best_by_product[model.product_id] = self._to_entity(model)
        
        return best_by_product

    async def set_preferred(self, product_id: str, link_id: str | None) -> bool:
        """Set a link as preferred for a product (unsets others).
        
        If link_id is None, all links for the product are unset as preferred.
        """
        # First, unset all preferred for this product
        stmt = select(ProductSupplierLinkModel).where(
            ProductSupplierLinkModel.product_id == product_id
        )
        result = await self._session.execute(stmt)
        for model in result.scalars().all():
            model.is_preferred = (link_id is not None and model.id == link_id)
            model.updated_at = datetime.now(UTC)
        
        await self._session.flush()
        return True

    def _to_entity(self, model: ProductSupplierLinkModel) -> ProductSupplierLink:
        """Convert model to domain entity."""
        return ProductSupplierLink(
            id=model.id,
            product_id=model.product_id,
            supplier_id=model.supplier_id,
            unit_cost=Decimal(str(model.unit_cost)),
            currency=model.currency,
            minimum_order_quantity=model.minimum_order_quantity,
            lead_time_days=model.lead_time_days,
            priority=model.priority,
            is_preferred=model.is_preferred,
            is_active=model.is_active,
            notes=model.notes,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
