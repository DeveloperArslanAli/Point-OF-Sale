"""Receipt use cases."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from app.application.receipts.ports import IReceiptRepository
from app.domain.common.errors import NotFoundError
from app.domain.receipts import Receipt, ReceiptLineItem, ReceiptPayment, ReceiptTotals


class CreateReceipt:
    """Create a new receipt."""

    def __init__(self, receipt_repository: IReceiptRepository) -> None:
        self._receipt_repository = receipt_repository

    async def execute(
        self,
        sale_id: str,
        receipt_number: str,
        store_name: str,
        store_address: str,
        store_phone: str,
        cashier_name: str,
        line_items: list[ReceiptLineItem],
        payments: list[ReceiptPayment],
        totals: ReceiptTotals,
        sale_date: datetime,
        tax_rate: Decimal,
        store_tax_id: Optional[str] = None,
        customer_name: Optional[str] = None,
        customer_email: Optional[str] = None,
        notes: Optional[str] = None,
        footer_message: Optional[str] = "Thank you for your business!",
        format_type: str = "thermal",
        locale: str = "en_US",
    ) -> Receipt:
        """Create and persist a receipt."""
        receipt = Receipt.create(
            sale_id=sale_id,
            receipt_number=receipt_number,
            store_name=store_name,
            store_address=store_address,
            store_phone=store_phone,
            cashier_name=cashier_name,
            line_items=line_items,
            payments=payments,
            totals=totals,
            sale_date=sale_date,
            tax_rate=tax_rate,
            store_tax_id=store_tax_id,
            customer_name=customer_name,
            customer_email=customer_email,
            notes=notes,
            footer_message=footer_message,
            format_type=format_type,
            locale=locale,
        )

        await self._receipt_repository.add(receipt)
        return receipt


class GetReceipt:
    """Get receipt by ID."""

    def __init__(self, receipt_repository: IReceiptRepository) -> None:
        self._receipt_repository = receipt_repository

    async def execute(self, receipt_id: str) -> Receipt:
        """Retrieve receipt."""
        receipt = await self._receipt_repository.get_by_id(receipt_id)
        if not receipt:
            raise NotFoundError(f"Receipt {receipt_id} not found")
        return receipt


class GetReceiptBySaleId:
    """Get receipt by sale ID."""

    def __init__(self, receipt_repository: IReceiptRepository) -> None:
        self._receipt_repository = receipt_repository

    async def execute(self, sale_id: str) -> Receipt:
        """Retrieve receipt by sale ID."""
        receipt = await self._receipt_repository.get_by_sale_id(sale_id)
        if not receipt:
            raise NotFoundError(f"Receipt for sale {sale_id} not found")
        return receipt


class GetReceiptByNumber:
    """Get receipt by receipt number."""

    def __init__(self, receipt_repository: IReceiptRepository) -> None:
        self._receipt_repository = receipt_repository

    async def execute(self, receipt_number: str) -> Receipt:
        """Retrieve receipt by receipt number."""
        receipt = await self._receipt_repository.get_by_receipt_number(receipt_number)
        if not receipt:
            raise NotFoundError(f"Receipt {receipt_number} not found")
        return receipt


class ListReceiptsByDateRange:
    """List receipts within a date range."""

    def __init__(self, receipt_repository: IReceiptRepository) -> None:
        self._receipt_repository = receipt_repository

    async def execute(
        self,
        start_date: str,
        end_date: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Receipt]:
        """List receipts in date range."""
        return await self._receipt_repository.list_by_date_range(
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset,
        )
