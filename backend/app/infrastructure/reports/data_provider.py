"""Report data provider implementation."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.reports.ports import IReportDataProvider
from app.domain.reports.entities import (
    FilterOperator,
    ReportDefinition,
    ReportFilter,
    ReportType,
)
from app.infrastructure.db.models.customer_model import CustomerModel
from app.infrastructure.db.models.employee_model import EmployeeModel
from app.infrastructure.db.models.gift_card_model import GiftCardModel
from app.infrastructure.db.models.inventory_movement_model import InventoryMovementModel
from app.infrastructure.db.models.product_model import ProductModel
from app.infrastructure.db.models.promotion_model import PromotionModel
from app.infrastructure.db.models.purchase_model import PurchaseOrderModel
from app.infrastructure.db.models.return_model import ReturnModel
from app.infrastructure.db.models.sale_model import SaleModel


class SqlAlchemyReportDataProvider(IReportDataProvider):
    """
    Report data provider using SQLAlchemy.
    
    Fetches data from database based on report type and filters.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def fetch_data(
        self,
        definition: ReportDefinition,
        parameters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Fetch data based on report type."""
        handlers = {
            ReportType.SALES: self._fetch_sales_data,
            ReportType.INVENTORY: self._fetch_inventory_data,
            ReportType.CUSTOMERS: self._fetch_customers_data,
            ReportType.RETURNS: self._fetch_returns_data,
            ReportType.PURCHASES: self._fetch_purchases_data,
            ReportType.EMPLOYEES: self._fetch_employees_data,
            ReportType.GIFT_CARDS: self._fetch_gift_cards_data,
            ReportType.PROMOTIONS: self._fetch_promotions_data,
        }

        handler = handlers.get(definition.report_type)
        if not handler:
            return []

        return await handler(definition, parameters)

    async def _fetch_sales_data(
        self,
        definition: ReportDefinition,
        parameters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Fetch sales report data."""
        stmt = select(
            SaleModel.id,
            SaleModel.sale_number,
            SaleModel.total_amount,
            SaleModel.tax_amount,
            SaleModel.discount_amount,
            SaleModel.status,
            SaleModel.created_at,
            SaleModel.customer_id,
            SaleModel.cashier_id,
        )

        # Apply tenant filter
        if definition.tenant_id:
            stmt = stmt.where(SaleModel.tenant_id == definition.tenant_id)

        # Apply definition filters
        stmt = self._apply_filters(stmt, SaleModel, definition.filters, parameters)

        # Apply date range from parameters
        if "start_date" in parameters:
            stmt = stmt.where(SaleModel.created_at >= parameters["start_date"])
        if "end_date" in parameters:
            stmt = stmt.where(SaleModel.created_at <= parameters["end_date"])

        # Order by date descending
        stmt = stmt.order_by(SaleModel.created_at.desc()).limit(10000)

        result = await self._session.execute(stmt)
        rows = result.mappings().all()

        return [
            {
                "id": row["id"],
                "sale_number": row["sale_number"],
                "total_amount": float(row["total_amount"] or 0),
                "tax_amount": float(row["tax_amount"] or 0),
                "discount_amount": float(row["discount_amount"] or 0),
                "status": row["status"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "customer_id": row["customer_id"],
                "cashier_id": row["cashier_id"],
            }
            for row in rows
        ]

    async def _fetch_inventory_data(
        self,
        definition: ReportDefinition,
        parameters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Fetch inventory report data."""
        # Get products with their stock levels from movements
        stmt = select(
            ProductModel.id,
            ProductModel.name,
            ProductModel.sku,
            ProductModel.price_retail,
            ProductModel.purchase_price,
            ProductModel.active,
            func.coalesce(
                func.sum(
                    func.case(
                        (InventoryMovementModel.direction == "IN", InventoryMovementModel.quantity),
                        else_=-InventoryMovementModel.quantity,
                    )
                ),
                0
            ).label("stock_quantity"),
        ).outerjoin(
            InventoryMovementModel,
            ProductModel.id == InventoryMovementModel.product_id,
        ).group_by(
            ProductModel.id,
            ProductModel.name,
            ProductModel.sku,
            ProductModel.price_retail,
            ProductModel.purchase_price,
            ProductModel.active,
        )

        # Apply filters
        if "active_only" in parameters and parameters["active_only"]:
            stmt = stmt.where(ProductModel.active == True)  # noqa: E712

        if "low_stock_threshold" in parameters:
            threshold = parameters["low_stock_threshold"]
            stmt = stmt.having(
                func.coalesce(
                    func.sum(
                        func.case(
                            (InventoryMovementModel.direction == "IN", InventoryMovementModel.quantity),
                            else_=-InventoryMovementModel.quantity,
                        )
                    ),
                    0
                ) < threshold
            )

        stmt = stmt.order_by(ProductModel.name.asc()).limit(10000)

        result = await self._session.execute(stmt)
        rows = result.mappings().all()

        return [
            {
                "id": row["id"],
                "name": row["name"],
                "sku": row["sku"],
                "price_retail": float(row["price_retail"] or 0),
                "purchase_price": float(row["purchase_price"] or 0),
                "stock_quantity": int(row["stock_quantity"] or 0),
                "active": row["active"],
            }
            for row in rows
        ]

    async def _fetch_customers_data(
        self,
        definition: ReportDefinition,
        parameters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Fetch customers report data."""
        stmt = select(
            CustomerModel.id,
            CustomerModel.name,
            CustomerModel.email,
            CustomerModel.phone,
            CustomerModel.loyalty_points,
            CustomerModel.total_purchases,
            CustomerModel.created_at,
        )

        # Apply tenant filter
        if definition.tenant_id:
            stmt = stmt.where(CustomerModel.tenant_id == definition.tenant_id)

        # Apply definition filters
        stmt = self._apply_filters(stmt, CustomerModel, definition.filters, parameters)

        stmt = stmt.order_by(CustomerModel.name.asc()).limit(10000)

        result = await self._session.execute(stmt)
        rows = result.mappings().all()

        return [
            {
                "id": row["id"],
                "name": row["name"],
                "email": row["email"],
                "phone": row["phone"],
                "loyalty_points": row["loyalty_points"],
                "total_purchases": float(row["total_purchases"] or 0),
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
            for row in rows
        ]

    async def _fetch_returns_data(
        self,
        definition: ReportDefinition,
        parameters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Fetch returns report data."""
        stmt = select(
            ReturnModel.id,
            ReturnModel.sale_id,
            ReturnModel.currency,
            ReturnModel.total_amount,
            ReturnModel.total_quantity,
            ReturnModel.created_at,
        )

        # Apply date range from parameters
        if "start_date" in parameters:
            stmt = stmt.where(ReturnModel.created_at >= parameters["start_date"])
        if "end_date" in parameters:
            stmt = stmt.where(ReturnModel.created_at <= parameters["end_date"])

        # Order by date descending
        stmt = stmt.order_by(ReturnModel.created_at.desc()).limit(10000)

        result = await self._session.execute(stmt)
        rows = result.mappings().all()

        return [
            {
                "id": row["id"],
                "sale_id": row["sale_id"],
                "currency": row["currency"],
                "total_amount": float(row["total_amount"] or 0),
                "total_quantity": int(row["total_quantity"] or 0),
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
            for row in rows
        ]

    async def _fetch_purchases_data(
        self,
        definition: ReportDefinition,
        parameters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Fetch purchases (purchase orders) report data."""
        stmt = select(
            PurchaseOrderModel.id,
            PurchaseOrderModel.supplier_id,
            PurchaseOrderModel.currency,
            PurchaseOrderModel.total_amount,
            PurchaseOrderModel.total_quantity,
            PurchaseOrderModel.created_at,
            PurchaseOrderModel.received_at,
        )

        # Apply tenant filter
        if definition.tenant_id:
            stmt = stmt.where(PurchaseOrderModel.tenant_id == definition.tenant_id)

        # Apply definition filters
        stmt = self._apply_filters(stmt, PurchaseOrderModel, definition.filters, parameters)

        # Apply date range from parameters
        if "start_date" in parameters:
            stmt = stmt.where(PurchaseOrderModel.created_at >= parameters["start_date"])
        if "end_date" in parameters:
            stmt = stmt.where(PurchaseOrderModel.created_at <= parameters["end_date"])

        # Order by date descending
        stmt = stmt.order_by(PurchaseOrderModel.created_at.desc()).limit(10000)

        result = await self._session.execute(stmt)
        rows = result.mappings().all()

        return [
            {
                "id": row["id"],
                "supplier_id": row["supplier_id"],
                "currency": row["currency"],
                "total_amount": float(row["total_amount"] or 0),
                "total_quantity": int(row["total_quantity"] or 0),
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "received_at": row["received_at"].isoformat() if row["received_at"] else None,
            }
            for row in rows
        ]

    async def _fetch_employees_data(
        self,
        definition: ReportDefinition,
        parameters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Fetch employees report data."""
        stmt = select(
            EmployeeModel.id,
            EmployeeModel.first_name,
            EmployeeModel.last_name,
            EmployeeModel.email,
            EmployeeModel.phone,
            EmployeeModel.position,
            EmployeeModel.hire_date,
            EmployeeModel.base_salary,
            EmployeeModel.is_active,
            EmployeeModel.created_at,
        )

        # Apply tenant filter
        if definition.tenant_id:
            stmt = stmt.where(EmployeeModel.tenant_id == definition.tenant_id)

        # Apply definition filters
        stmt = self._apply_filters(stmt, EmployeeModel, definition.filters, parameters)

        # Filter by active status if specified
        if "active_only" in parameters and parameters["active_only"]:
            stmt = stmt.where(EmployeeModel.is_active == True)  # noqa: E712

        stmt = stmt.order_by(EmployeeModel.last_name.asc(), EmployeeModel.first_name.asc()).limit(10000)

        result = await self._session.execute(stmt)
        rows = result.mappings().all()

        return [
            {
                "id": row["id"],
                "first_name": row["first_name"],
                "last_name": row["last_name"],
                "full_name": f"{row['first_name']} {row['last_name']}",
                "email": row["email"],
                "phone": row["phone"],
                "position": row["position"],
                "hire_date": row["hire_date"].isoformat() if row["hire_date"] else None,
                "base_salary": float(row["base_salary"] or 0),
                "is_active": row["is_active"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
            for row in rows
        ]

    async def _fetch_gift_cards_data(
        self,
        definition: ReportDefinition,
        parameters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Fetch gift cards report data."""
        stmt = select(
            GiftCardModel.id,
            GiftCardModel.code,
            GiftCardModel.initial_balance,
            GiftCardModel.current_balance,
            GiftCardModel.currency,
            GiftCardModel.status,
            GiftCardModel.issued_date,
            GiftCardModel.expiry_date,
            GiftCardModel.customer_id,
            GiftCardModel.created_at,
        )

        # Apply tenant filter
        if definition.tenant_id:
            stmt = stmt.where(GiftCardModel.tenant_id == definition.tenant_id)

        # Apply definition filters
        stmt = self._apply_filters(stmt, GiftCardModel, definition.filters, parameters)

        # Filter by status if specified
        if "status" in parameters:
            stmt = stmt.where(GiftCardModel.status == parameters["status"])

        stmt = stmt.order_by(GiftCardModel.created_at.desc()).limit(10000)

        result = await self._session.execute(stmt)
        rows = result.mappings().all()

        return [
            {
                "id": row["id"],
                "code": row["code"],
                "initial_balance": float(row["initial_balance"] or 0),
                "current_balance": float(row["current_balance"] or 0),
                "balance_used": float((row["initial_balance"] or 0) - (row["current_balance"] or 0)),
                "currency": row["currency"],
                "status": row["status"],
                "issued_date": row["issued_date"].isoformat() if row["issued_date"] else None,
                "expiry_date": row["expiry_date"].isoformat() if row["expiry_date"] else None,
                "customer_id": row["customer_id"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
            for row in rows
        ]

    async def _fetch_promotions_data(
        self,
        definition: ReportDefinition,
        parameters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Fetch promotions report data."""
        stmt = select(
            PromotionModel.id,
            PromotionModel.name,
            PromotionModel.description,
            PromotionModel.status,
            PromotionModel.discount_rule,
            PromotionModel.start_date,
            PromotionModel.end_date,
            PromotionModel.usage_limit,
            PromotionModel.usage_count,
            PromotionModel.coupon_code,
        )

        # Apply tenant filter
        if definition.tenant_id:
            stmt = stmt.where(PromotionModel.tenant_id == definition.tenant_id)

        # Apply definition filters
        stmt = self._apply_filters(stmt, PromotionModel, definition.filters, parameters)

        # Filter by status if specified
        if "status" in parameters:
            stmt = stmt.where(PromotionModel.status == parameters["status"])

        stmt = stmt.order_by(PromotionModel.start_date.desc()).limit(10000)

        result = await self._session.execute(stmt)
        rows = result.mappings().all()

        return [
            {
                "id": row["id"],
                "name": row["name"],
                "description": row["description"],
                "status": row["status"],
                "discount_rule": row["discount_rule"],
                "start_date": row["start_date"].isoformat() if row["start_date"] else None,
                "end_date": row["end_date"].isoformat() if row["end_date"] else None,
                "usage_limit": row["usage_limit"],
                "usage_count": row["usage_count"],
                "usage_remaining": (row["usage_limit"] - row["usage_count"]) if row["usage_limit"] else None,
                "coupon_code": row["coupon_code"],
            }
            for row in rows
        ]

    def _apply_filters(
        self,
        stmt,
        model,
        filters: list[ReportFilter],
        parameters: dict[str, Any],
    ):
        """Apply filters to a query."""
        for f in filters:
            # Check if filter value is overridden in parameters
            value = parameters.get(f.field, f.value)
            
            if not hasattr(model, f.field):
                continue

            column = getattr(model, f.field)

            if f.operator == FilterOperator.EQUALS:
                stmt = stmt.where(column == value)
            elif f.operator == FilterOperator.NOT_EQUALS:
                stmt = stmt.where(column != value)
            elif f.operator == FilterOperator.GREATER_THAN:
                stmt = stmt.where(column > value)
            elif f.operator == FilterOperator.GREATER_OR_EQUAL:
                stmt = stmt.where(column >= value)
            elif f.operator == FilterOperator.LESS_THAN:
                stmt = stmt.where(column < value)
            elif f.operator == FilterOperator.LESS_OR_EQUAL:
                stmt = stmt.where(column <= value)
            elif f.operator == FilterOperator.CONTAINS:
                stmt = stmt.where(column.ilike(f"%{value}%"))
            elif f.operator == FilterOperator.STARTS_WITH:
                stmt = stmt.where(column.ilike(f"{value}%"))
            elif f.operator == FilterOperator.IN:
                if isinstance(value, list):
                    stmt = stmt.where(column.in_(value))
            elif f.operator == FilterOperator.BETWEEN:
                value2 = parameters.get(f"{f.field}_end", f.value2)
                if value2:
                    stmt = stmt.where(column.between(value, value2))
            elif f.operator == FilterOperator.IS_NULL:
                stmt = stmt.where(column.is_(None))
            elif f.operator == FilterOperator.IS_NOT_NULL:
                stmt = stmt.where(column.isnot(None))

        return stmt
