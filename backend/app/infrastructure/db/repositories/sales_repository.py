from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.application.sales.ports import CustomerSalesSummary, SalesRepository
from app.core.tenant import get_current_tenant_id
from app.domain.common.money import Money
from app.domain.sales import Sale, SaleItem, SalePayment
from app.infrastructure.db.models.sale_model import SaleItemModel, SaleModel
from app.infrastructure.db.models.sale_payment_model import SalePaymentModel


class SqlAlchemySalesRepository(SalesRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _apply_tenant_filter(self, stmt):
        """Apply tenant filter if context is set."""
        tenant_id = get_current_tenant_id()
        if tenant_id and hasattr(SaleModel, "tenant_id"):
            return stmt.where(SaleModel.tenant_id == tenant_id)
        return stmt

    async def add_sale(self, sale: Sale, items: Sequence[SaleItem]) -> None:
        if not items:
            raise ValueError("Sale must include items to persist")

        created_at = sale.created_at
        closed_at = sale.closed_at
        item_timestamp = closed_at or created_at or datetime.now(UTC)
        tenant_id = get_current_tenant_id()

        sale_model = SaleModel(
            id=sale.id,
            currency=sale.currency,
            total_amount=sale.total_amount.amount,
            total_quantity=sale.total_quantity,
            created_at=created_at,
            closed_at=closed_at,
            customer_id=sale.customer_id,
            shift_id=sale.shift_id,
            tenant_id=tenant_id,  # Set tenant from context
            items=[
                SaleItemModel(
                    id=item.id,
                    product_id=item.product_id,
                    quantity=item.quantity,
                    unit_price=item.unit_price.amount,
                    line_total=item.line_total.amount,
                    created_at=item_timestamp,
                )
                for item in items
            ],
            payment_allocations=[
                SalePaymentModel(
                    id=payment.id,
                    sale_id=sale.id,
                    payment_method=payment.payment_method,
                    amount=payment.amount.amount,
                    currency=payment.amount.currency,
                    reference_number=payment.reference_number,
                    card_last_four=payment.card_last_four,
                    gift_card_id=payment.gift_card_id,
                    gift_card_code=payment.gift_card_code,
                    created_at=payment.created_at,
                )
                for payment in sale.payments
            ],
        )
        self._session.add(sale_model)
        await self._session.flush()

    async def get_by_id(self, sale_id: str) -> Sale | None:
        stmt = (
            select(SaleModel)
            .options(
                selectinload(SaleModel.items),
                selectinload(SaleModel.payment_allocations),
            )
            .where(SaleModel.id == sale_id)
        )
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_sale(model)

    async def list_sales(
        self,
        *,
        customer_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[Sale], int]:
        stmt = (
            select(SaleModel)
            .options(
                selectinload(SaleModel.items),
                selectinload(SaleModel.payment_allocations),
            )
            .order_by(SaleModel.created_at.desc())
        )
        count_stmt = select(func.count(SaleModel.id))
        
        # Apply tenant filter
        stmt = self._apply_tenant_filter(stmt)
        count_stmt = self._apply_tenant_filter(count_stmt)

        if customer_id is not None:
            stmt = stmt.where(SaleModel.customer_id == customer_id)
            count_stmt = count_stmt.where(SaleModel.customer_id == customer_id)
        if date_from is not None:
            stmt = stmt.where(SaleModel.created_at >= date_from)
            count_stmt = count_stmt.where(SaleModel.created_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(SaleModel.created_at <= date_to)
            count_stmt = count_stmt.where(SaleModel.created_at <= date_to)

        stmt = stmt.offset(offset).limit(limit)

        sales_result = await self._session.execute(stmt)
        sale_models = sales_result.scalars().all()
        count_result = await self._session.execute(count_stmt)
        total = count_result.scalar_one()

        sales = [self._to_sale(model) for model in sale_models]
        return sales, int(total)

    async def list_sales_for_customer(
        self,
        customer_id: str,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[Sale], int]:
        return await self.list_sales(customer_id=customer_id, offset=offset, limit=limit)

    async def get_customer_sales_summary(self, customer_id: str) -> CustomerSalesSummary:
        summary_stmt = select(
            func.count(SaleModel.id),
            func.coalesce(func.sum(SaleModel.total_amount), 0),
            func.coalesce(func.sum(SaleModel.total_quantity), 0),
            func.min(SaleModel.created_at),
            func.max(SaleModel.created_at),
        ).where(SaleModel.customer_id == customer_id)

        result = await self._session.execute(summary_stmt)
        total_sales, total_amount, total_quantity, first_sale_at, last_sale_at = result.one()

        total_sales_int = int(total_sales or 0)
        total_amount_decimal = Decimal(total_amount or 0).quantize(Decimal("0.01"))
        total_quantity_int = int(total_quantity or 0)

        currency: str | None = None
        last_sale_id: str | None = None
        last_sale_amount: Decimal | None = None

        if total_sales_int > 0:
            last_sale_stmt = (
                select(
                    SaleModel.id,
                    SaleModel.currency,
                    SaleModel.total_amount,
                )
                .where(SaleModel.customer_id == customer_id)
                .order_by(SaleModel.created_at.desc())
                .limit(1)
            )
            last_sale_result = await self._session.execute(last_sale_stmt)
            last_row = last_sale_result.first()
            if last_row is not None:
                last_sale_id = last_row[0]
                currency = last_row[1]
                last_sale_amount = Decimal(last_row[2]).quantize(Decimal("0.01"))

        return CustomerSalesSummary(
            currency=currency,
            total_sales=total_sales_int,
            total_amount=total_amount_decimal,
            total_quantity=total_quantity_int,
            first_sale_at=first_sale_at,
            last_sale_at=last_sale_at,
            last_sale_id=last_sale_id,
            last_sale_amount=last_sale_amount,
        )

    def _to_sale(self, model: SaleModel) -> Sale:
        sale = Sale(
            id=model.id,
            currency=model.currency,
            created_at=model.created_at,
            closed_at=model.closed_at,
            customer_id=model.customer_id,
            shift_id=model.shift_id,
        )
        items: list[SaleItem] = []
        for item_model in model.items:
            item = SaleItem(
                id=item_model.id,
                product_id=item_model.product_id,
                quantity=item_model.quantity,
                unit_price=Money(item_model.unit_price, sale.currency),
                line_total=Money(item_model.line_total, sale.currency),
            )
            items.append(item)
        sale.items.extend(items)

        payments: list[SalePayment] = []
        for payment_model in model.payment_allocations:
            payment = SalePayment(
                id=payment_model.id,
                payment_method=payment_model.payment_method,
                amount=Money(payment_model.amount, sale.currency),
                reference_number=payment_model.reference_number,
                card_last_four=payment_model.card_last_four,
                gift_card_id=payment_model.gift_card_id,
                gift_card_code=payment_model.gift_card_code,
                created_at=payment_model.created_at,
            )
            payments.append(payment)
        sale.payments.extend(payments)
        return sale
