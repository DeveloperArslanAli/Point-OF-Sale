from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import AUDIT_ROLES, PURCHASING_ROLES, require_roles
from app.api.schemas.purchases import (
    PurchaseCreate,
    PurchaseListOut,
    PurchaseOut,
    PurchasePageMetaOut,
    PurchaseRecordOut,
    ReceivePurchaseCreate,
    ReceivingResultOut,
    ReceivingOut,
    ReceivingLineOut,
)
from app.api.schemas.inventory import InventoryMovementOut
from app.application.purchases.use_cases.get_purchase import GetPurchaseInput, GetPurchaseUseCase
from app.application.purchases.use_cases.list_purchases import (
    ListPurchasesInput,
    ListPurchasesUseCase,
)
from app.application.purchases.use_cases.record_purchase import (
    PurchaseLineInput,
    RecordPurchaseInput,
    RecordPurchaseUseCase,
)
from app.application.purchases.use_cases.receive_purchase_order import (
    ReceivePurchaseOrderInput,
    ReceivePurchaseOrderUseCase,
    ReceivingLineInput,
)
from app.domain.auth.entities import User, UserRole
from app.infrastructure.db.repositories.inventory_movement_repository import (
    SqlAlchemyInventoryMovementRepository,
)
from app.infrastructure.db.repositories.inventory_repository import SqlAlchemyProductRepository
from app.infrastructure.db.repositories.purchase_repository import SqlAlchemyPurchaseRepository
from app.infrastructure.db.repositories.supplier_repository import SqlAlchemySupplierRepository
from app.infrastructure.db.session import get_session
from app.shared.pagination import PageParams

READ_PURCHASING_ROLES: tuple[UserRole, ...] = tuple(dict.fromkeys(PURCHASING_ROLES + AUDIT_ROLES))

router = APIRouter(prefix="/purchases", tags=["purchases"])


@router.post("", response_model=PurchaseRecordOut, status_code=status.HTTP_201_CREATED)
async def record_purchase(
    payload: PurchaseCreate,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*PURCHASING_ROLES)),
) -> PurchaseRecordOut:
    supplier_repo = SqlAlchemySupplierRepository(session)
    product_repo = SqlAlchemyProductRepository(session)
    purchase_repo = SqlAlchemyPurchaseRepository(session)
    inventory_repo = SqlAlchemyInventoryMovementRepository(session)
    use_case = RecordPurchaseUseCase(supplier_repo, product_repo, purchase_repo, inventory_repo)
    result = await use_case.execute(
        RecordPurchaseInput(
            supplier_id=payload.supplier_id,
            currency=payload.currency,
            lines=[
                PurchaseLineInput(
                    product_id=line.product_id,
                    quantity=line.quantity,
                    unit_cost=line.unit_cost,
                )
                for line in payload.lines
            ],
        )
    )
    return PurchaseRecordOut.build(result.purchase, result.movements)


@router.get("", response_model=PurchaseListOut)
async def list_purchases(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    supplier_id: str | None = Query(None, min_length=1, max_length=26),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*READ_PURCHASING_ROLES)),
) -> PurchaseListOut:
    params = PageParams(page=page, limit=limit)
    purchase_repo = SqlAlchemyPurchaseRepository(session)
    use_case = ListPurchasesUseCase(purchase_repo)
    result = await use_case.execute(
        ListPurchasesInput(
            page=params.page,
            limit=params.limit,
            supplier_id=supplier_id,
        )
    )
    items = [PurchaseOut.from_domain(purchase) for purchase in result.purchases]
    meta = PurchasePageMetaOut(
        page=result.page,
        limit=result.limit,
        total=result.total,
        pages=result.pages,
    )
    return PurchaseListOut(items=items, meta=meta)


@router.get("/{purchase_id}", response_model=PurchaseOut)
async def get_purchase(
    purchase_id: str,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*READ_PURCHASING_ROLES)),
) -> PurchaseOut:
    purchase_repo = SqlAlchemyPurchaseRepository(session)
    use_case = GetPurchaseUseCase(purchase_repo)
    purchase = await use_case.execute(GetPurchaseInput(purchase_id=purchase_id))
    return PurchaseOut.from_domain(purchase)


@router.post("/{purchase_id}/receive", response_model=ReceivingResultOut, status_code=status.HTTP_201_CREATED)
async def receive_purchase_order(
    purchase_id: str,
    payload: ReceivePurchaseCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_roles(*PURCHASING_ROLES)),
) -> ReceivingResultOut:
    """
    Receive items for a purchase order.

    Tracks partial deliveries, damaged items, and other receiving exceptions.
    Automatically creates inventory movements for accepted quantities.
    """
    purchase_repo = SqlAlchemyPurchaseRepository(session)
    product_repo = SqlAlchemyProductRepository(session)
    inventory_repo = SqlAlchemyInventoryMovementRepository(session)

    use_case = ReceivePurchaseOrderUseCase(
        purchase_repo=purchase_repo,
        product_repo=product_repo,
        inventory_repo=inventory_repo,
    )

    result = await use_case.execute(
        ReceivePurchaseOrderInput(
            purchase_order_id=purchase_id,
            received_by_user_id=current_user.id,
            lines=[
                ReceivingLineInput(
                    purchase_order_item_id=line.purchase_order_item_id,
                    product_id=line.product_id,
                    quantity_ordered=line.quantity_ordered,
                    quantity_received=line.quantity_received,
                    quantity_damaged=line.quantity_damaged,
                    exception_notes=line.exception_notes,
                )
                for line in payload.lines
            ],
            notes=payload.notes,
        )
    )

    # Convert receiving to output
    receiving_out = ReceivingOut(
        id=result.receiving.id,
        purchase_order_id=result.receiving.purchase_order_id,
        received_by_user_id=result.receiving.received_by_user_id,
        received_at=result.receiving.received_at,
        status=result.receiving.status.value,
        notes=result.receiving.notes,
        items=[
            ReceivingLineOut(
                id=line.id,
                purchase_order_item_id=line.purchase_order_item_id,
                product_id=line.product_id,
                quantity_ordered=line.quantity_ordered,
                quantity_received=line.quantity_received,
                quantity_accepted=line.quantity_accepted,
                quantity_damaged=line.quantity_damaged,
                exception_type=line.exception_type.value if line.exception_type else None,
                exception_notes=line.exception_notes,
                received_at=result.receiving.received_at,
            )
            for line in result.receiving.lines
        ],
        created_at=result.receiving.created_at,
        total_ordered=result.total_ordered,
        total_received=result.total_received,
        total_accepted=result.total_accepted,
        total_damaged=result.total_damaged,
        fill_rate=result.fill_rate,
        has_exceptions=result.has_exceptions,
        exception_summary=result.exception_summary,
    )

    movements_out = [
        InventoryMovementOut(
            id=m.id,
            product_id=m.product_id,
            quantity=m.quantity,
            direction=m.direction,
            reason=m.reason,
            reference=m.reference,
            occurred_at=m.occurred_at,
            created_at=m.created_at,
        )
        for m in result.inventory_movements
    ]

    return ReceivingResultOut(
        receiving=receiving_out,
        movements=movements_out,
    )
