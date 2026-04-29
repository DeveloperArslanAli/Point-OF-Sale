from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping, Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.application.returns.ports import ReturnsRepository
from app.core.tenant import get_current_tenant_id
from app.domain.returns import Return, ReturnItem
from app.domain.common.money import Money
from app.infrastructure.db.models.return_model import ReturnItemModel, ReturnModel


class SqlAlchemyReturnsRepository(ReturnsRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _apply_tenant_filter(self, stmt: Select[Any]) -> Select[Any]:
        """Apply tenant filter if context is set."""
        tenant_id = get_current_tenant_id()
        if tenant_id:
            return stmt.where(ReturnModel.tenant_id == tenant_id)
        return stmt

    async def add_return(self, return_: Return, items: Sequence[ReturnItem]) -> None:
        if not items:
            raise ValueError("Return must include items to persist")

        created_at = return_.created_at
        tenant_id = get_current_tenant_id()
        return_model = ReturnModel(
            id=return_.id,
            tenant_id=tenant_id,
            sale_id=return_.sale_id,
            currency=return_.currency,
            total_amount=return_.total_amount.amount,
            total_quantity=return_.total_quantity,
            created_at=created_at,
            items=[
                ReturnItemModel(
                    id=item.id,
                    sale_item_id=item.sale_item_id,
                    product_id=item.product_id,
                    quantity=item.quantity,
                    unit_price=item.unit_price.amount,
                    line_total=item.line_total.amount,
                    created_at=created_at,
                )
                for item in items
            ],
        )
        self._session.add(return_model)
        await self._session.flush()

    async def get_returned_quantities(self, sale_item_ids: Sequence[str]) -> Mapping[str, int]:
        if not sale_item_ids:
            return {}

        stmt = (
            select(ReturnItemModel.sale_item_id, func.coalesce(func.sum(ReturnItemModel.quantity), 0))
            .where(ReturnItemModel.sale_item_id.in_(sale_item_ids))
            .group_by(ReturnItemModel.sale_item_id)
        )
        result = await self._session.execute(stmt)
        return {row[0]: int(row[1]) for row in result.all()}

    async def get_by_id(self, return_id: str) -> Return | None:
        stmt = (
            select(ReturnModel)
            .options(selectinload(ReturnModel.items))
            .where(ReturnModel.id == return_id)
        )
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_return(model)

    async def list_returns(
        self,
        *,
        sale_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[Return], int]:
        stmt = (
            select(ReturnModel)
            .options(selectinload(ReturnModel.items))
            .order_by(ReturnModel.created_at.desc())
        )
        count_stmt = select(func.count(ReturnModel.id))
        
        # Apply tenant filter
        stmt = self._apply_tenant_filter(stmt)
        tenant_id = get_current_tenant_id()
        if tenant_id:
            count_stmt = count_stmt.where(ReturnModel.tenant_id == tenant_id)

        if sale_id is not None:
            stmt = stmt.where(ReturnModel.sale_id == sale_id)
            count_stmt = count_stmt.where(ReturnModel.sale_id == sale_id)
        if date_from is not None:
            stmt = stmt.where(ReturnModel.created_at >= date_from)
            count_stmt = count_stmt.where(ReturnModel.created_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(ReturnModel.created_at <= date_to)
            count_stmt = count_stmt.where(ReturnModel.created_at <= date_to)

        stmt = stmt.offset(offset).limit(limit)

        rows = await self._session.execute(stmt)
        models = rows.scalars().all()
        count_result = await self._session.execute(count_stmt)
        total = count_result.scalar_one()

        returns = [self._to_return(model) for model in models]
        return returns, int(total)

    def _to_return(self, model: ReturnModel) -> Return:
        return_ = Return(
            id=model.id,
            sale_id=model.sale_id,
            currency=model.currency,
            created_at=model.created_at,
        )
        items = [self._to_return_item(item_model, model.currency) for item_model in model.items]
        return_.items.extend(items)
        return return_

    @staticmethod
    def _to_return_item(model: ReturnItemModel, currency: str) -> ReturnItem:
        unit_price = Money(Decimal(model.unit_price), currency)
        line_total = Money(Decimal(model.line_total), currency)
        return ReturnItem(
            id=model.id,
            sale_item_id=model.sale_item_id,
            product_id=model.product_id,
            quantity=model.quantity,
            unit_price=unit_price,
            line_total=line_total,
        )
