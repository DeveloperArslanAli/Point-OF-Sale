"""Offline sync domain entities."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from app.domain.common.identifiers import new_ulid


class OfflineActionType(str, Enum):
    """Types of offline actions that can be queued."""

    SALE = "sale"
    REFUND = "refund"
    SHIFT_START = "shift_start"
    SHIFT_END = "shift_end"
    DRAWER_OPEN = "drawer_open"
    DRAWER_CLOSE = "drawer_close"
    DRAWER_MOVEMENT = "drawer_movement"
    INVENTORY_ADJUSTMENT = "inventory_adjustment"


class OfflineItemStatus(str, Enum):
    """Status of an offline queue item."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"  # Duplicate idempotency key


@dataclass(slots=True)
class OfflineQueueItem:
    """
    Represents a single offline action queued for replay.

    Used when POS terminals lose connectivity and need to sync
    operations when back online.
    """

    id: str
    idempotency_key: str
    action_type: OfflineActionType | str  # Can be str for unknown types
    terminal_id: str
    user_id: str
    payload: dict[str, Any]
    status: OfflineItemStatus = OfflineItemStatus.PENDING
    error_message: str | None = None
    created_offline_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    processed_at: datetime | None = None
    retry_count: int = 0
    max_retries: int = 3

    @staticmethod
    def create(
        *,
        idempotency_key: str,
        action_type: OfflineActionType | str,
        terminal_id: str,
        user_id: str,
        payload: dict[str, Any],
        created_offline_at: datetime | None = None,
    ) -> OfflineQueueItem:
        """
        Create a new offline queue item.

        Args:
            idempotency_key: Unique key to prevent duplicate processing
            action_type: Type of action to replay
            terminal_id: Source terminal
            user_id: User who performed action
            payload: Action-specific data
            created_offline_at: When action was performed offline

        Returns:
            New OfflineQueueItem
        """
        if isinstance(action_type, str):
            try:
                action_type = OfflineActionType(action_type)
            except ValueError:
                # Invalid action type - will be caught during processing
                pass

        return OfflineQueueItem(
            id=new_ulid(),
            idempotency_key=idempotency_key,
            action_type=action_type,
            terminal_id=terminal_id,
            user_id=user_id,
            payload=payload,
            created_offline_at=created_offline_at or datetime.now(UTC),
        )

    def mark_processing(self) -> None:
        """Mark item as currently being processed."""
        self.status = OfflineItemStatus.PROCESSING

    def mark_completed(self) -> None:
        """Mark item as successfully processed."""
        self.status = OfflineItemStatus.COMPLETED
        self.processed_at = datetime.now(UTC)

    def mark_failed(self, error: str, allow_retry: bool = False) -> None:
        """Mark item as failed with error message.
        
        Args:
            error: Error message describing the failure
            allow_retry: If True, use retry logic; if False, mark as failed immediately
        """
        self.error_message = error
        if allow_retry:
            self.retry_count += 1
            if self.retry_count >= self.max_retries:
                self.status = OfflineItemStatus.FAILED
            else:
                self.status = OfflineItemStatus.PENDING
        else:
            # No retry - immediately failed
            self.status = OfflineItemStatus.FAILED
            self.processed_at = datetime.now(UTC)

    def mark_skipped(self, reason: str = "Duplicate idempotency key") -> None:
        """Mark item as skipped (e.g., duplicate)."""
        self.status = OfflineItemStatus.SKIPPED
        self.error_message = reason
        self.processed_at = datetime.now(UTC)

    @property
    def can_retry(self) -> bool:
        """Check if item can be retried."""
        return self.retry_count < self.max_retries and self.status != OfflineItemStatus.COMPLETED


@dataclass(slots=True)
class OfflineSyncBatch:
    """
    Batch of offline items to be processed together.

    Tracks overall sync session progress.
    """

    id: str
    terminal_id: str
    user_id: str
    items: list[OfflineQueueItem] = field(default_factory=list)
    total_items: int = 0
    completed_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    @staticmethod
    def create(
        *,
        terminal_id: str,
        user_id: str,
        items: list[OfflineQueueItem],
    ) -> OfflineSyncBatch:
        """Create a new sync batch."""
        return OfflineSyncBatch(
            id=new_ulid(),
            terminal_id=terminal_id,
            user_id=user_id,
            items=items,
            total_items=len(items),
        )

    def record_completion(self, item: OfflineQueueItem) -> None:
        """Record item completion status."""
        if item.status == OfflineItemStatus.COMPLETED:
            self.completed_count += 1
        elif item.status == OfflineItemStatus.FAILED:
            self.failed_count += 1
        elif item.status == OfflineItemStatus.SKIPPED:
            self.skipped_count += 1

    def finalize(self) -> None:
        """Mark batch as complete."""
        self.completed_at = datetime.now(UTC)

    @property
    def is_complete(self) -> bool:
        """Check if all items have been processed."""
        processed = self.completed_count + self.failed_count + self.skipped_count
        return processed >= self.total_items

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_items == 0:
            return 100.0
        return (self.completed_count / self.total_items) * 100
