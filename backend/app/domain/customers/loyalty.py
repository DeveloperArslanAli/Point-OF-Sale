"""Customer loyalty program domain entities."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from app.domain.common.errors import ConflictError, ValidationError
from app.domain.common.identifiers import new_ulid

if TYPE_CHECKING:
    from app.domain.customers import Customer


class LoyaltyTier(str, Enum):
    """Customer loyalty tiers based on points."""

    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"

    @classmethod
    def from_points(cls, points: int) -> LoyaltyTier:
        """Determine tier based on total points earned."""
        if points >= 10000:
            return cls.PLATINUM
        elif points >= 5000:
            return cls.GOLD
        elif points >= 1000:
            return cls.SILVER
        return cls.BRONZE

    @property
    def point_multiplier(self) -> Decimal:
        """Points multiplier for purchases based on tier."""
        multipliers = {
            LoyaltyTier.BRONZE: Decimal("1.0"),
            LoyaltyTier.SILVER: Decimal("1.25"),
            LoyaltyTier.GOLD: Decimal("1.5"),
            LoyaltyTier.PLATINUM: Decimal("2.0"),
        }
        return multipliers[self]

    @property
    def discount_percentage(self) -> Decimal:
        """Discount percentage for tier members."""
        discounts = {
            LoyaltyTier.BRONZE: Decimal("0"),
            LoyaltyTier.SILVER: Decimal("5"),
            LoyaltyTier.GOLD: Decimal("10"),
            LoyaltyTier.PLATINUM: Decimal("15"),
        }
        return discounts[self]


class PointTransactionType(str, Enum):
    """Types of loyalty point transactions."""

    EARN = "earn"  # Points earned from purchase
    REDEEM = "redeem"  # Points redeemed for discount
    BONUS = "bonus"  # Bonus points from promotions
    EXPIRE = "expire"  # Points that expired
    ADJUST = "adjust"  # Manual adjustment by admin
    REFUND = "refund"  # Points returned from refund


@dataclass(slots=True)
class LoyaltyPointTransaction:
    """Record of a loyalty points transaction."""

    id: str
    loyalty_account_id: str
    transaction_type: PointTransactionType
    points: int  # Positive for earn/bonus, negative for redeem/expire
    balance_after: int
    reference_id: str | None  # Sale ID, promotion ID, etc.
    description: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @staticmethod
    def create(
        *,
        loyalty_account_id: str,
        transaction_type: PointTransactionType,
        points: int,
        balance_after: int,
        reference_id: str | None = None,
        description: str = "",
    ) -> LoyaltyPointTransaction:
        """Create a new point transaction record."""
        return LoyaltyPointTransaction(
            id=new_ulid(),
            loyalty_account_id=loyalty_account_id,
            transaction_type=transaction_type,
            points=points,
            balance_after=balance_after,
            reference_id=reference_id,
            description=description,
        )


@dataclass(slots=True)
class LoyaltyAccount:
    """Customer loyalty account tracking points and tier."""

    id: str
    customer_id: str
    current_points: int = 0
    lifetime_points: int = 0  # Total points ever earned (for tier calculation)
    tier: LoyaltyTier = LoyaltyTier.BRONZE
    enrolled_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    version: int = 0

    # Points configuration (could be configurable per tenant)
    POINTS_PER_DOLLAR: int = 1  # 1 point per dollar spent
    POINTS_FOR_REDEMPTION_DOLLAR: int = 100  # 100 points = $1 discount
    MIN_REDEMPTION_POINTS: int = 100  # Minimum points to redeem

    @staticmethod
    def enroll(*, customer_id: str) -> LoyaltyAccount:
        """Enroll a customer in the loyalty program."""
        if not customer_id:
            raise ValidationError(
                "customer_id is required", code="loyalty.invalid_customer_id"
            )
        return LoyaltyAccount(
            id=new_ulid(),
            customer_id=customer_id,
        )

    def earn_points(
        self,
        *,
        amount: Decimal,
        reference_id: str | None = None,
        description: str = "",
    ) -> LoyaltyPointTransaction:
        """Earn points from a purchase."""
        if amount <= 0:
            raise ValidationError(
                "Amount must be positive to earn points",
                code="loyalty.invalid_amount",
            )

        # Calculate points with tier multiplier
        base_points = int(amount * self.POINTS_PER_DOLLAR)
        multiplied_points = int(Decimal(base_points) * self.tier.point_multiplier)
        points_earned = max(multiplied_points, 1)  # At least 1 point

        self.current_points += points_earned
        self.lifetime_points += points_earned
        self._update_tier()
        self._touch()

        return LoyaltyPointTransaction.create(
            loyalty_account_id=self.id,
            transaction_type=PointTransactionType.EARN,
            points=points_earned,
            balance_after=self.current_points,
            reference_id=reference_id,
            description=description or f"Earned {points_earned} points from purchase",
        )

    def redeem_points(
        self,
        *,
        points: int,
        reference_id: str | None = None,
        description: str = "",
    ) -> LoyaltyPointTransaction:
        """Redeem points for a discount."""
        if points <= 0:
            raise ValidationError(
                "Points must be positive to redeem", code="loyalty.invalid_points"
            )
        if points < self.MIN_REDEMPTION_POINTS:
            raise ValidationError(
                f"Minimum {self.MIN_REDEMPTION_POINTS} points required for redemption",
                code="loyalty.min_redemption_not_met",
            )
        if points > self.current_points:
            raise ConflictError(
                f"Insufficient points: have {self.current_points}, need {points}",
                code="loyalty.insufficient_points",
            )

        self.current_points -= points
        self._touch()

        return LoyaltyPointTransaction.create(
            loyalty_account_id=self.id,
            transaction_type=PointTransactionType.REDEEM,
            points=-points,
            balance_after=self.current_points,
            reference_id=reference_id,
            description=description or f"Redeemed {points} points",
        )

    def add_bonus_points(
        self,
        *,
        points: int,
        reference_id: str | None = None,
        description: str = "",
    ) -> LoyaltyPointTransaction:
        """Add bonus points from promotions or special events."""
        if points <= 0:
            raise ValidationError(
                "Bonus points must be positive", code="loyalty.invalid_points"
            )

        self.current_points += points
        self.lifetime_points += points
        self._update_tier()
        self._touch()

        return LoyaltyPointTransaction.create(
            loyalty_account_id=self.id,
            transaction_type=PointTransactionType.BONUS,
            points=points,
            balance_after=self.current_points,
            reference_id=reference_id,
            description=description or f"Bonus {points} points",
        )

    def refund_points(
        self,
        *,
        points: int,
        reference_id: str | None = None,
        description: str = "",
    ) -> LoyaltyPointTransaction:
        """Deduct points when a purchase is refunded."""
        if points <= 0:
            raise ValidationError(
                "Refund points must be positive", code="loyalty.invalid_points"
            )

        # Don't go negative, cap at 0
        actual_deduction = min(points, self.current_points)
        self.current_points -= actual_deduction
        # Lifetime points don't decrease on refund
        self._touch()

        return LoyaltyPointTransaction.create(
            loyalty_account_id=self.id,
            transaction_type=PointTransactionType.REFUND,
            points=-actual_deduction,
            balance_after=self.current_points,
            reference_id=reference_id,
            description=description or f"Refunded {actual_deduction} points",
        )

    def adjust_points(
        self,
        *,
        points: int,
        description: str,
    ) -> LoyaltyPointTransaction:
        """Manually adjust points (admin action)."""
        if not description:
            raise ValidationError(
                "Description required for manual adjustment",
                code="loyalty.description_required",
            )

        new_balance = self.current_points + points
        if new_balance < 0:
            raise ValidationError(
                f"Adjustment would result in negative balance: {new_balance}",
                code="loyalty.negative_balance",
            )

        self.current_points = new_balance
        if points > 0:
            self.lifetime_points += points
        self._update_tier()
        self._touch()

        return LoyaltyPointTransaction.create(
            loyalty_account_id=self.id,
            transaction_type=PointTransactionType.ADJUST,
            points=points,
            balance_after=self.current_points,
            description=description,
        )

    def calculate_redemption_value(self, points: int) -> Decimal:
        """Calculate the dollar value of points for redemption."""
        if points <= 0:
            return Decimal("0")
        return Decimal(points) / Decimal(self.POINTS_FOR_REDEMPTION_DOLLAR)

    def points_needed_for_next_tier(self) -> int | None:
        """Calculate points needed to reach the next tier."""
        tier_thresholds = {
            LoyaltyTier.BRONZE: 1000,  # Points to reach Silver
            LoyaltyTier.SILVER: 5000,  # Points to reach Gold
            LoyaltyTier.GOLD: 10000,  # Points to reach Platinum
            LoyaltyTier.PLATINUM: None,  # Already at max
        }
        threshold = tier_thresholds[self.tier]
        if threshold is None:
            return None
        return max(0, threshold - self.lifetime_points)

    def _update_tier(self) -> None:
        """Update tier based on lifetime points."""
        new_tier = LoyaltyTier.from_points(self.lifetime_points)
        if new_tier != self.tier:
            self.tier = new_tier

    def _touch(self) -> None:
        """Update timestamp and version."""
        self.updated_at = datetime.now(UTC)
        self.version += 1
