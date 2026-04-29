"""Gift card use cases."""
from __future__ import annotations

from datetime import datetime, timezone

import structlog

from app.application.gift_cards.ports import IGiftCardRepository
from app.domain.common.money import Money
from app.domain.gift_cards.entities import GiftCard

logger = structlog.get_logger(__name__)


class PurchaseGiftCard:
    """Purchase a new gift card."""

    def __init__(self, gift_card_repository: IGiftCardRepository) -> None:
        self._gift_card_repository = gift_card_repository

    async def execute(
        self,
        amount: Money,
        customer_id: str | None = None,
        validity_days: int = 365,
    ) -> GiftCard:
        """
        Purchase a new gift card.
        
        Args:
            amount: Initial balance for the gift card
            customer_id: Optional customer who purchased the card
            validity_days: Number of days until expiry (default: 365)
            
        Returns:
            Newly created gift card in PENDING status
            
        Raises:
            ValidationError: If amount is invalid
        """
        logger.info(
            "purchase_gift_card",
            amount=amount.amount,
            currency=amount.currency,
            customer_id=customer_id,
            validity_days=validity_days,
        )

        # Create the gift card
        gift_card = GiftCard.purchase(
            amount=amount.amount,
            currency=amount.currency,
            customer_id=customer_id,
            validity_days=validity_days,
        )

        # Save to repository
        await self._gift_card_repository.add(gift_card)

        logger.info(
            "gift_card_purchased",
            gift_card_id=gift_card.id,
            code=gift_card.code,
            amount=gift_card.initial_balance.amount,
        )

        return gift_card


class ActivateGiftCard:
    """Activate a purchased gift card."""

    def __init__(self, gift_card_repository: IGiftCardRepository) -> None:
        self._gift_card_repository = gift_card_repository

    async def execute(self, code: str) -> GiftCard:
        """
        Activate a gift card by its code.
        
        Args:
            code: Gift card redemption code
            
        Returns:
            Activated gift card
            
        Raises:
            ValueError: If gift card not found
            ValidationError: If gift card cannot be activated
        """
        logger.info("activate_gift_card", code=code)

        # Get gift card
        gift_card = await self._gift_card_repository.get_by_code(code)
        if not gift_card:
            msg = f"Gift card with code {code} not found"
            raise ValueError(msg)

        # Activate
        gift_card.activate()

        # Update repository
        await self._gift_card_repository.update(gift_card)

        logger.info(
            "gift_card_activated",
            gift_card_id=gift_card.id,
            code=gift_card.code,
        )

        return gift_card


class RedeemGiftCard:
    """Redeem value from a gift card."""

    def __init__(self, gift_card_repository: IGiftCardRepository) -> None:
        self._gift_card_repository = gift_card_repository

    async def execute(self, code: str, amount: Money) -> GiftCard:
        """
        Redeem an amount from a gift card.
        
        Args:
            code: Gift card redemption code
            amount: Amount to redeem
            
        Returns:
            Updated gift card with reduced balance
            
        Raises:
            ValueError: If gift card not found
            ValidationError: If gift card cannot be redeemed or insufficient balance
        """
        logger.info(
            "redeem_gift_card",
            code=code,
            amount=amount.amount,
            currency=amount.currency,
        )

        # Get gift card
        gift_card = await self._gift_card_repository.get_by_code(code)
        if not gift_card:
            msg = f"Gift card with code {code} not found"
            raise ValueError(msg)

        # Redeem
        gift_card.redeem(amount.amount)

        # Update repository
        await self._gift_card_repository.update(gift_card)

        logger.info(
            "gift_card_redeemed",
            gift_card_id=gift_card.id,
            code=gift_card.code,
            redeemed_amount=amount.amount,
            remaining_balance=gift_card.current_balance.amount,
            status=gift_card.status.value,
        )

        return gift_card


class CheckGiftCardBalance:
    """Check the balance of a gift card."""

    def __init__(self, gift_card_repository: IGiftCardRepository) -> None:
        self._gift_card_repository = gift_card_repository

    async def execute(self, code: str) -> tuple[Money, bool]:
        """
        Check gift card balance and usability.
        
        Args:
            code: Gift card redemption code
            
        Returns:
            Tuple of (current_balance, is_usable)
            
        Raises:
            ValueError: If gift card not found
        """
        logger.info("check_gift_card_balance", code=code)

        # Get gift card
        gift_card = await self._gift_card_repository.get_by_code(code)
        if not gift_card:
            msg = f"Gift card with code {code} not found"
            raise ValueError(msg)

        # Check balance (this auto-expires if needed)
        balance = gift_card.check_balance()
        is_usable = gift_card.is_usable()

        # If status changed due to expiry, update repository
        if gift_card.status.value == "expired":
            await self._gift_card_repository.update(gift_card)

        logger.info(
            "gift_card_balance_checked",
            gift_card_id=gift_card.id,
            code=gift_card.code,
            balance=balance.amount,
            status=gift_card.status.value,
            is_usable=is_usable,
        )

        return balance, is_usable


class ListCustomerGiftCards:
    """List gift cards for a customer."""

    def __init__(self, gift_card_repository: IGiftCardRepository) -> None:
        self._gift_card_repository = gift_card_repository

    async def execute(
        self,
        customer_id: str,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[GiftCard], int]:
        """
        List gift cards for a customer.
        
        Args:
            customer_id: Customer ID
            page: Page number (1-indexed)
            limit: Items per page
            
        Returns:
            Tuple of (gift_cards, total_count)
        """
        logger.info(
            "list_customer_gift_cards",
            customer_id=customer_id,
            page=page,
            limit=limit,
        )

        gift_cards, total = await self._gift_card_repository.list_by_customer(
            customer_id,
            page=page,
            limit=limit,
        )

        logger.info(
            "customer_gift_cards_listed",
            customer_id=customer_id,
            count=len(gift_cards),
            total=total,
        )

        return gift_cards, total
