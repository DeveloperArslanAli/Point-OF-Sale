from __future__ import annotations

from decimal import Decimal
from typing import Any, Sequence

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import ColumnElement

from app.application.catalog.ports import ProductRepository
from app.core.tenant import get_current_tenant_id
from app.domain.catalog.entities import Product
from app.domain.common.money import Money
from app.infrastructure.db.models.product_model import ProductModel


class SqlAlchemyProductRepository(ProductRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    def _apply_tenant_filter(self, stmt):
        """Apply tenant filter if context is set."""
        tenant_id = get_current_tenant_id()
        if tenant_id and hasattr(ProductModel, "tenant_id"):
            return stmt.where(ProductModel.tenant_id == tenant_id)
        return stmt

    async def add(self, product: Product) -> None:
        tenant_id = get_current_tenant_id()
        model = ProductModel(
            id=product.id,
            name=product.name,
            sku=product.sku,
            price_retail=product.price_retail.amount,
            purchase_price=product.purchase_price.amount,
            category_id=product.category_id,
            active=product.active,
            version=product.version,
            tenant_id=tenant_id,
        )
        self._session.add(model)
        await self._session.flush()

    async def get_by_sku(self, sku: str) -> Product | None:
        stmt = select(ProductModel).where(ProductModel.sku == sku)
        stmt = self._apply_tenant_filter(stmt)
        model = await self._fetch_one(stmt)
        return self._to_entity(model)

    async def get_by_id(self, product_id: str, *, lock: bool = False) -> Product | None:
        stmt = select(ProductModel).where(ProductModel.id == product_id)
        stmt = self._apply_tenant_filter(stmt)
        if lock:
            stmt = stmt.with_for_update()
        model = await self._fetch_one(stmt)
        return self._to_entity(model)

    async def update(self, product: Product, *, expected_version: int) -> bool:
        stmt = (
            update(ProductModel)
            .where(ProductModel.id == product.id, ProductModel.version == expected_version)
            .values(
                name=product.name,
                sku=product.sku,
                price_retail=product.price_retail.amount,
                purchase_price=product.purchase_price.amount,
                category_id=product.category_id,
                active=product.active,
                updated_at=product.updated_at,
                version=product.version,
            )
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    async def _fetch_one(self, stmt: Select[tuple[ProductModel]]) -> ProductModel | None:
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    def _to_entity(self, model: ProductModel | None) -> Product | None:
        if model is None:
            return None
        return Product(
            id=model.id,
            name=model.name,
            sku=model.sku,
            price_retail=Money(Decimal(str(model.price_retail))),
            purchase_price=Money(Decimal(str(model.purchase_price))),
            category_id=model.category_id,
            active=model.active,
            created_at=model.created_at,
            updated_at=model.updated_at,
            version=model.version,
        )

    async def list_products(
        self,
        *,
        search: str | None = None,
        category_id: str | None = None,
        active: bool | None = None,
        min_price: Decimal | None = None,
        max_price: Decimal | None = None,
        sort_by: str = "created_at",
        sort_direction: str = "desc",
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[Product], int]:
        stmt = select(ProductModel)
        count_stmt = select(func.count(ProductModel.id))
        
        # Apply tenant filter
        stmt = self._apply_tenant_filter(stmt)
        count_stmt = self._apply_tenant_filter(count_stmt)
        
        filters: list[ColumnElement[bool]] = []
        if search:
            like = f"%{search.lower()}%"
            condition = func.lower(ProductModel.name).like(like)
            sku_condition = func.lower(ProductModel.sku).like(like)
            filters.append(condition | sku_condition)
        if category_id:
            filters.append(ProductModel.category_id == category_id)
        if active is not None:
            filters.append(ProductModel.active == active)
        if min_price is not None:
            filters.append(ProductModel.price_retail >= min_price)
        if max_price is not None:
            filters.append(ProductModel.price_retail <= max_price)

        if filters:
            for cond in filters:
                stmt = stmt.where(cond)
                count_stmt = count_stmt.where(cond)

        sort_columns: dict[str, ColumnElement[Any] | InstrumentedAttribute[Any]] = {
            "created_at": ProductModel.created_at,
            "name": func.lower(ProductModel.name),
            "sku": func.lower(ProductModel.sku),
            "retail_price": ProductModel.price_retail,
        }
        sort_column = sort_columns.get(sort_by, ProductModel.created_at)
        order_clause = sort_column.desc() if sort_direction == "desc" else sort_column.asc()

        stmt = stmt.order_by(order_clause, ProductModel.created_at.desc()).offset(offset).limit(limit)
        res = await self._session.execute(stmt)
        rows = res.scalars().all()
        count_res = await self._session.execute(count_stmt)
        total = count_res.scalar_one()
        products = [
            Product(
                id=m.id,
                name=m.name,
                sku=m.sku,
                price_retail=Money(Decimal(str(m.price_retail))),
                purchase_price=Money(Decimal(str(m.purchase_price))),
                category_id=m.category_id,
                active=m.active,
                created_at=m.created_at,
                updated_at=m.updated_at,
                version=m.version,
            )
            for m in rows
        ]
        return products, int(total)
