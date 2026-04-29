"""
Phase 12 End-to-End Integration Tests.

Tests the complete POS workflow combining:
- Cash drawer management
- Shift management  
- Product catalog
- Inventory movements
- Sales with split payments
- Gift card purchase, activate, and redemption as payment
- Promotions/discounts
- Receipt generation
- Reconciliation

This validates all Phase 12 components working together.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.domain.auth.entities import UserRole
from tests.integration.api.helpers import login_as


@pytest.mark.asyncio
async def test_full_pos_workflow_e2e(async_session):
    """
    Complete end-to-end test of the POS workflow:
    1. Manager sets up products and inventory
    2. Cashier opens drawer and starts shift
    3. Cashier sells items with split payments (cash + card)
    4. Receipt is generated
    5. Customer buys gift card
    6. Another sale paid with gift card + cash
    7. Cashier ends shift with reconciliation
    8. Drawer closes with over/short calculation
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Setup: Get tokens for manager and cashier
        manager_token = await login_as(
            async_session, client, UserRole.MANAGER, email_prefix="e2e_manager"
        )
        cashier_token = await login_as(
            async_session, client, UserRole.CASHIER, email_prefix="e2e_cashier"
        )
        terminal_id = f"TERM-E2E-{uuid.uuid4().hex[:6]}"

        # ==================== STEP 1: Manager creates products ====================
        
        product1_resp = await client.post(
            "/api/v1/products",
            json={
                "name": "E2E Widget A",
                "sku": f"E2E-A-{uuid.uuid4().hex[:6]}",
                "retail_price": "25.00",
                "purchase_price": "12.00",
            },
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert product1_resp.status_code == 201, product1_resp.text
        product1_id = product1_resp.json()["id"]

        product2_resp = await client.post(
            "/api/v1/products",
            json={
                "name": "E2E Widget B",
                "sku": f"E2E-B-{uuid.uuid4().hex[:6]}",
                "retail_price": "15.00",
                "purchase_price": "7.50",
            },
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert product2_resp.status_code == 201, product2_resp.text
        product2_id = product2_resp.json()["id"]

        # Stock inventory
        for pid in [product1_id, product2_id]:
            stock_resp = await client.post(
                f"/api/v1/products/{pid}/inventory/movements",
                json={"quantity": 50, "direction": "in", "reason": "initial_stock"},
                headers={"Authorization": f"Bearer {manager_token}"},
            )
            assert stock_resp.status_code == 201

        # ==================== STEP 2: Cashier opens drawer and starts shift ====================
        
        drawer_resp = await client.post(
            "/api/v1/cash-drawer/open",
            json={"terminal_id": terminal_id, "opening_amount": "200.00"},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert drawer_resp.status_code == 201, drawer_resp.text
        drawer_id = drawer_resp.json()["id"]
        assert drawer_resp.json()["status"] == "open"

        shift_resp = await client.post(
            "/api/v1/shifts/start",
            json={
                "terminal_id": terminal_id,
                "opening_cash": "200.00",
                "drawer_session_id": drawer_id,
            },
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert shift_resp.status_code == 201, shift_resp.text
        shift_id = shift_resp.json()["id"]
        assert shift_resp.json()["status"] == "active"

        # ==================== STEP 3: First sale with split payments ====================
        
        # Sale: 2x Widget A ($50) + 1x Widget B ($15) = $65 total
        # Payment: $40 cash + $25 card
        sale1_resp = await client.post(
            "/api/v1/sales",
            json={
                "currency": "USD",
                "lines": [
                    {"product_id": product1_id, "quantity": 2, "unit_price": "25.00"},
                    {"product_id": product2_id, "quantity": 1, "unit_price": "15.00"},
                ],
                "payments": [
                    {"payment_method": "cash", "amount": "40.00"},
                    {"payment_method": "card", "amount": "25.00"},
                ],
                "shift_id": shift_id,
            },
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert sale1_resp.status_code == 201, sale1_resp.text
        sale1 = sale1_resp.json()["sale"]
        assert Decimal(sale1["total_amount"]) == Decimal("65.00")
        assert len(sale1["payments"]) == 2
        sale1_id = sale1["id"]

        # ==================== STEP 4: Generate receipt for first sale ====================
        
        receipt1_resp = await client.post(
            "/api/v1/receipts",
            json={"sale_id": sale1_id},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert receipt1_resp.status_code == 201, receipt1_resp.text
        receipt1 = receipt1_resp.json()
        assert receipt1["sale_id"] == sale1_id
        assert len(receipt1["line_items"]) == 2
        receipt1_id = receipt1["id"]

        # Verify receipt retrieval
        get_receipt = await client.get(
            f"/api/v1/receipts/{receipt1_id}",
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert get_receipt.status_code == 200

        # ==================== STEP 5: Customer purchases gift card ====================
        
        gc_purchase = await client.post(
            "/api/v1/gift-cards/purchase",
            json={"amount": "50.00", "currency": "USD", "validity_days": 365},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert gc_purchase.status_code == 201, gc_purchase.text
        gc_code = gc_purchase.json()["code"]
        assert gc_code.startswith("GC-")

        # Activate gift card
        gc_activate = await client.post(
            "/api/v1/gift-cards/activate",
            json={"code": gc_code},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert gc_activate.status_code == 200, gc_activate.text
        assert gc_activate.json()["status"] == "active"

        # Check balance
        gc_balance = await client.get(
            f"/api/v1/gift-cards/{gc_code}/balance",
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert gc_balance.status_code == 200
        assert Decimal(gc_balance.json()["current_balance"]) == Decimal("50.00")

        # ==================== STEP 6: Second sale with gift card payment ====================
        
        # Sale: 1x Widget A ($25) + 1x Widget B ($15) = $40 total
        # Payment: $30 gift card + $10 cash
        sale2_resp = await client.post(
            "/api/v1/sales",
            json={
                "currency": "USD",
                "lines": [
                    {"product_id": product1_id, "quantity": 1, "unit_price": "25.00"},
                    {"product_id": product2_id, "quantity": 1, "unit_price": "15.00"},
                ],
                "payments": [
                    {"payment_method": "gift_card", "amount": "30.00", "gift_card_code": gc_code},
                    {"payment_method": "cash", "amount": "10.00"},
                ],
                "shift_id": shift_id,
            },
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert sale2_resp.status_code == 201, sale2_resp.text
        sale2 = sale2_resp.json()["sale"]
        assert Decimal(sale2["total_amount"]) == Decimal("40.00")
        assert len(sale2["payments"]) == 2

        # Verify gift card balance decreased
        gc_balance2 = await client.get(
            f"/api/v1/gift-cards/{gc_code}/balance",
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert gc_balance2.status_code == 200
        assert Decimal(gc_balance2.json()["current_balance"]) == Decimal("20.00")  # 50 - 30

        # ==================== STEP 7: End shift and verify totals ====================
        
        shift_end_resp = await client.post(
            "/api/v1/shifts/end",
            json={"shift_id": shift_id, "closing_cash": "250.00"},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert shift_end_resp.status_code == 200, shift_end_resp.text
        ended_shift = shift_end_resp.json()
        assert ended_shift["status"] == "closed"
        
        # Verify shift totals reflect both sales
        # Total sales: $65 + $40 = $105
        assert Decimal(ended_shift["total_sales"]) == Decimal("105.00")
        # Cash sales: $40 (sale1) + $10 (sale2) = $50
        assert Decimal(ended_shift["cash_sales"]) == Decimal("50.00")
        # Card sales: $25 (sale1)
        assert Decimal(ended_shift["card_sales"]) == Decimal("25.00")
        # Gift card sales: $30 (sale2)
        assert Decimal(ended_shift["gift_card_sales"]) == Decimal("30.00")
        # Transaction count: 2
        assert ended_shift["total_transactions"] == 2

        # ==================== STEP 8: Close drawer with reconciliation ====================
        
        # Expected cash: $200 opening + $50 cash from sales = $250
        # Actual count: $250 (no over/short)
        drawer_close = await client.post(
            "/api/v1/cash-drawer/close",
            json={"session_id": drawer_id, "closing_amount": "250.00"},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert drawer_close.status_code == 200, drawer_close.text
        closed_drawer = drawer_close.json()
        assert closed_drawer["status"] == "closed"
        
        # Verify drawer movements include sale cash
        movements = closed_drawer.get("movements", [])
        sale_movements = [m for m in movements if m["movement_type"] == "sale"]
        total_sale_cash = sum(Decimal(m["amount"]) for m in sale_movements)
        assert total_sale_cash == Decimal("50.00")  # $40 + $10 from cash portions

        # Verify over/short calculation
        # Expected: $200 + $50 sales = $250
        # Counted: $250
        # Over/Short: $0
        assert closed_drawer.get("over_short") is not None
        assert Decimal(closed_drawer["over_short"]) == Decimal("0.00")


@pytest.mark.asyncio
async def test_sale_with_promotion_discount_e2e(async_session):
    """
    End-to-end test with promotion discount applied:
    1. Create promotion (10% off)
    2. Create product and stock
    3. Apply promotion to calculate discount
    4. Record sale with discounted price
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_token = await login_as(
            async_session, client, UserRole.ADMIN, email_prefix="e2e_promo_admin"
        )
        cashier_token = await login_as(
            async_session, client, UserRole.CASHIER, email_prefix="e2e_promo_cashier"
        )
        
        # Create promotion
        coupon_code = f"SAVE10-{uuid.uuid4().hex[:4].upper()}"
        promo_resp = await client.post(
            "/api/v1/promotions",
            json={
                "name": "E2E 10% Off",
                "description": "Test promotion",
                "discount_type": "percentage",
                "value": 10,
                "priority": 1,
                "coupon_code": coupon_code,
                "start_date": "2024-01-01T00:00:00Z",
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert promo_resp.status_code == 201, promo_resp.text
        promo_id = promo_resp.json()["id"]
        
        # Activate promotion
        activate_resp = await client.post(
            f"/api/v1/promotions/{promo_id}/activate",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert activate_resp.status_code == 200
        
        # Create product
        product_resp = await client.post(
            "/api/v1/products",
            json={
                "name": "Promo Widget",
                "sku": f"PW-{uuid.uuid4().hex[:6]}",
                "retail_price": "100.00",
                "purchase_price": "50.00",
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert product_resp.status_code == 201
        product_id = product_resp.json()["id"]
        
        # Add stock
        await client.post(
            f"/api/v1/products/{product_id}/inventory/movements",
            json={"quantity": 10, "direction": "in", "reason": "stock"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        
        # Apply promotion to calculate discount
        apply_resp = await client.post(
            "/api/v1/promotions/apply",
            json={
                "promotion_id": promo_id,
                "subtotal": "100.00",
                "currency": "USD",
                "quantity": 1,
                "coupon_code": coupon_code,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert apply_resp.status_code == 200
        discount = Decimal(apply_resp.json()["discount_amount"])
        assert discount == Decimal("10.00")  # 10% of $100
        
        # Record sale with discounted price ($90 after 10% off)
        sale_resp = await client.post(
            "/api/v1/sales",
            json={
                "currency": "USD",
                "lines": [{"product_id": product_id, "quantity": 1, "unit_price": "90.00"}],
                "payments": [{"payment_method": "cash", "amount": "90.00"}],
            },
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert sale_resp.status_code == 201, sale_resp.text
        assert Decimal(sale_resp.json()["sale"]["total_amount"]) == Decimal("90.00")


@pytest.mark.asyncio
async def test_gift_card_insufficient_balance_e2e(async_session):
    """
    Test that gift card with insufficient balance is rejected:
    1. Purchase and activate gift card ($25)
    2. Try to pay more than balance ($30) - should fail
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(
            async_session, client, UserRole.MANAGER, email_prefix="e2e_gc_insuf"
        )
        cashier_token = await login_as(
            async_session, client, UserRole.CASHIER, email_prefix="e2e_gc_insuf_cashier"
        )
        
        # Create and stock product
        product_resp = await client.post(
            "/api/v1/products",
            json={
                "name": "Expensive Item",
                "sku": f"EXP-{uuid.uuid4().hex[:6]}",
                "retail_price": "30.00",
                "purchase_price": "15.00",
            },
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert product_resp.status_code == 201
        product_id = product_resp.json()["id"]
        
        await client.post(
            f"/api/v1/products/{product_id}/inventory/movements",
            json={"quantity": 5, "direction": "in", "reason": "stock"},
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        
        # Purchase $25 gift card
        gc_purchase = await client.post(
            "/api/v1/gift-cards/purchase",
            json={"amount": "25.00", "currency": "USD"},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert gc_purchase.status_code == 201
        gc_code = gc_purchase.json()["code"]
        
        # Activate
        await client.post(
            "/api/v1/gift-cards/activate",
            json={"code": gc_code},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        
        # Try to use $30 from $25 gift card - should fail
        sale_resp = await client.post(
            "/api/v1/sales",
            json={
                "currency": "USD",
                "lines": [{"product_id": product_id, "quantity": 1, "unit_price": "30.00"}],
                "payments": [
                    {"payment_method": "gift_card", "amount": "30.00", "gift_card_code": gc_code},
                ],
            },
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        # Should fail with validation error about insufficient balance
        assert sale_resp.status_code == 400, sale_resp.text
        assert "balance" in sale_resp.text.lower() or "insufficient" in sale_resp.text.lower()


@pytest.mark.asyncio
async def test_drawer_over_short_calculation_e2e(async_session):
    """
    Test cash drawer over/short calculation:
    1. Open drawer with $100
    2. Record $30 cash sale
    3. Close drawer counting $125 (should be $5 short - expected $130)
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(
            async_session, client, UserRole.MANAGER, email_prefix="e2e_overshort_mgr"
        )
        cashier_token = await login_as(
            async_session, client, UserRole.CASHIER, email_prefix="e2e_overshort"
        )
        terminal_id = f"TERM-OS-{uuid.uuid4().hex[:6]}"
        
        # Create product
        product_resp = await client.post(
            "/api/v1/products",
            json={
                "name": "OverShort Widget",
                "sku": f"OS-{uuid.uuid4().hex[:6]}",
                "retail_price": "30.00",
                "purchase_price": "15.00",
            },
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert product_resp.status_code == 201
        product_id = product_resp.json()["id"]
        
        await client.post(
            f"/api/v1/products/{product_id}/inventory/movements",
            json={"quantity": 10, "direction": "in", "reason": "stock"},
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        
        # Open drawer with $100
        drawer_resp = await client.post(
            "/api/v1/cash-drawer/open",
            json={"terminal_id": terminal_id, "opening_amount": "100.00"},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert drawer_resp.status_code == 201
        drawer_id = drawer_resp.json()["id"]
        
        # Start shift linked to drawer
        shift_resp = await client.post(
            "/api/v1/shifts/start",
            json={
                "terminal_id": terminal_id,
                "opening_cash": "100.00",
                "drawer_session_id": drawer_id,
            },
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert shift_resp.status_code == 201
        shift_id = shift_resp.json()["id"]
        
        # Record $30 cash sale
        sale_resp = await client.post(
            "/api/v1/sales",
            json={
                "currency": "USD",
                "lines": [{"product_id": product_id, "quantity": 1, "unit_price": "30.00"}],
                "payments": [{"payment_method": "cash", "amount": "30.00"}],
                "shift_id": shift_id,
            },
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert sale_resp.status_code == 201
        
        # End shift
        await client.post(
            "/api/v1/shifts/end",
            json={"shift_id": shift_id, "closing_cash": "125.00"},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        
        # Close drawer counting $125 (should be $5 short)
        # Expected: $100 + $30 = $130
        # Counted: $125
        # Over/Short: -$5 (short)
        drawer_close = await client.post(
            "/api/v1/cash-drawer/close",
            json={"session_id": drawer_id, "closing_amount": "125.00"},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert drawer_close.status_code == 200, drawer_close.text
        closed = drawer_close.json()
        
        # Verify over/short is -$5 (short)
        over_short = Decimal(closed["over_short"])
        assert over_short == Decimal("-5.00"), f"Expected -5.00 short, got {over_short}"
