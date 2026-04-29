"""Receipt repository implementation."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.receipts.ports import IReceiptRepository
from app.core.tenant import get_current_tenant_id
from app.domain.common.money import Money
from app.domain.receipts import Receipt, ReceiptLineItem, ReceiptPayment, ReceiptTotals
from app.infrastructure.db.models.receipt_model import ReceiptModel


class ReceiptRepository(IReceiptRepository):
    """Receipt repository using SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _apply_tenant_filter(self, stmt: Select[Any]) -> Select[Any]:
        """Apply tenant filter if context is set."""
        tenant_id = get_current_tenant_id()
        if tenant_id:
            return stmt.where(ReceiptModel.tenant_id == tenant_id)
        return stmt

    async def add(self, receipt: Receipt) -> None:
        """Add a new receipt."""
        model = self._to_model(receipt)
        model.tenant_id = get_current_tenant_id()
        self._session.add(model)
        await self._session.flush()

    async def get_by_id(self, receipt_id: str) -> Optional[Receipt]:
        """Get receipt by ID."""
        stmt = select(ReceiptModel).where(ReceiptModel.id == receipt_id)
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_sale_id(self, sale_id: str) -> Optional[Receipt]:
        """Get receipt by sale ID."""
        stmt = select(ReceiptModel).where(ReceiptModel.sale_id == sale_id)
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_receipt_number(self, receipt_number: str) -> Optional[Receipt]:
        """Get receipt by receipt number."""
        stmt = select(ReceiptModel).where(ReceiptModel.receipt_number == receipt_number)
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_by_date_range(
        self,
        start_date: str,
        end_date: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Receipt]:
        """List receipts within a date range."""
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
        
        stmt = (
            select(ReceiptModel)
            .where(ReceiptModel.sale_date >= start_dt)
            .where(ReceiptModel.sale_date <= end_dt)
            .order_by(ReceiptModel.sale_date.desc())
            .limit(limit)
            .offset(offset)
        )
        stmt = self._apply_tenant_filter(stmt)
        
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_entity(model) for model in models]

    async def update(self, receipt: Receipt) -> None:
        """Update an existing receipt."""
        stmt = select(ReceiptModel).where(ReceiptModel.id == receipt.id)
        stmt = self._apply_tenant_filter(stmt)
        result = await self._session.execute(stmt)
        model = result.scalar_one()
        
        # Update model fields
        model.notes = receipt.notes
        model.footer_message = receipt.footer_message
        model.version = receipt.version
        
        await self._session.flush()

    def _to_model(self, receipt: Receipt) -> ReceiptModel:
        """Convert Receipt entity to ReceiptModel."""
        return ReceiptModel(
            id=receipt.id,
            sale_id=receipt.sale_id,
            receipt_number=receipt.receipt_number,
            store_name=receipt.store_name,
            store_address=receipt.store_address,
            store_phone=receipt.store_phone,
            store_tax_id=receipt.store_tax_id,
            cashier_name=receipt.cashier_name,
            customer_name=receipt.customer_name,
            customer_email=receipt.customer_email,
            line_items=self._line_items_to_json(receipt.line_items),
            payments=self._payments_to_json(receipt.payments),
            totals=self._totals_to_json(receipt.totals),
            sale_date=receipt.sale_date,
            tax_rate=receipt.tax_rate,
            notes=receipt.notes,
            footer_message=receipt.footer_message,
            format_type=receipt.format_type,
            locale=receipt.locale,
            created_at=receipt.created_at,
            version=receipt.version,
        )

    def _to_entity(self, model: ReceiptModel) -> Receipt:
        """Convert ReceiptModel to Receipt entity."""
        return Receipt(
            id=model.id,
            sale_id=model.sale_id,
            receipt_number=model.receipt_number,
            store_name=model.store_name,
            store_address=model.store_address,
            store_phone=model.store_phone,
            store_tax_id=model.store_tax_id,
            cashier_name=model.cashier_name,
            customer_name=model.customer_name,
            customer_email=model.customer_email,
            line_items=self._json_to_line_items(model.line_items),
            payments=self._json_to_payments(model.payments),
            totals=self._json_to_totals(model.totals),
            sale_date=model.sale_date,
            tax_rate=model.tax_rate,
            notes=model.notes,
            footer_message=model.footer_message,
            format_type=model.format_type,
            locale=model.locale,
            created_at=model.created_at,
            version=model.version,
        )

    def _line_items_to_json(self, line_items: list[ReceiptLineItem]) -> dict:
        """Convert line items to JSON."""
        return {
            "items": [
                {
                    "product_name": item.product_name,
                    "sku": item.sku,
                    "quantity": str(item.quantity),
                    "unit_price": {
                        "amount": str(item.unit_price.amount),
                        "currency": item.unit_price.currency,
                    },
                    "line_total": {
                        "amount": str(item.line_total.amount),
                        "currency": item.line_total.currency,
                    },
                    "discount_amount": {
                        "amount": str(item.discount_amount.amount),
                        "currency": item.discount_amount.currency,
                    },
                }
                for item in line_items
            ]
        }

    def _json_to_line_items(self, data: dict) -> list[ReceiptLineItem]:
        """Convert JSON to line items."""
        return [
            ReceiptLineItem(
                product_name=item["product_name"],
                sku=item["sku"],
                quantity=Decimal(item["quantity"]),
                unit_price=Money(
                    Decimal(item["unit_price"]["amount"]),
                    item["unit_price"]["currency"],
                ),
                line_total=Money(
                    Decimal(item["line_total"]["amount"]),
                    item["line_total"]["currency"],
                ),
                discount_amount=Money(
                    Decimal(item["discount_amount"]["amount"]),
                    item["discount_amount"]["currency"],
                ),
            )
            for item in data["items"]
        ]

    def _payments_to_json(self, payments: list[ReceiptPayment]) -> dict:
        """Convert payments to JSON."""
        return {
            "payments": [
                {
                    "payment_method": payment.payment_method,
                    "amount": {
                        "amount": str(payment.amount.amount),
                        "currency": payment.amount.currency,
                    },
                    "reference_number": payment.reference_number,
                    "card_last_four": payment.card_last_four,
                }
                for payment in payments
            ]
        }

    def _json_to_payments(self, data: dict) -> list[ReceiptPayment]:
        """Convert JSON to payments."""
        return [
            ReceiptPayment(
                payment_method=payment["payment_method"],
                amount=Money(
                    Decimal(payment["amount"]["amount"]),
                    payment["amount"]["currency"],
                ),
                reference_number=payment.get("reference_number"),
                card_last_four=payment.get("card_last_four"),
            )
            for payment in data["payments"]
        ]

    def _totals_to_json(self, totals: ReceiptTotals) -> dict:
        """Convert totals to JSON."""
        return {
            "subtotal": {
                "amount": str(totals.subtotal.amount),
                "currency": totals.subtotal.currency,
            },
            "tax_amount": {
                "amount": str(totals.tax_amount.amount),
                "currency": totals.tax_amount.currency,
            },
            "discount_amount": {
                "amount": str(totals.discount_amount.amount),
                "currency": totals.discount_amount.currency,
            },
            "total": {
                "amount": str(totals.total.amount),
                "currency": totals.total.currency,
            },
            "amount_paid": {
                "amount": str(totals.amount_paid.amount),
                "currency": totals.amount_paid.currency,
            },
            "change_given": {
                "amount": str(totals.change_given.amount),
                "currency": totals.change_given.currency,
            },
        }

    def _json_to_totals(self, data: dict) -> ReceiptTotals:
        """Convert JSON to totals."""
        return ReceiptTotals(
            subtotal=Money(
                Decimal(data["subtotal"]["amount"]),
                data["subtotal"]["currency"],
            ),
            tax_amount=Money(
                Decimal(data["tax_amount"]["amount"]),
                data["tax_amount"]["currency"],
            ),
            discount_amount=Money(
                Decimal(data["discount_amount"]["amount"]),
                data["discount_amount"]["currency"],
            ),
            total=Money(
                Decimal(data["total"]["amount"]),
                data["total"]["currency"],
            ),
            amount_paid=Money(
                Decimal(data["amount_paid"]["amount"]),
                data["amount_paid"]["currency"],
            ),
            change_given=Money(
                Decimal(data["change_given"]["amount"]),
                data["change_given"]["currency"],
            ),
        )
