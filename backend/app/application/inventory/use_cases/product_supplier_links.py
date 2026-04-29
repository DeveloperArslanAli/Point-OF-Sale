"""Use cases for managing product-supplier links.

These use cases handle CRUD operations and business logic for
product-supplier relationships with cost/lead time overrides.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from app.domain.common.errors import NotFoundError, ValidationError, ConflictError
from app.domain.common.identifiers import new_ulid
from app.domain.inventory import ProductSupplierLink
from app.infrastructure.db.repositories.product_supplier_link_repository import (
    SqlAlchemyProductSupplierLinkRepository,
)
from app.infrastructure.db.repositories.inventory_repository import SqlAlchemyProductRepository
from app.infrastructure.db.repositories.supplier_repository import SqlAlchemySupplierRepository


@dataclass(slots=True)
class CreateLinkInput:
    """Input for creating a product-supplier link."""

    product_id: str
    supplier_id: str
    unit_cost: Decimal
    currency: str = "USD"
    minimum_order_quantity: int = 1
    lead_time_days: int = 7
    priority: int = 1
    is_preferred: bool = False
    notes: str | None = None


@dataclass(slots=True)
class UpdateLinkInput:
    """Input for updating a product-supplier link."""

    link_id: str
    unit_cost: Decimal | None = None
    currency: str | None = None
    minimum_order_quantity: int | None = None
    lead_time_days: int | None = None
    priority: int | None = None
    is_preferred: bool | None = None
    is_active: bool | None = None
    notes: str | None = None


class CreateProductSupplierLinkUseCase:
    """Use case for creating a product-supplier link."""

    def __init__(
        self,
        link_repo: SqlAlchemyProductSupplierLinkRepository,
        product_repo: SqlAlchemyProductRepository,
        supplier_repo: SqlAlchemySupplierRepository,
    ) -> None:
        self._link_repo = link_repo
        self._product_repo = product_repo
        self._supplier_repo = supplier_repo

    async def execute(self, data: CreateLinkInput) -> ProductSupplierLink:
        """Create a new product-supplier link."""
        # Validate product exists
        product = await self._product_repo.get_by_id(data.product_id)
        if not product:
            raise NotFoundError(f"Product {data.product_id} not found", code="link.product_not_found")

        # Validate supplier exists
        supplier = await self._supplier_repo.get_by_id(data.supplier_id)
        if not supplier:
            raise NotFoundError(f"Supplier {data.supplier_id} not found", code="link.supplier_not_found")

        # Check for existing link
        existing = await self._link_repo.get_by_product_and_supplier(data.product_id, data.supplier_id)
        if existing:
            raise ConflictError(
                f"Link between product {data.product_id} and supplier {data.supplier_id} already exists",
                code="link.already_exists",
            )

        # If this is preferred, unset other preferred links for this product
        if data.is_preferred:
            await self._link_repo.set_preferred(data.product_id, None)

        # Create the link
        link = ProductSupplierLink(
            id=new_ulid(),
            product_id=data.product_id,
            supplier_id=data.supplier_id,
            unit_cost=data.unit_cost,
            currency=data.currency,
            minimum_order_quantity=data.minimum_order_quantity,
            lead_time_days=data.lead_time_days,
            priority=data.priority,
            is_preferred=data.is_preferred,
            is_active=True,
            notes=data.notes,
        )

        await self._link_repo.add(link)
        return link


class UpdateProductSupplierLinkUseCase:
    """Use case for updating a product-supplier link."""

    def __init__(self, link_repo: SqlAlchemyProductSupplierLinkRepository) -> None:
        self._link_repo = link_repo

    async def execute(self, data: UpdateLinkInput) -> ProductSupplierLink:
        """Update an existing product-supplier link."""
        link = await self._link_repo.get_by_id(data.link_id)
        if not link:
            raise NotFoundError(f"Link {data.link_id} not found", code="link.not_found")

        # Update fields if provided
        if data.unit_cost is not None:
            link.unit_cost = data.unit_cost
        if data.currency is not None:
            link.currency = data.currency
        if data.minimum_order_quantity is not None:
            link.minimum_order_quantity = data.minimum_order_quantity
        if data.lead_time_days is not None:
            link.lead_time_days = data.lead_time_days
        if data.priority is not None:
            link.priority = data.priority
        if data.is_active is not None:
            link.is_active = data.is_active
        if data.notes is not None:
            link.notes = data.notes

        # Handle preferred status change
        if data.is_preferred is not None:
            if data.is_preferred and not link.is_preferred:
                # Setting as preferred - unset others first
                await self._link_repo.set_preferred(link.product_id, None)
            link.is_preferred = data.is_preferred

        await self._link_repo.update(link)
        return link


class DeleteProductSupplierLinkUseCase:
    """Use case for deleting a product-supplier link."""

    def __init__(self, link_repo: SqlAlchemyProductSupplierLinkRepository) -> None:
        self._link_repo = link_repo

    async def execute(self, link_id: str) -> bool:
        """Delete a product-supplier link."""
        deleted = await self._link_repo.delete(link_id)
        if not deleted:
            raise NotFoundError(f"Link {link_id} not found", code="link.not_found")
        return True


class GetProductSupplierLinkUseCase:
    """Use case for getting a single product-supplier link."""

    def __init__(self, link_repo: SqlAlchemyProductSupplierLinkRepository) -> None:
        self._link_repo = link_repo

    async def execute(self, link_id: str) -> ProductSupplierLink:
        """Get a product-supplier link by ID."""
        link = await self._link_repo.get_by_id(link_id)
        if not link:
            raise NotFoundError(f"Link {link_id} not found", code="link.not_found")
        return link


class ListProductSuppliersUseCase:
    """Use case for listing suppliers for a product."""

    def __init__(self, link_repo: SqlAlchemyProductSupplierLinkRepository) -> None:
        self._link_repo = link_repo

    async def execute(
        self, product_id: str, *, active_only: bool = True
    ) -> Sequence[ProductSupplierLink]:
        """List all suppliers linked to a product."""
        return await self._link_repo.list_by_product(product_id, active_only=active_only)


class ListSupplierProductsUseCase:
    """Use case for listing products for a supplier."""

    def __init__(self, link_repo: SqlAlchemyProductSupplierLinkRepository) -> None:
        self._link_repo = link_repo

    async def execute(
        self, supplier_id: str, *, active_only: bool = True
    ) -> Sequence[ProductSupplierLink]:
        """List all products linked to a supplier."""
        return await self._link_repo.list_by_supplier(supplier_id, active_only=active_only)


class GetPreferredSupplierUseCase:
    """Use case for getting the preferred supplier for a product."""

    def __init__(self, link_repo: SqlAlchemyProductSupplierLinkRepository) -> None:
        self._link_repo = link_repo

    async def execute(self, product_id: str) -> ProductSupplierLink | None:
        """Get the preferred supplier link for a product."""
        return await self._link_repo.get_preferred_supplier(product_id)


class SetPreferredSupplierUseCase:
    """Use case for setting the preferred supplier for a product."""

    def __init__(self, link_repo: SqlAlchemyProductSupplierLinkRepository) -> None:
        self._link_repo = link_repo

    async def execute(self, product_id: str, supplier_id: str) -> ProductSupplierLink:
        """Set a supplier as preferred for a product."""
        link = await self._link_repo.get_by_product_and_supplier(product_id, supplier_id)
        if not link:
            raise NotFoundError(
                f"Link between product {product_id} and supplier {supplier_id} not found",
                code="link.not_found",
            )

        # Unset other preferred links and set this one
        await self._link_repo.set_preferred(product_id, link.id)

        # Refresh the link
        link.is_preferred = True
        return link
