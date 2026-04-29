from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from app.application.cash_drawer import ICashDrawerRepository
from app.application.catalog.ports import ProductRepository
from app.application.common.event_dispatcher import EventDispatcher
from app.application.gift_cards.ports import IGiftCardRepository
from app.application.customers.ports import CustomerRepository
from app.application.inventory.ports import InventoryMovementRepository
from app.application.sales.ports import SalesRepository
from app.application.shifts import IShiftRepository
from app.domain.cash_drawer import MovementType
from app.domain.catalog.entities import Product
from app.domain.common.errors import ConflictError, NotFoundError, ValidationError
from app.domain.inventory import InventoryMovement, MovementDirection
from app.domain.sales import Sale, SalePayment
from app.domain.sales.events import SaleRecordedEvent


@dataclass(slots=True)
class SaleLineInput:
    product_id: str
    quantity: int
    unit_price: Decimal


@dataclass(slots=True)
class SalePaymentInput:
    """Input for a single payment within a sale."""
    payment_method: str
    amount: Decimal
    reference_number: str | None = None
    card_last_four: str | None = None
    gift_card_code: str | None = None


@dataclass(slots=True)
class RecordSaleInput:
    lines: Sequence[SaleLineInput]
    payments: Sequence[SalePaymentInput]
    currency: str = "USD"
    customer_id: str | None = None
    shift_id: str | None = None


@dataclass(slots=True)
class RecordSaleResult:
    sale: Sale
    movements: list[InventoryMovement]


