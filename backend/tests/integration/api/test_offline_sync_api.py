"""Integration tests for offline sync replay API."""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.domain.auth.entities import UserRole
from tests.integration.api.helpers import login_as

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio


# ---------------------- Helper Functions ----------------------


async def add_stock_for_product(session: "AsyncSession", product_id: str, quantity: int = 100) -> None:
    """Add initial stock for a product by creating an inventory movement."""
    from app.infrastructure.db.repositories.inventory_movement_repository import SqlAlchemyInventoryMovementRepository
    from app.domain.inventory import InventoryMovement, MovementDirection
    
    inventory_repo = SqlAlchemyInventoryMovementRepository(session)
    movement = InventoryMovement.record(
        product_id=product_id,
        quantity=quantity,
        direction=MovementDirection.IN,
        reason="initial_stock",
        reference="test-setup",
    )
    await inventory_repo.add(movement)
    await session.commit()


# ---------------------- Offline Sync Replay Tests ----------------------


async def test_replay_sale_action_success(async_session: "AsyncSession") -> None:
    """Sale action should create a sale and return success."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="sync_sale")

        # First create a product for the sale
        from app.infrastructure.db.models.product_model import ProductModel
        from ulid import ULID

        product_id = str(ULID())
        product = ProductModel(
            id=product_id,
            sku=f"SYNC-TEST-{uuid.uuid4().hex[:6]}",
            name="Sync Test Product",
            price_retail=Decimal("10.00"),
            purchase_price=Decimal("5.00"),
            
            category_id=None,
            active=True,
        )
        async_session.add(product)
        await async_session.commit()
        
        # Add stock for the product
        await add_stock_for_product(async_session, product_id, quantity=100)

        # Create sale action
        idempotency_key = str(uuid.uuid4())
        items = [
            {
                "idempotency_key": idempotency_key,
                "action_type": "sale",
                "payload": {
                    "lines": [
                        {"product_id": product_id, "quantity": 2, "unit_price": "10.00"}
                    ],
                    "payments": [{"payment_method": "cash", "amount": "20.00"}],
                },
            }
        ]

        response = await client.post(
            "/api/v1/sync/replay",
            json={"terminal_id": "terminal-001", "items": items},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["total_items"] == 1
        assert data["completed_count"] == 1
        assert data["skipped_count"] == 0
        assert data["failed_count"] == 0
        assert len(data["results"]) == 1
        assert data["results"][0]["idempotency_key"] == idempotency_key
        assert data["results"][0]["status"] == "completed"
        assert data["results"][0]["result_id"] is not None


async def test_replay_idempotency_skips_duplicate(async_session: "AsyncSession") -> None:
    """Replaying same idempotency_key should be skipped (idempotent)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="sync_idempotent")

        from app.infrastructure.db.models.product_model import ProductModel
        from ulid import ULID

        product_id = str(ULID())
        product = ProductModel(
            id=product_id,
            sku=f"SYNC-TEST-{uuid.uuid4().hex[:6]}",
            name="Idempotency Test Product",
            price_retail=Decimal("15.00"),
            purchase_price=Decimal("8.00"),
            
            category_id=None,
            active=True,
        )
        async_session.add(product)
        await async_session.commit()
        
        # Add stock for the product
        await add_stock_for_product(async_session, product_id, quantity=100)

        idempotency_key = str(uuid.uuid4())
        items = [
            {
                "idempotency_key": idempotency_key,
                "action_type": "sale",
                "payload": {
                    "lines": [
                        {"product_id": product_id, "quantity": 1, "unit_price": "15.00"}
                    ],
                    "payments": [{"payment_method": "cash", "amount": "15.00"}],
                },
            }
        ]

        # First request
        response1 = await client.post(
            "/api/v1/sync/replay",
            json={"terminal_id": "terminal-001", "items": items},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert response1.status_code == 200, response1.text
        data1 = response1.json()
        assert data1["completed_count"] == 1
        first_server_id = data1["results"][0]["result_id"]

        # Second request with same idempotency_key - should be skipped
        response2 = await client.post(
            "/api/v1/sync/replay",
            json={"terminal_id": "terminal-001", "items": items},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert response2.status_code == 200, response2.text
        data2 = response2.json()
        assert data2["completed_count"] == 0
        assert data2["skipped_count"] == 1
        assert data2["results"][0]["status"] == "skipped"
        # Should return the original server_id
        assert data2["results"][0]["result_id"] == first_server_id


async def test_replay_multiple_actions_batch(async_session: "AsyncSession") -> None:
    """Multiple actions in a batch should all be processed."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="sync_batch")

        from app.infrastructure.db.models.product_model import ProductModel
        from ulid import ULID

        product_id = str(ULID())
        product = ProductModel(
            id=product_id,
            sku=f"SYNC-TEST-{uuid.uuid4().hex[:6]}",
            name="Batch Test Product",
            price_retail=Decimal("5.00"),
            purchase_price=Decimal("2.50"),
            
            category_id=None,
            active=True,
        )
        async_session.add(product)
        await async_session.commit()
        # Add stock for the product (needs 1+2+3=6 units)
        await add_stock_for_product(async_session, product_id, quantity=100)

        items = [
            {
                "idempotency_key": str(uuid.uuid4()),
                "action_type": "sale",
                "payload": {
                    "lines": [
                        {"product_id": product_id, "quantity": 1, "unit_price": "5.00"}
                    ],
                    "payments": [{"payment_method": "cash", "amount": "5.00"}],
                },
            },
            {
                "idempotency_key": str(uuid.uuid4()),
                "action_type": "sale",
                "payload": {
                    "lines": [
                        {"product_id": product_id, "quantity": 2, "unit_price": "5.00"}
                    ],
                    "payments": [{"payment_method": "card", "amount": "10.00"}],
                },
            },
            {
                "idempotency_key": str(uuid.uuid4()),
                "action_type": "sale",
                "payload": {
                    "lines": [
                        {"product_id": product_id, "quantity": 3, "unit_price": "5.00"}
                    ],
                    "payments": [{"payment_method": "cash", "amount": "15.00"}],
                },
            },
        ]

        response = await client.post(
            "/api/v1/sync/replay",
            json={"terminal_id": "terminal-001", "items": items},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["total_items"] == 3
        assert data["completed_count"] == 3
        assert data["skipped_count"] == 0
        assert data["failed_count"] == 0
        assert len(data["results"]) == 3
        for result in data["results"]:
            assert result["status"] == "completed"
            assert result["result_id"] is not None


async def test_replay_invalid_action_type_fails(async_session: "AsyncSession") -> None:
    """Invalid action type should fail processing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="sync_invalid")

        items = [
            {
                "idempotency_key": str(uuid.uuid4()),
                "action_type": "invalid_type",
                "payload": {},
            }
        ]

        response = await client.post(
            "/api/v1/sync/replay",
            json={"terminal_id": "terminal-001", "items": items},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        # Action type validation happens during processing, not schema validation
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["failed_count"] == 1
        assert data["results"][0]["status"] == "failed"


async def test_replay_requires_authentication(async_session: "AsyncSession") -> None:
    """Sync replay requires authentication."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/sync/replay",
            json={"terminal_id": "terminal-001", "items": []},
        )
        assert response.status_code == 401


async def test_replay_partial_batch_with_failure(async_session: "AsyncSession") -> None:
    """Batch with one failing action should still process others."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="sync_partial")

        from app.infrastructure.db.models.product_model import ProductModel
        from ulid import ULID

        product_id = str(ULID())
        product = ProductModel(
            id=product_id,
            sku=f"SYNC-TEST-{uuid.uuid4().hex[:6]}",
            name="Partial Batch Test Product",
            price_retail=Decimal("10.00"),
            purchase_price=Decimal("5.00"),
            
            category_id=None,
            active=True,
        )
        async_session.add(product)
        await async_session.commit()
        # Add stock for the product (needs 1+2=3 units for the valid sales)
        await add_stock_for_product(async_session, product_id, quantity=100)

        items = [
            {
                "idempotency_key": str(uuid.uuid4()),
                "action_type": "sale",
                "payload": {
                    "lines": [
                        {"product_id": product_id, "quantity": 1, "unit_price": "10.00"}
                    ],
                    "payments": [{"payment_method": "cash", "amount": "10.00"}],
                },
            },
            {
                "idempotency_key": str(uuid.uuid4()),
                "action_type": "sale",
                "payload": {
                    "lines": [
                        {"product_id": "nonexistent-product-id", "quantity": 1, "unit_price": "10.00"}
                    ],
                    "payments": [{"payment_method": "cash", "amount": "10.00"}],
                },
            },
            {
                "idempotency_key": str(uuid.uuid4()),
                "action_type": "sale",
                "payload": {
                    "lines": [
                        {"product_id": product_id, "quantity": 2, "unit_price": "10.00"}
                    ],
                    "payments": [{"payment_method": "cash", "amount": "20.00"}],
                },
            },
        ]

        response = await client.post(
            "/api/v1/sync/replay",
            json={"terminal_id": "terminal-001", "items": items},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["total_items"] == 3
        # At least 2 should complete, 1 should fail
        assert data["completed_count"] >= 2
        assert data["failed_count"] >= 1


async def test_replay_shift_start_action(async_session: "AsyncSession") -> None:
    """Shift start action should create a shift."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="sync_shift")

        idempotency_key = str(uuid.uuid4())
        items = [
            {
                "idempotency_key": idempotency_key,
                "action_type": "shift_start",
                "payload": {
                    "terminal_id": f"terminal-{uuid.uuid4().hex[:8]}",
                    "opening_cash": "100.00",
                    "currency": "USD",
                },
            }
        ]

        response = await client.post(
            "/api/v1/sync/replay",
            json={"terminal_id": "terminal-001", "items": items},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["completed_count"] == 1
        assert data["results"][0]["status"] == "completed"
        assert data["results"][0]["result_id"] is not None


async def test_replay_drawer_open_action(async_session: "AsyncSession") -> None:
    """Drawer open action should create a drawer session."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="sync_drawer")

        idempotency_key = str(uuid.uuid4())
        items = [
            {
                "idempotency_key": idempotency_key,
                "action_type": "drawer_open",
                "payload": {
                    "terminal_id": f"terminal-{uuid.uuid4().hex[:8]}",
                    "opening_amount": "200.00",
                    "currency": "USD",
                },
            }
        ]

        response = await client.post(
            "/api/v1/sync/replay",
            json={"terminal_id": "terminal-002", "items": items},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["completed_count"] == 1
        assert data["results"][0]["status"] == "completed"
        assert data["results"][0]["result_id"] is not None


async def test_replay_empty_items_fails_validation(async_session: "AsyncSession") -> None:
    """Empty items list should fail validation."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="sync_empty")

        response = await client.post(
            "/api/v1/sync/replay",
            json={"terminal_id": "terminal-001", "items": []},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        assert response.status_code == 422  # Validation error


async def test_unsupported_action_type_fails(async_session: "AsyncSession") -> None:
    """Unsupported action types should fail processing gracefully."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        cashier_token = await login_as(async_session, client, UserRole.CASHIER, email_prefix="sync_unsupported")

        items = [
            {
                "idempotency_key": str(uuid.uuid4()),
                "action_type": "future_action",
                "payload": {"some": "data"},
            }
        ]

        response = await client.post(
            "/api/v1/sync/replay",
            json={"terminal_id": "terminal-001", "items": items},
            headers={"Authorization": f"Bearer {cashier_token}"},
        )
        # Should process but fail since action type is unsupported
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["failed_count"] == 1
        assert "unsupported" in data["results"][0]["error"].lower() or "invalid" in data["results"][0]["error"].lower() or "not a valid" in data["results"][0]["error"].lower()
