"""Integration tests for Cash Drawer and Shift management (Phase 12)."""
import uuid
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.domain.auth.entities import UserRole
from tests.integration.api.helpers import login_as


# ---------------------- Cash Drawer Tests ----------------------


@pytest.mark.asyncio
async def test_open_and_close_cash_drawer(async_session):
    """Test opening and closing a cash drawer session."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="drawer_cashier")
        terminal_id = f"TERM-{uuid.uuid4().hex[:8]}"

        # Open drawer
        open_resp = await client.post(
            "/api/v1/cash-drawer/open",
            json={"terminal_id": terminal_id, "opening_amount": "100.00"},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert open_resp.status_code == 201, open_resp.text
        drawer = open_resp.json()
        assert drawer["status"] == "open"
        assert drawer["terminal_id"] == terminal_id
        assert Decimal(drawer["opening_amount"]) == Decimal("100.00")
        drawer_id = drawer["id"]

        # Close drawer
        close_resp = await client.post(
            "/api/v1/cash-drawer/close",
            json={"session_id": drawer_id, "closing_amount": "150.00", "notes": "End of shift"},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert close_resp.status_code == 200, close_resp.text
        closed_drawer = close_resp.json()
        assert closed_drawer["status"] == "closed"
        assert Decimal(closed_drawer["closing_amount"]) == Decimal("150.00")


@pytest.mark.asyncio
async def test_record_cash_movement(async_session):
    """Test recording cash movements (drop, pickup) on an open drawer."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="drawer_movement")
        terminal_id = f"TERM-{uuid.uuid4().hex[:8]}"

        # Open drawer
        open_resp = await client.post(
            "/api/v1/cash-drawer/open",
            json={"terminal_id": terminal_id, "opening_amount": "200.00"},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert open_resp.status_code == 201, open_resp.text
        drawer_id = open_resp.json()["id"]

        # Record a cash drop
        drop_resp = await client.post(
            "/api/v1/cash-drawer/movements",
            json={
                "session_id": drawer_id,
                "movement_type": "drop",
                "amount": "50.00",
                "notes": "Midday safe drop",
            },
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert drop_resp.status_code == 201, drop_resp.text
        movement = drop_resp.json()
        assert movement["movement_type"] == "drop"
        assert Decimal(movement["amount"]) == Decimal("50.00")

        # Record a cash pickup
        pickup_resp = await client.post(
            "/api/v1/cash-drawer/movements",
            json={
                "session_id": drawer_id,
                "movement_type": "pickup",
                "amount": "25.00",
                "notes": "Manager pickup",
            },
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert pickup_resp.status_code == 201, pickup_resp.text
        pickup = pickup_resp.json()
        assert pickup["movement_type"] == "pickup"


@pytest.mark.asyncio
async def test_get_open_drawer_for_terminal(async_session):
    """Test retrieving the currently open drawer for a terminal."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="drawer_terminal")
        terminal_id = f"TERM-{uuid.uuid4().hex[:8]}"

        # Initially no open drawer
        get_resp = await client.get(
            f"/api/v1/cash-drawer/terminal/{terminal_id}/open",
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert get_resp.status_code == 404

        # Open drawer
        open_resp = await client.post(
            "/api/v1/cash-drawer/open",
            json={"terminal_id": terminal_id, "opening_amount": "100.00"},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert open_resp.status_code == 201
        drawer_id = open_resp.json()["id"]

        # Now should find open drawer
        get_resp2 = await client.get(
            f"/api/v1/cash-drawer/terminal/{terminal_id}/open",
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert get_resp2.status_code == 200, get_resp2.text
        assert get_resp2.json()["id"] == drawer_id


@pytest.mark.asyncio
async def test_cannot_open_second_drawer_same_terminal(async_session):
    """Test that opening a second drawer on the same terminal fails."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="drawer_dup")
        terminal_id = f"TERM-{uuid.uuid4().hex[:8]}"

        # Open first drawer
        open_resp = await client.post(
            "/api/v1/cash-drawer/open",
            json={"terminal_id": terminal_id, "opening_amount": "100.00"},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert open_resp.status_code == 201

        # Try to open second drawer - should fail
        open_resp2 = await client.post(
            "/api/v1/cash-drawer/open",
            json={"terminal_id": terminal_id, "opening_amount": "100.00"},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert open_resp2.status_code == 400  # Domain validation error


# ---------------------- Shift Tests ----------------------


@pytest.mark.asyncio
async def test_start_and_end_shift(async_session):
    """Test starting and ending a cashier shift."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="shift_cashier")
        terminal_id = f"TERM-{uuid.uuid4().hex[:8]}"

        # Start shift
        start_resp = await client.post(
            "/api/v1/shifts/start",
            json={"terminal_id": terminal_id, "opening_cash": "100.00"},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert start_resp.status_code == 201, start_resp.text
        shift = start_resp.json()
        assert shift["status"] == "active"
        assert shift["terminal_id"] == terminal_id
        shift_id = shift["id"]

        # End shift
        end_resp = await client.post(
            "/api/v1/shifts/end",
            json={"shift_id": shift_id, "closing_cash": "150.00"},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert end_resp.status_code == 200, end_resp.text
        ended = end_resp.json()
        assert ended["status"] == "closed"
        assert Decimal(ended["closing_cash"]) == Decimal("150.00")


@pytest.mark.asyncio
async def test_get_active_shift(async_session):
    """Test retrieving the currently active shift for a user."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="shift_active")
        terminal_id = f"TERM-{uuid.uuid4().hex[:8]}"

        # No active shift initially
        get_resp = await client.get(
            "/api/v1/shifts/active",
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert get_resp.status_code == 404

        # Start shift
        start_resp = await client.post(
            "/api/v1/shifts/start",
            json={"terminal_id": terminal_id, "opening_cash": "100.00"},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert start_resp.status_code == 201
        shift_id = start_resp.json()["id"]

        # Now should find active shift
        get_resp2 = await client.get(
            "/api/v1/shifts/active",
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert get_resp2.status_code == 200, get_resp2.text
        assert get_resp2.json()["id"] == shift_id


@pytest.mark.asyncio
async def test_cannot_start_second_shift(async_session):
    """Test that starting a second shift while one is active fails."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="shift_dup")
        terminal_id = f"TERM-{uuid.uuid4().hex[:8]}"

        # Start first shift
        start_resp = await client.post(
            "/api/v1/shifts/start",
            json={"terminal_id": terminal_id, "opening_cash": "100.00"},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert start_resp.status_code == 201

        # Try to start second shift - should fail
        start_resp2 = await client.post(
            "/api/v1/shifts/start",
            json={"terminal_id": f"TERM-{uuid.uuid4().hex[:8]}", "opening_cash": "100.00"},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert start_resp2.status_code == 400  # Domain validation error


# ---------------------- Integration: Sale with Shift Tests ----------------------


@pytest.mark.asyncio
async def test_sale_linked_to_shift(async_session):
    """Test recording a sale linked to an active shift."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="mgr_shift_sale")
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="cashier_shift_sale")
        terminal_id = f"TERM-{uuid.uuid4().hex[:8]}"

        # Create product
        product_resp = await client.post(
            "/api/v1/products",
            json={
                "name": "ShiftTestWidget",
                "sku": f"ST-{uuid.uuid4().hex[:6]}",
                "retail_price": "25.00",
                "purchase_price": "12.00",
            },
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert product_resp.status_code == 201
        product_id = product_resp.json()["id"]

        # Seed stock
        stock_resp = await client.post(
            f"/api/v1/products/{product_id}/inventory/movements",
            json={"quantity": 10, "direction": "in", "reason": "init"},
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert stock_resp.status_code == 201

        # Start shift
        shift_resp = await client.post(
            "/api/v1/shifts/start",
            json={"terminal_id": terminal_id, "opening_cash": "100.00"},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert shift_resp.status_code == 201
        shift_id = shift_resp.json()["id"]

        # Record sale with shift_id
        sale_resp = await client.post(
            "/api/v1/sales",
            json={
                "currency": "USD",
                "lines": [{"product_id": product_id, "quantity": 2, "unit_price": "25.00"}],
                "payments": [{"payment_method": "cash", "amount": "50.00"}],
                "shift_id": shift_id,
            },
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert sale_resp.status_code == 201, sale_resp.text
        sale_body = sale_resp.json()
        assert sale_body["sale"]["shift_id"] == shift_id


@pytest.mark.asyncio
async def test_shift_with_drawer_tracks_cash_from_sales(async_session):
    """Test that cash payments from sales are tracked in the drawer via shift."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="mgr_drawer_sale")
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="cashier_drawer_sale")
        terminal_id = f"TERM-{uuid.uuid4().hex[:8]}"

        # Create product
        product_resp = await client.post(
            "/api/v1/products",
            json={
                "name": "DrawerSaleWidget",
                "sku": f"DS-{uuid.uuid4().hex[:6]}",
                "retail_price": "30.00",
                "purchase_price": "15.00",
            },
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert product_resp.status_code == 201
        product_id = product_resp.json()["id"]

        # Seed stock
        await client.post(
            f"/api/v1/products/{product_id}/inventory/movements",
            json={"quantity": 10, "direction": "in", "reason": "init"},
            headers={"Authorization": f"Bearer {manager_token}"},
        )

        # Open drawer
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

        # Record cash sale linked to shift
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
        assert sale_resp.status_code == 201, sale_resp.text

        # Verify drawer has a sale movement from the cash payment
        drawer_get = await client.get(
            f"/api/v1/cash-drawer/{drawer_id}",
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert drawer_get.status_code == 200
        drawer_data = drawer_get.json()
        movements = drawer_data.get("movements", [])
        # Sale movements track cash received from sales
        sale_movements = [m for m in movements if m["movement_type"] == "sale"]
        assert len(sale_movements) >= 1
        # At least one sale movement of 30.00
        amounts = [Decimal(m["amount"]) for m in sale_movements]
        assert Decimal("30.00") in amounts


# ---------------------- RBAC Tests ----------------------


@pytest.mark.asyncio
async def test_auditor_cannot_open_drawer(async_session):
    """Test that auditors cannot open cash drawers."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        auditor_token = await login_as(async_session, client, UserRole.AUDITOR, email_prefix="aud_drawer")

        resp = await client.post(
            "/api/v1/cash-drawer/open",
            json={"terminal_id": "TERM-AUD", "opening_amount": "100.00"},
            headers={"Authorization": f"Bearer {auditor_token}"},
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_auditor_cannot_start_shift(async_session):
    """Test that auditors cannot start shifts."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        auditor_token = await login_as(async_session, client, UserRole.AUDITOR, email_prefix="aud_shift")

        resp = await client.post(
            "/api/v1/shifts/start",
            json={"terminal_id": "TERM-AUD", "opening_cash": "100.00"},
            headers={"Authorization": f"Bearer {auditor_token}"},
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_cash_drawer_sessions(async_session):
    """Test listing cash drawer sessions with pagination."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="mgr_list_drawer")

        # List sessions (may be empty or have some from other tests)
        resp = await client.get(
            "/api/v1/cash-drawer",
            params={"page": 1, "limit": 10},
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body


@pytest.mark.asyncio
async def test_list_shifts(async_session):
    """Test listing shifts with pagination."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_token = await login_as(async_session, client, UserRole.MANAGER, email_prefix="mgr_list_shift")

        # List shifts
        resp = await client.get(
            "/api/v1/shifts",
            params={"page": 1, "limit": 10},
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "items" in body