class RecordSaleUseCase:
    def __init__(
        self,
        product_repo: ProductRepository,
        sales_repo: SalesRepository,
        inventory_repo: InventoryMovementRepository,
        customer_repo: CustomerRepository | None = None,
        gift_card_repo: IGiftCardRepository | None = None,
        event_dispatcher: EventDispatcher | None = None,
        shift_repo: IShiftRepository | None = None,
        drawer_repo: ICashDrawerRepository | None = None,
        *,
        enforce_stock: bool = True,
    ) -> None:
        self._product_repo = product_repo
        self._sales_repo = sales_repo
        self._inventory_repo = inventory_repo
        self._customer_repo = customer_repo
        self._gift_card_repo = gift_card_repo
        self._event_dispatcher = event_dispatcher
        self._shift_repo = shift_repo
        self._drawer_repo = drawer_repo
        self._enforce_stock = enforce_stock

    async def execute(self, data: RecordSaleInput) -> RecordSaleResult:
        if not data.lines:
            raise ValidationError("Sale requires at least one line item")
        if not data.payments:
            raise ValidationError("Sale requires at least one payment")

        sale = Sale.start(currency=data.currency, shift_id=data.shift_id)
        product_cache: dict[str, Product] = {}
        required_quantities: dict[str, int] = {}
        cash_payment_total = Decimal("0")

        if data.customer_id is not None:
            if self._customer_repo is None:
                raise ValidationError("Customer support is not configured")
            customer = await self._customer_repo.get_by_id(data.customer_id)
            if customer is None:
                raise NotFoundError("Customer not found")
            if not customer.active:
                raise ValidationError("Customer is inactive")
            sale.assign_customer(customer.id)

        # Pre-fetch and lock products in deterministic order to prevent deadlocks
        unique_product_ids = sorted(list(set(line.product_id for line in data.lines)))
        for pid in unique_product_ids:
            product = await self._product_repo.get_by_id(pid, lock=True)
            if product is None:
                raise NotFoundError(f"Product {pid} not found")
            if not product.active:
                raise ValidationError(f"Product {product.id} is inactive")
            
            # Optimistic locking: touch the product to ensure serialization
            # This works on SQLite (write lock) and Postgres (version check)
            current_version = product.version
            product.version += 1
            success = await self._product_repo.update(product, expected_version=current_version)
            if not success:
                raise ConflictError(f"Product {pid} was modified concurrently")

            product_cache[pid] = product

        for line in data.lines:
            if line.quantity <= 0:
                raise ValidationError("Quantity must be positive")
            if line.unit_price <= Decimal("0"):
                raise ValidationError("Unit price must be positive")

            product = product_cache[line.product_id]
            sale.add_line(product_id=product.id, quantity=line.quantity, unit_price=line.unit_price)
            required_quantities[product.id] = required_quantities.get(product.id, 0) + line.quantity

        for product_id, required in required_quantities.items():
            stock = await self._inventory_repo.get_stock_level(product_id)
            if self._enforce_stock and stock.quantity_on_hand < required:
                raise ValidationError(f"Insufficient stock for product {product_id}")

        # Add payments to sale
        for payment_input in data.payments:
            method = payment_input.payment_method.lower()
            reference_number = payment_input.reference_number
            gift_card_code = payment_input.gift_card_code.strip().upper() if payment_input.gift_card_code else None
            gift_card_id: str | None = None

            if method == "gift_card":
                if self._gift_card_repo is None:
                    raise ValidationError("Gift card payments are not configured")

                candidate_code = gift_card_code or (reference_number.strip().upper() if reference_number else None)
                if candidate_code is None:
                    raise ValidationError("Gift card code is required for gift card payments")

                gift_card = await self._gift_card_repo.get_by_code(candidate_code)
                if gift_card is None:
                    raise NotFoundError(f"Gift card {candidate_code} not found")

                if gift_card.current_balance.currency != sale.currency:
                    raise ValidationError("Gift card currency does not match sale currency")

                try:
                    gift_card.redeem(payment_input.amount)
                except ValidationError as exc:
                    raise ValidationError(str(exc)) from exc

                await self._gift_card_repo.update(gift_card)

                gift_card_id = gift_card.id
                gift_card_code = gift_card.code
                reference_number = gift_card.code

            payment = SalePayment.create(
                payment_method=method,
                amount=payment_input.amount,
                currency=sale.currency,
                reference_number=reference_number,
                card_last_four=payment_input.card_last_four,
                gift_card_id=gift_card_id,
                gift_card_code=gift_card_code,
            )
            sale.add_payment(payment)

            # Track cash payments for drawer recording
            if method == "cash":
                cash_payment_total += payment_input.amount

        # Validate total payments match sale total
        sale.validate_payments()

        sale.close()

        movements: list[InventoryMovement] = []
        for item in sale.iter_items():
            movement = InventoryMovement.record(
                product_id=item.product_id,
                quantity=item.quantity,
                direction=MovementDirection.OUT,
                reason="sale",
                reference=sale.id,
                occurred_at=sale.closed_at,
            )
            await self._inventory_repo.add(movement)
            movements.append(movement)

        await self._sales_repo.add_sale(sale, list(sale.iter_items()))

        # Record cash payment to drawer if shift is linked and has open drawer
        if data.shift_id and self._shift_repo and self._drawer_repo and cash_payment_total > Decimal("0"):
            shift = await self._shift_repo.get_by_id(data.shift_id)
            if shift and shift.drawer_session_id:
                drawer = await self._drawer_repo.get_by_id(shift.drawer_session_id)
                if drawer and drawer.status.value == "open":
                    drawer.record_sale_cash(
                        cash_received=cash_payment_total,
                        change_given=Decimal("0"),  # Change is already accounted in sale payments
                        sale_id=sale.id,
                    )
                    # Persist the sale movement (last added)
                    sale_movement = drawer.movements[-1]
                    await self._drawer_repo.add_movement(sale_movement)

        if self._event_dispatcher is not None:
            event = SaleRecordedEvent(
                aggregate_id=sale.id,
                total_amount=str(sale.total_amount.amount),
                currency=sale.currency,
                customer_id=sale.customer_id,
            )
            await self._event_dispatcher.publish(event)

        return RecordSaleResult(sale=sale, movements=movements)
