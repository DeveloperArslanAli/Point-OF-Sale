"""API router for product-supplier links.

Provides endpoints for managing product-supplier relationships
with cost/lead time overrides and preferred supplier ranking.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import INVENTORY_ROLES, PURCHASING_ROLES, require_roles
from app.api.schemas.product_supplier_links import (
    ProductSupplierLinkCreate,
    ProductSupplierLinkUpdate,
    ProductSupplierLinkOut,
    ProductSupplierLinksListOut,
    PreferredSupplierOut,
    BulkLinkCreate,
    BulkLinkResult,
)
from app.application.inventory.use_cases.product_supplier_links import (
    CreateProductSupplierLinkUseCase,
    UpdateProductSupplierLinkUseCase,
    DeleteProductSupplierLinkUseCase,
    GetProductSupplierLinkUseCase,
    ListProductSuppliersUseCase,
    ListSupplierProductsUseCase,
    GetPreferredSupplierUseCase,
    SetPreferredSupplierUseCase,
    CreateLinkInput,
    UpdateLinkInput,
)
from app.domain.auth.entities import User, UserRole
from app.infrastructure.db.repositories.product_supplier_link_repository import (
    SqlAlchemyProductSupplierLinkRepository,
)
from app.infrastructure.db.repositories.inventory_repository import SqlAlchemyProductRepository
from app.infrastructure.db.repositories.supplier_repository import SqlAlchemySupplierRepository
from app.infrastructure.db.session import get_session

# Roles that can manage product-supplier links
LINK_WRITE_ROLES: tuple[UserRole, ...] = tuple(
    dict.fromkeys(INVENTORY_ROLES + PURCHASING_ROLES)
)

router = APIRouter(prefix="/product-supplier-links", tags=["product-supplier-links"])


@router.post("", response_model=ProductSupplierLinkOut, status_code=status.HTTP_201_CREATED)
async def create_link(
    payload: ProductSupplierLinkCreate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*LINK_WRITE_ROLES)),
) -> ProductSupplierLinkOut:
    """Create a new product-supplier link."""
    link_repo = SqlAlchemyProductSupplierLinkRepository(session)
    product_repo = SqlAlchemyProductRepository(session)
    supplier_repo = SqlAlchemySupplierRepository(session)

    use_case = CreateProductSupplierLinkUseCase(link_repo, product_repo, supplier_repo)

    link = await use_case.execute(
        CreateLinkInput(
            product_id=payload.product_id,
            supplier_id=payload.supplier_id,
            unit_cost=payload.unit_cost,
            currency=payload.currency,
            minimum_order_quantity=payload.minimum_order_quantity,
            lead_time_days=payload.lead_time_days,
            priority=payload.priority,
            is_preferred=payload.is_preferred,
            notes=payload.notes,
        )
    )

    return ProductSupplierLinkOut(
        id=link.id,
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
        created_at=link.created_at,
        updated_at=link.updated_at,
    )


@router.get("/{link_id}", response_model=ProductSupplierLinkOut)
async def get_link(
    link_id: str,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*INVENTORY_ROLES)),
) -> ProductSupplierLinkOut:
    """Get a product-supplier link by ID."""
    link_repo = SqlAlchemyProductSupplierLinkRepository(session)
    use_case = GetProductSupplierLinkUseCase(link_repo)

    link = await use_case.execute(link_id)

    return ProductSupplierLinkOut(
        id=link.id,
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
        created_at=link.created_at,
        updated_at=link.updated_at,
    )


@router.patch("/{link_id}", response_model=ProductSupplierLinkOut)
async def update_link(
    link_id: str,
    payload: ProductSupplierLinkUpdate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*LINK_WRITE_ROLES)),
) -> ProductSupplierLinkOut:
    """Update a product-supplier link."""
    link_repo = SqlAlchemyProductSupplierLinkRepository(session)
    use_case = UpdateProductSupplierLinkUseCase(link_repo)

    link = await use_case.execute(
        UpdateLinkInput(
            link_id=link_id,
            unit_cost=payload.unit_cost,
            currency=payload.currency,
            minimum_order_quantity=payload.minimum_order_quantity,
            lead_time_days=payload.lead_time_days,
            priority=payload.priority,
            is_preferred=payload.is_preferred,
            is_active=payload.is_active,
            notes=payload.notes,
        )
    )

    return ProductSupplierLinkOut(
        id=link.id,
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
        created_at=link.created_at,
        updated_at=link.updated_at,
    )


@router.delete("/{link_id}")
async def delete_link(
    link_id: str,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*LINK_WRITE_ROLES)),
) -> Response:
    """Delete a product-supplier link."""
    link_repo = SqlAlchemyProductSupplierLinkRepository(session)
    use_case = DeleteProductSupplierLinkUseCase(link_repo)
    await use_case.execute(link_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/by-product/{product_id}", response_model=ProductSupplierLinksListOut)
async def list_product_suppliers(
    product_id: str,
    active_only: bool = Query(True),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*INVENTORY_ROLES)),
) -> ProductSupplierLinksListOut:
    """List all suppliers linked to a product."""
    link_repo = SqlAlchemyProductSupplierLinkRepository(session)
    use_case = ListProductSuppliersUseCase(link_repo)

    links = await use_case.execute(product_id, active_only=active_only)

    items = [
        ProductSupplierLinkOut(
            id=link.id,
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
            created_at=link.created_at,
            updated_at=link.updated_at,
        )
        for link in links
    ]

    return ProductSupplierLinksListOut(items=items, total=len(items))


@router.get("/by-supplier/{supplier_id}", response_model=ProductSupplierLinksListOut)
async def list_supplier_products(
    supplier_id: str,
    active_only: bool = Query(True),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*INVENTORY_ROLES)),
) -> ProductSupplierLinksListOut:
    """List all products linked to a supplier."""
    link_repo = SqlAlchemyProductSupplierLinkRepository(session)
    use_case = ListSupplierProductsUseCase(link_repo)

    links = await use_case.execute(supplier_id, active_only=active_only)

    items = [
        ProductSupplierLinkOut(
            id=link.id,
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
            created_at=link.created_at,
            updated_at=link.updated_at,
        )
        for link in links
    ]

    return ProductSupplierLinksListOut(items=items, total=len(items))


@router.get("/by-product/{product_id}/preferred", response_model=PreferredSupplierOut)
async def get_preferred_supplier(
    product_id: str,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*INVENTORY_ROLES)),
) -> PreferredSupplierOut:
    """Get the preferred supplier for a product."""
    link_repo = SqlAlchemyProductSupplierLinkRepository(session)
    use_case = GetPreferredSupplierUseCase(link_repo)

    link = await use_case.execute(product_id)

    link_out = None
    if link:
        link_out = ProductSupplierLinkOut(
            id=link.id,
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
            created_at=link.created_at,
            updated_at=link.updated_at,
        )

    return PreferredSupplierOut(
        link=link_out,
        product_id=product_id,
        has_preferred=link is not None,
    )


@router.post(
    "/by-product/{product_id}/preferred/{supplier_id}",
    response_model=ProductSupplierLinkOut,
)
async def set_preferred_supplier(
    product_id: str,
    supplier_id: str,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*LINK_WRITE_ROLES)),
) -> ProductSupplierLinkOut:
    """Set a supplier as the preferred supplier for a product."""
    link_repo = SqlAlchemyProductSupplierLinkRepository(session)
    use_case = SetPreferredSupplierUseCase(link_repo)

    link = await use_case.execute(product_id, supplier_id)

    return ProductSupplierLinkOut(
        id=link.id,
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
        created_at=link.created_at,
        updated_at=link.updated_at,
    )


@router.post("/bulk", response_model=BulkLinkResult, status_code=status.HTTP_201_CREATED)
async def bulk_create_links(
    payload: BulkLinkCreate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*LINK_WRITE_ROLES)),
) -> BulkLinkResult:
    """Bulk create product-supplier links."""
    link_repo = SqlAlchemyProductSupplierLinkRepository(session)
    product_repo = SqlAlchemyProductRepository(session)
    supplier_repo = SqlAlchemySupplierRepository(session)

    use_case = CreateProductSupplierLinkUseCase(link_repo, product_repo, supplier_repo)

    created = 0
    failed = 0
    errors: list[str] = []

    for link_data in payload.links:
        try:
            await use_case.execute(
                CreateLinkInput(
                    product_id=link_data.product_id,
                    supplier_id=link_data.supplier_id,
                    unit_cost=link_data.unit_cost,
                    currency=link_data.currency,
                    minimum_order_quantity=link_data.minimum_order_quantity,
                    lead_time_days=link_data.lead_time_days,
                    priority=link_data.priority,
                    is_preferred=link_data.is_preferred,
                    notes=link_data.notes,
                )
            )
            created += 1
        except Exception as e:
            failed += 1
            errors.append(f"Product {link_data.product_id} / Supplier {link_data.supplier_id}: {str(e)}")

    return BulkLinkResult(created=created, failed=failed, errors=errors)
