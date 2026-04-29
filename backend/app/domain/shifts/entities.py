"""Shift domain entity."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum

from app.domain.common.errors import ValidationError
from app.domain.common.identifiers import new_ulid
from app.domain.common.money import Money


class ShiftStatus(str, Enum):
    """Shift status."""

    ACTIVE = "active"
    CLOSED = "closed"


@dataclass(slots=True)
class Shift:
    """
    Shift aggregate root.

    Represents a cashier's work session, tracking all sales and
    payments made during the shift.
    """

    id: str
    user_id: str
    terminal_id: str
    drawer_session_id: str | None = None
    status: ShiftStatus = ShiftStatus.ACTIVE
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    ended_at: datetime | None = None
    opening_cash: Money | None = None
    closing_cash: Money | None = None
    # Running totals
    total_sales: Money = field(default_factory=lambda: Money(Decimal("0"), "USD"))
    total_transactions: int = 0
    cash_sales: Money = field(default_factory=lambda: Money(Decimal("0"), "USD"))
    card_sales: Money = field(default_factory=lambda: Money(Decimal("0"), "USD"))
    gift_card_sales: Money = field(default_factory=lambda: Money(Decimal("0"), "USD"))
    other_sales: Money = field(default_factory=lambda: Money(Decimal("0"), "USD"))
    total_refunds: Money = field(default_factory=lambda: Money(Decimal("0"), "USD"))
    refund_count: int = 0
    version: int = 0

    @staticmethod
    def start(
        *,
        user_id: str,
        terminal_id: str,
        drawer_session_id: str | None = None,
        opening_cash: Decimal | None = None,
        currency: str = "USD",
    ) -> Shift:
        """
        Start a new shift.

        Args:
            user_id: Cashier/user starting the shift
            terminal_id: POS terminal ID
            drawer_session_id: Optional linked cash drawer session
            opening_cash: Starting cash amount
            currency: Currency for totals

        Returns:
            New active Shift
        """
        if not user_id:
            raise ValidationError(
                "user_id is required",
                code="shift.missing_user",
            )
        if not terminal_id:
            raise ValidationError(
                "terminal_id is required",
                code="shift.missing_terminal",
            )

        return Shift(
            id=new_ulid(),
            user_id=user_id,
            terminal_id=terminal_id,
            drawer_session_id=drawer_session_id,
            opening_cash=Money(opening_cash, currency) if opening_cash is not None else None,
            total_sales=Money(Decimal("0"), currency),
            cash_sales=Money(Decimal("0"), currency),
            card_sales=Money(Decimal("0"), currency),
            gift_card_sales=Money(Decimal("0"), currency),
            other_sales=Money(Decimal("0"), currency),
            total_refunds=Money(Decimal("0"), currency),
        )

    def record_sale(
        self,
        *,
        sale_total: Decimal,
        cash_amount: Decimal = Decimal("0"),
        card_amount: Decimal = Decimal("0"),
        gift_card_amount: Decimal = Decimal("0"),
        other_amount: Decimal = Decimal("0"),
    ) -> None:
        """
        Record a sale's payment breakdown to shift totals.

        Args:
            sale_total: Total sale amount
            cash_amount: Amount paid in cash
            card_amount: Amount paid by card
            gift_card_amount: Amount paid by gift card
            other_amount: Amount paid by other methods
        """
        if self.status == ShiftStatus.CLOSED:
            raise ValidationError(
                "cannot record sale on closed shift",
                code="shift.already_closed",
            )

        currency = self.total_sales.currency
        self.total_sales = self.total_sales.add(Money(sale_total, currency))
        self.total_transactions += 1

        if cash_amount > Decimal("0"):
            self.cash_sales = self.cash_sales.add(Money(cash_amount, currency))
        if card_amount > Decimal("0"):
            self.card_sales = self.card_sales.add(Money(card_amount, currency))
        if gift_card_amount > Decimal("0"):
            self.gift_card_sales = self.gift_card_sales.add(Money(gift_card_amount, currency))
        if other_amount > Decimal("0"):
            self.other_sales = self.other_sales.add(Money(other_amount, currency))

        self._touch()

    def record_refund(self, *, refund_amount: Decimal) -> None:
        """
        Record a refund against the shift.

        Args:
            refund_amount: Amount refunded
        """
        if self.status == ShiftStatus.CLOSED:
            raise ValidationError(
                "cannot record refund on closed shift",
                code="shift.already_closed",
            )

        currency = self.total_refunds.currency
        self.total_refunds = self.total_refunds.add(Money(refund_amount, currency))
        self.refund_count += 1
        self._touch()

    def end_shift(self, *, closing_cash: Decimal | None = None) -> None:
        """
        End the shift.

        Args:
            closing_cash: Closing cash amount to record

        Raises:
            ValidationError: If shift is already closed
        """
        if self.status == ShiftStatus.CLOSED:
            raise ValidationError(
                "shift is already closed",
                code="shift.already_closed",
            )

        currency = self.total_sales.currency
        if closing_cash is not None:
            self.closing_cash = Money(closing_cash, currency)

        self.status = ShiftStatus.CLOSED
        self.ended_at = datetime.now(UTC)
        self._touch()

    def link_drawer(self, drawer_session_id: str) -> None:
        """Link a cash drawer session to this shift."""
        if self.status == ShiftStatus.CLOSED:
            raise ValidationError(
                "cannot link drawer to closed shift",
                code="shift.already_closed",
            )
        self.drawer_session_id = drawer_session_id
        self._touch()

    @property
    def is_active(self) -> bool:
        """Check if shift is currently active."""
        return self.status == ShiftStatus.ACTIVE

    @property
    def net_sales(self) -> Money:
        """Calculate net sales (total sales - refunds)."""
        return self.total_sales.subtract(self.total_refunds)

    @property
    def duration_minutes(self) -> int | None:
        """Calculate shift duration in minutes."""
        end = self.ended_at or datetime.now(UTC)
        delta = end - self.started_at
        return int(delta.total_seconds() / 60)

    def _touch(self) -> None:
        """Increment version for optimistic locking."""
        self.version += 1
