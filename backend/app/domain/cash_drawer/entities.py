"""Cash drawer domain entities."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum

from app.domain.common.errors import ValidationError
from app.domain.common.identifiers import new_ulid
from app.domain.common.money import Money


class DrawerStatus(str, Enum):
    """Cash drawer session status."""

    OPEN = "open"
    CLOSED = "closed"


class MovementType(str, Enum):
    """Cash movement type within a drawer session."""

    PAY_IN = "pay_in"  # Cash added (float top-up, refund float)
    PAYOUT = "payout"  # Cash removed (petty cash)
    DROP = "drop"  # Cash dropped to safe/bank
    PICKUP = "pickup"  # Cash picked up by manager
    CASH_IN = "cash_in"  # Cash received from sale
    SALE = "sale"  # Cash received from sale (alias)
    CHANGE = "change"  # Change given to customer
    REFUND = "refund"  # Cash refunded to customer


@dataclass(slots=True)
class CashMovement:
    """
    Individual cash movement within a drawer session.

    Tracks every cash transaction affecting the drawer balance.
    """

    id: str
    drawer_session_id: str
    movement_type: MovementType
    amount: Money
    reason: str | None = None
    reference_id: str | None = None  # sale_id, refund_id, etc.
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @staticmethod
    def create(
        *,
        drawer_session_id: str,
        movement_type: MovementType,
        amount: Decimal,
        currency: str = "USD",
        reason: str | None = None,
        reference_id: str | None = None,
    ) -> CashMovement:
        """Create a new cash movement."""
        if amount <= Decimal("0"):
            raise ValidationError(
                "cash movement amount must be positive",
                code="cash_movement.invalid_amount",
            )

        return CashMovement(
            id=new_ulid(),
            drawer_session_id=drawer_session_id,
            movement_type=movement_type,
            amount=Money(amount, currency),
            reason=reason,
            reference_id=reference_id,
        )


@dataclass(slots=True)
class CashDrawerSession:
    """
    Cash drawer session aggregate root.

    Represents a single drawer session from open to close, tracking
    all cash movements and calculating over/short on close.
    """

    id: str
    terminal_id: str
    opened_by: str  # user_id
    closed_by: str | None = None
    opening_float: Money = field(default_factory=lambda: Money(Decimal("0"), "USD"))
    closing_count: Money | None = None
    expected_balance: Money = field(default_factory=lambda: Money(Decimal("0"), "USD"))
    over_short: Money | None = None
    status: DrawerStatus = DrawerStatus.OPEN
    opened_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    closed_at: datetime | None = None
    version: int = 0
    movements: list[CashMovement] = field(default_factory=list)

    @staticmethod
    def open_drawer(
        *,
        terminal_id: str,
        opened_by: str,
        opening_float: Decimal,
        currency: str = "USD",
    ) -> CashDrawerSession:
        """
        Open a new cash drawer session.

        Args:
            terminal_id: Identifier for the POS terminal
            opened_by: User ID who opened the drawer
            opening_float: Starting cash amount
            currency: Currency code

        Returns:
            New open CashDrawerSession
        """
        if not terminal_id:
            raise ValidationError(
                "terminal_id is required",
                code="cash_drawer.missing_terminal",
            )
        if not opened_by:
            raise ValidationError(
                "opened_by user_id is required",
                code="cash_drawer.missing_user",
            )
        if opening_float < Decimal("0"):
            raise ValidationError(
                "opening float cannot be negative",
                code="cash_drawer.invalid_float",
            )

        float_money = Money(opening_float, currency)

        return CashDrawerSession(
            id=new_ulid(),
            terminal_id=terminal_id,
            opened_by=opened_by,
            opening_float=float_money,
            expected_balance=float_money,
        )

    def record_movement(
        self,
        *,
        movement_type: MovementType,
        amount: Decimal,
        reason: str | None = None,
        reference_id: str | None = None,
    ) -> CashMovement:
        """
        Record a cash movement and update expected balance.

        Args:
            movement_type: Type of movement
            amount: Positive amount of movement
            reason: Optional description
            reference_id: Optional reference (sale_id, etc.)

        Returns:
            Created CashMovement

        Raises:
            ValidationError: If drawer is closed or invalid amount
        """
        if self.status == DrawerStatus.CLOSED:
            raise ValidationError(
                "cannot record movement on closed drawer",
                code="cash_drawer.already_closed",
            )

        movement = CashMovement.create(
            drawer_session_id=self.id,
            movement_type=movement_type,
            amount=amount,
            currency=self.opening_float.currency,
            reason=reason,
            reference_id=reference_id,
        )

        # Update expected balance based on movement type
        if movement_type in (MovementType.PAY_IN, MovementType.SALE):
            self.expected_balance = self.expected_balance.add(movement.amount)
        elif movement_type in (MovementType.PAYOUT, MovementType.CHANGE, MovementType.REFUND):
            self.expected_balance = self.expected_balance.subtract(movement.amount)

        self.movements.append(movement)
        self._touch()
        return movement

    def record_sale_cash(
        self,
        *,
        cash_received: Decimal,
        change_given: Decimal,
        sale_id: str,
    ) -> tuple[CashMovement, CashMovement | None]:
        """
        Record cash received from a sale and change given.

        Args:
            cash_received: Total cash tendered by customer
            change_given: Change returned to customer
            sale_id: Reference sale ID

        Returns:
            Tuple of (sale_movement, change_movement or None)
        """
        sale_movement = self.record_movement(
            movement_type=MovementType.SALE,
            amount=cash_received,
            reason="Cash sale",
            reference_id=sale_id,
        )

        change_movement = None
        if change_given > Decimal("0"):
            change_movement = self.record_movement(
                movement_type=MovementType.CHANGE,
                amount=change_given,
                reason="Change given",
                reference_id=sale_id,
            )

        return sale_movement, change_movement

    def close_drawer(
        self,
        *,
        closed_by: str,
        closing_count: Decimal,
    ) -> None:
        """
        Close the drawer session with counted cash.

        Args:
            closed_by: User ID who closed the drawer
            closing_count: Actual counted cash amount

        Raises:
            ValidationError: If already closed or invalid data
        """
        if self.status == DrawerStatus.CLOSED:
            raise ValidationError(
                "drawer is already closed",
                code="cash_drawer.already_closed",
            )
        if not closed_by:
            raise ValidationError(
                "closed_by user_id is required",
                code="cash_drawer.missing_user",
            )
        if closing_count < Decimal("0"):
            raise ValidationError(
                "closing count cannot be negative",
                code="cash_drawer.invalid_count",
            )

        self.closed_by = closed_by
        self.closing_count = Money(closing_count, self.opening_float.currency)
        self.over_short = self.closing_count.subtract(self.expected_balance)
        self.status = DrawerStatus.CLOSED
        self.closed_at = datetime.now(UTC)
        self._touch()

    def calculate_totals(self) -> dict[str, Decimal]:
        """
        Calculate movement totals by type.

        Returns:
            Dict with totals for each movement type
        """
        totals: dict[str, Decimal] = {
            "pay_in": Decimal("0"),
            "payout": Decimal("0"),
            "drop": Decimal("0"),
            "pickup": Decimal("0"),
            "sales": Decimal("0"),
            "change": Decimal("0"),
            "refunds": Decimal("0"),
        }

        for movement in self.movements:
            if movement.movement_type == MovementType.PAY_IN:
                totals["pay_in"] += movement.amount.amount
            elif movement.movement_type == MovementType.PAYOUT:
                totals["payout"] += movement.amount.amount
            elif movement.movement_type == MovementType.DROP:
                totals["drop"] += movement.amount.amount
            elif movement.movement_type == MovementType.PICKUP:
                totals["pickup"] += movement.amount.amount
            elif movement.movement_type in (MovementType.SALE, MovementType.CASH_IN):
                totals["sales"] += movement.amount.amount
            elif movement.movement_type == MovementType.CHANGE:
                totals["change"] += movement.amount.amount
            elif movement.movement_type == MovementType.REFUND:
                totals["refunds"] += movement.amount.amount

        return totals

    @property
    def is_open(self) -> bool:
        """Check if drawer is currently open."""
        return self.status == DrawerStatus.OPEN

    @property
    def net_cash_from_sales(self) -> Money:
        """Calculate net cash from sales (sales - change - refunds)."""
        totals = self.calculate_totals()
        net = totals["sales"] - totals["change"] - totals["refunds"]
        return Money(net, self.opening_float.currency)

    def _touch(self) -> None:
        """Increment version for optimistic locking."""
        self.version += 1
