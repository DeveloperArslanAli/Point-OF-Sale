"""Unit tests for Prometheus metrics module."""

from __future__ import annotations

import pytest

from app.infrastructure.observability.metrics import (
    record_cash_drawer_operation,
    record_celery_task,
    record_gift_card_issued,
    record_gift_card_redeemed,
    record_inventory_movement,
    record_login,
    record_return,
    record_sale,
    record_stock_alert,
    set_active_sessions,
    set_active_shifts,
    set_celery_queue_depth,
    set_db_connections,
    set_websocket_connections,
)


class TestSalesMetrics:
    """Tests for sales metrics recording."""

    def test_record_sale_increments_counters(self) -> None:
        """Should increment sales counters without error."""
        # Should not raise
        record_sale(
            payment_method="cash",
            status="completed",
            amount_cents=1000,
            currency="USD",
            item_count=2,
            category="electronics",
        )

    def test_record_sale_different_methods(self) -> None:
        """Should handle different payment methods."""
        record_sale("cash", "completed", 500)
        record_sale("card", "completed", 1500)
        record_sale("gift_card", "completed", 750)


class TestInventoryMetrics:
    """Tests for inventory metrics recording."""

    def test_record_inventory_in(self) -> None:
        """Should record inventory in movement."""
        record_inventory_movement("in", "purchase")

    def test_record_inventory_out(self) -> None:
        """Should record inventory out movement."""
        record_inventory_movement("out", "sale")

    def test_record_stock_alert(self) -> None:
        """Should record stock alerts."""
        record_stock_alert("low_stock")
        record_stock_alert("out_of_stock")
        record_stock_alert("reorder_point")


class TestReturnMetrics:
    """Tests for return metrics recording."""

    def test_record_return(self) -> None:
        """Should record return with reason."""
        record_return("defective")
        record_return("wrong_item")


class TestGiftCardMetrics:
    """Tests for gift card metrics recording."""

    def test_record_gift_card_issued(self) -> None:
        """Should increment gift card issued counter."""
        record_gift_card_issued()

    def test_record_gift_card_redeemed(self) -> None:
        """Should increment gift card redeemed counter."""
        record_gift_card_redeemed()


class TestUserMetrics:
    """Tests for user activity metrics recording."""

    def test_record_login_success(self) -> None:
        """Should record successful login."""
        record_login("cashier", success=True)

    def test_record_login_failed(self) -> None:
        """Should record failed login."""
        record_login("admin", success=False)

    def test_set_active_sessions(self) -> None:
        """Should set active sessions gauge."""
        set_active_sessions(10)
        set_active_sessions(5)

    def test_set_active_shifts(self) -> None:
        """Should set active shifts gauge."""
        set_active_shifts(3)


class TestCashDrawerMetrics:
    """Tests for cash drawer metrics recording."""

    def test_record_cash_drawer_operations(self) -> None:
        """Should record cash drawer operations."""
        record_cash_drawer_operation("open")
        record_cash_drawer_operation("close")
        record_cash_drawer_operation("adjustment")


class TestSystemMetrics:
    """Tests for system metrics recording."""

    def test_set_db_connections(self) -> None:
        """Should set DB connections gauge."""
        set_db_connections(25)

    def test_set_websocket_connections(self) -> None:
        """Should set WebSocket connections gauge."""
        set_websocket_connections(10)

    def test_record_celery_task(self) -> None:
        """Should record Celery task events."""
        record_celery_task("process_import", "started")
        record_celery_task("process_import", "success")
        record_celery_task("send_email", "failed")

    def test_set_celery_queue_depth(self) -> None:
        """Should set queue depth gauge."""
        set_celery_queue_depth("default", 5)
        set_celery_queue_depth("imports", 10)
