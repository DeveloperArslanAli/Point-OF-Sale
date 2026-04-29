from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import SALES_ROLES, require_roles
from app.api.dependencies.cache import get_cache_service
from app.application.common.cache import CacheService
from app.api.schemas.sale import SaleCreate, SaleListOut, SaleOut, SalePageMetaOut, SaleRecordOut
from app.application.sales.use_cases.get_sale import GetSaleInput, GetSaleUseCase
from app.application.sales.use_cases.list_sales import ListSalesInput, ListSalesUseCase
from app.application.sales.use_cases.record_sale import (
    RecordSaleInput,
    RecordSaleUseCase,
    SaleLineInput,
    SalePaymentInput,
)
from app.domain.auth.entities import User, UserRole
from app.core.settings import get_settings
from app.infrastructure.db.repositories.customer_repository import SqlAlchemyCustomerRepository
from app.infrastructure.db.repositories.inventory_movement_repository import (
    SqlAlchemyInventoryMovementRepository,
)
from app.infrastructure.db.repositories.inventory_repository import SqlAlchemyProductRepository
from app.infrastructure.db.repositories.sales_repository import SqlAlchemySalesRepository
from app.infrastructure.db.repositories.returns_repository import SqlAlchemyReturnsRepository
from app.infrastructure.db.repositories.gift_card_repository import SqlAlchemyGiftCardRepository
from app.infrastructure.db.repositories.cash_drawer_repository import SqlAlchemyCashDrawerRepository
from app.infrastructure.db.repositories.shift_repository import SqlAlchemyShiftRepository
from app.infrastructure.db.session import get_session
from app.infrastructure.websocket.handlers.sales_handler import SalesEventHandler

router = APIRouter(prefix="/sales", tags=["sales"])
settings = get_settings()


@router.post("", response_model=SaleRecordOut, status_code=status.HTTP_201_CREATED)
async def record_sale(
    payload: SaleCreate,
    session: AsyncSession = Depends(get_session),
    cache: CacheService = Depends(get_cache_service),
    current_user: User = Depends(require_roles(*SALES_ROLES)),
) -> SaleRecordOut:
    product_repo = SqlAlchemyProductRepository(session)
    sales_repo = SqlAlchemySalesRepository(session)
    inventory_repo = SqlAlchemyInventoryMovementRepository(session)
    customer_repo = SqlAlchemyCustomerRepository(session)
    gift_card_repo = SqlAlchemyGiftCardRepository(session)
    shift_repo = SqlAlchemyShiftRepository(session)
    drawer_repo = SqlAlchemyCashDrawerRepository(session)
    use_case = RecordSaleUseCase(
        product_repo,
        sales_repo,
        inventory_repo,
        customer_repo,
        gift_card_repo,
        shift_repo=shift_repo,
        drawer_repo=drawer_repo,
        enforce_stock=settings.ENFORCE_STOCK_ON_SALE,
    )
    result = await use_case.execute(
        RecordSaleInput(
            currency=payload.currency,
            customer_id=payload.customer_id,
            shift_id=payload.shift_id,
            lines=[
                SaleLineInput(
                    product_id=line.product_id,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                )
                for line in payload.lines
            ],
            payments=[
                SalePaymentInput(
                    payment_method=payment.payment_method,
                    amount=payment.amount,
                    reference_number=payment.reference_number,
                    card_last_four=payment.card_last_four,
                    gift_card_code=payment.gift_card_code,
                )
                for payment in payload.payments
            ],
        )
    )
    await cache.clear_prefix("products:list")
    
    # Publish real-time event
    customer_name = None
    if result.sale.customer_id:
        customer = await customer_repo.get_by_id(str(result.sale.customer_id))
        if customer:
            customer_name = customer.full_name
    
    await SalesEventHandler.publish_sale_created(
        sale=result.sale,
        cashier_id=current_user.id,
        cashier_name=current_user.email,
        customer_name=customer_name,
        tenant_id=getattr(current_user, "tenant_id", "default"),
    )
    
    return SaleRecordOut.build(result.sale, result.movements)


@router.get("/{sale_id}", response_model=SaleOut)
async def get_sale(
    sale_id: str,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*(SALES_ROLES + (UserRole.AUDITOR,)))),
) -> SaleOut:
    sales_repo = SqlAlchemySalesRepository(session)
    returns_repo = SqlAlchemyReturnsRepository(session)
    use_case = GetSaleUseCase(sales_repo)
    sale = await use_case.execute(GetSaleInput(sale_id=sale_id))
    
    item_ids = [item.id for item in sale.iter_items()]
    returned_quantities = await returns_repo.get_returned_quantities(item_ids)
    
    return SaleOut.from_domain(sale, returned_quantities)


@router.get("", response_model=SaleListOut)
async def list_sales(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    customer_id: str | None = Query(None, min_length=1, max_length=26),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*(SALES_ROLES + (UserRole.AUDITOR,)))),
) -> SaleListOut:
    sales_repo = SqlAlchemySalesRepository(session)
    use_case = ListSalesUseCase(sales_repo)
    result = await use_case.execute(
        ListSalesInput(
            page=page,
            limit=limit,
            customer_id=customer_id,
            date_from=date_from,
            date_to=date_to,
        )
    )
    items = [SaleOut.from_domain(sale) for sale in result.sales]
    meta = SalePageMetaOut(page=result.page, limit=result.limit, total=result.total, pages=result.pages)
    return SaleListOut(items=items, meta=meta)
