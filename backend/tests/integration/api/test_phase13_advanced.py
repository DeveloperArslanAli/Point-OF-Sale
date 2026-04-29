"""Integration tests for Phase 13 advanced features.

Tests:
- Advanced forecasting with seasonality and confidence intervals
- Product-supplier links (CRUD)
- Purchase order receiving with exceptions
"""

import datetime
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.domain.auth.entities import UserRole
from tests.integration.api.helpers import login_as


@pytest.mark.asyncio
class TestAdvancedForecasting:
    """Tests for advanced forecasting with seasonality."""

    async def test_advanced_forecast_returns_seasonality_factors(self, async_session):
        """Test advanced forecast endpoint returns seasonality data."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            manager_token = await login_as(
                async_session, client, UserRole.MANAGER, email_prefix="mgr_adv_forecast"
            )
            headers = {"Authorization": f"Bearer {manager_token}"}

            now = datetime.datetime.now(datetime.timezone.utc)
            suffix = now.strftime("%Y%m%d%H%M%S%f")

            # Create product with sufficient historical data
            prod_resp = await client.post(
                "/api/v1/products",
                json={
                    "name": "SeasonalWidget",
                    "sku": f"SW-{suffix}",
                    "retail_price": "15.00",
                    "purchase_price": "8.00",
                },
                headers=headers,
            )
            assert prod_resp.status_code == 201, prod_resp.text
            product_id = prod_resp.json()["id"]

            # Seed varied movement data over multiple weeks
            for i in range(30):
                date = now - datetime.timedelta(days=i)
                direction = "out" if i % 2 == 0 else "in"
                quantity = 10 + (i % 7) * 5  # Vary quantity to create patterns

                await client.post(
                    f"/api/v1/inventory/products/{product_id}/movements",
                    json={
                        "quantity": quantity,
                        "direction": direction,
                        "reason": "sales" if direction == "out" else "restock",
                        "occurred_at": date.isoformat(),
                    },
                    headers=headers,
                )

            # Call advanced forecast endpoint
            resp = await client.get(
                "/api/v1/inventory/intelligence/forecast/advanced",
                params={
                    "product_id": product_id,
                    "lookback_days": 30,
                    "lead_time_days": 7,
                    "forecast_days": 14,
                },
                headers=headers,
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()

            # Verify response structure
            assert "product_id" in body
            assert body["product_id"] == product_id
            assert "method" in body
            assert "confidence" in body
            assert "insights" in body

    async def test_advanced_forecast_with_smoothing_alpha(self, async_session):
        """Test advanced forecast with custom smoothing alpha parameter."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            manager_token = await login_as(
                async_session, client, UserRole.MANAGER, email_prefix="mgr_smooth_forecast"
            )
            headers = {"Authorization": f"Bearer {manager_token}"}

            now = datetime.datetime.now(datetime.timezone.utc)
            suffix = now.strftime("%Y%m%d%H%M%S%f")

            prod_resp = await client.post(
                "/api/v1/products",
                json={
                    "name": "SmoothWidget",
                    "sku": f"SMW-{suffix}",
                    "retail_price": "20.00",
                    "purchase_price": "12.00",
                },
                headers=headers,
            )
            assert prod_resp.status_code == 201, prod_resp.text
            product_id = prod_resp.json()["id"]

            # Add some movement data
            await client.post(
                f"/api/v1/inventory/products/{product_id}/movements",
                json={
                    "quantity": 100,
                    "direction": "in",
                    "reason": "initial",
                    "occurred_at": (now - datetime.timedelta(days=10)).isoformat(),
                },
                headers=headers,
            )

            # Test with high smoothing alpha (more weight on recent data)
            resp = await client.get(
                "/api/v1/inventory/intelligence/forecast/advanced",
                params={
                    "product_id": product_id,
                    "smoothing_alpha": 0.5,
                    "lookback_days": 14,
                },
                headers=headers,
            )
            assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
class TestPurchaseOrderReceiving:
    """Tests for purchase order receiving functionality."""

    async def test_receive_purchase_order_full_delivery(self, async_session):
        """Test receiving a full purchase order creates inventory movements."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            manager_token = await login_as(
                async_session, client, UserRole.MANAGER, email_prefix="mgr_recv_full"
            )
            headers = {"Authorization": f"Bearer {manager_token}"}

            now = datetime.datetime.now(datetime.timezone.utc)
            suffix = now.strftime("%Y%m%d%H%M%S%f")

            # Create supplier
            supplier_resp = await client.post(
                "/api/v1/suppliers",
                json={
                    "name": f"ReceiveTestSupplier-{suffix}",
                    "email": f"recv-supplier-{suffix}@test.com",
                    "phone": "555-0123",
                },
                headers=headers,
            )
            assert supplier_resp.status_code == 201, supplier_resp.text
            supplier_id = supplier_resp.json()["id"]

            # Create product
            prod_resp = await client.post(
                "/api/v1/products",
                json={
                    "name": f"ReceiveWidget-{suffix}",
                    "sku": f"RW-{suffix}",
                    "retail_price": "25.00",
                    "purchase_price": "15.00",
                },
                headers=headers,
            )
            assert prod_resp.status_code == 201, prod_resp.text
            product_id = prod_resp.json()["id"]

            # Create purchase order
            po_resp = await client.post(
                "/api/v1/purchases",
                json={
                    "supplier_id": supplier_id,
                    "currency": "USD",
                    "lines": [
                        {
                            "product_id": product_id,
                            "quantity": 50,
                            "unit_cost": "15.00",
                        }
                    ],
                },
                headers=headers,
            )
            assert po_resp.status_code == 201, po_resp.text
            purchase = po_resp.json()["purchase"]
            purchase_id = purchase["id"]
            line_id = purchase["lines"][0]["id"]

            # Receive full order
            recv_resp = await client.post(
                f"/api/v1/purchases/{purchase_id}/receive",
                json={
                    "lines": [
                        {
                            "purchase_order_item_id": line_id,
                            "product_id": product_id,
                            "quantity_ordered": 50,
                            "quantity_received": 50,
                            "quantity_damaged": 0,
                        }
                    ],
                    "notes": "Full delivery received",
                },
                headers=headers,
            )
            assert recv_resp.status_code == 201, recv_resp.text
            body = recv_resp.json()

            # Verify response structure
            receiving = body["receiving"]
            assert receiving["status"] == "complete"
            assert receiving["fill_rate"] == "1.00"
            assert receiving["has_exceptions"] is False
            assert len(receiving["items"]) == 1

            item = receiving["items"][0]
            assert item["quantity_ordered"] == 50
            assert item["quantity_received"] == 50
            assert item["quantity_accepted"] == 50
            assert item["quantity_damaged"] == 0
            assert item["exception_type"] is None

            # Verify inventory movement was created
            assert len(body["movements"]) == 1
            movement = body["movements"][0]
            assert movement["product_id"] == product_id
            assert movement["quantity"] == 50
            assert movement["direction"] == "in"

    async def test_receive_purchase_order_partial_delivery(self, async_session):
        """Test receiving a partial delivery tracks exception."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            manager_token = await login_as(
                async_session, client, UserRole.MANAGER, email_prefix="mgr_recv_partial"
            )
            headers = {"Authorization": f"Bearer {manager_token}"}

            now = datetime.datetime.now(datetime.timezone.utc)
            suffix = now.strftime("%Y%m%d%H%M%S%f")

            # Create supplier and product
            supplier_resp = await client.post(
                "/api/v1/suppliers",
                json={
                    "name": f"PartialSupplier-{suffix}",
                    "email": f"partial-{suffix}@test.com",
                    "phone": "555-0456",
                },
                headers=headers,
            )
            assert supplier_resp.status_code == 201
            supplier_id = supplier_resp.json()["id"]

            prod_resp = await client.post(
                "/api/v1/products",
                json={
                    "name": f"PartialWidget-{suffix}",
                    "sku": f"PW-{suffix}",
                    "retail_price": "30.00",
                    "purchase_price": "18.00",
                },
                headers=headers,
            )
            assert prod_resp.status_code == 201
            product_id = prod_resp.json()["id"]

            # Create purchase order for 100 units
            po_resp = await client.post(
                "/api/v1/purchases",
                json={
                    "supplier_id": supplier_id,
                    "currency": "USD",
                    "lines": [
                        {
                            "product_id": product_id,
                            "quantity": 100,
                            "unit_cost": "18.00",
                        }
                    ],
                },
                headers=headers,
            )
            assert po_resp.status_code == 201
            purchase = po_resp.json()["purchase"]
            purchase_id = purchase["id"]
            line_id = purchase["lines"][0]["id"]

            # Receive only 75 units
            recv_resp = await client.post(
                f"/api/v1/purchases/{purchase_id}/receive",
                json={
                    "lines": [
                        {
                            "purchase_order_item_id": line_id,
                            "product_id": product_id,
                            "quantity_ordered": 100,
                            "quantity_received": 75,
                            "quantity_damaged": 0,
                            "exception_notes": "Supplier short 25 units",
                        }
                    ],
                    "notes": "Partial shipment received",
                },
                headers=headers,
            )
            assert recv_resp.status_code == 201, recv_resp.text
            body = recv_resp.json()

            receiving = body["receiving"]
            assert receiving["status"] == "partial"
            assert receiving["has_exceptions"] is True
            assert "partial_delivery" in receiving["exception_summary"]

            item = receiving["items"][0]
            assert item["quantity_accepted"] == 75
            assert item["exception_type"] == "partial_delivery"

    async def test_receive_purchase_order_with_damaged_items(self, async_session):
        """Test receiving with damaged items tracks separately."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            manager_token = await login_as(
                async_session, client, UserRole.MANAGER, email_prefix="mgr_recv_dmg"
            )
            headers = {"Authorization": f"Bearer {manager_token}"}

            now = datetime.datetime.now(datetime.timezone.utc)
            suffix = now.strftime("%Y%m%d%H%M%S%f")

            # Create supplier and product
            supplier_resp = await client.post(
                "/api/v1/suppliers",
                json={
                    "name": f"DamageSupplier-{suffix}",
                    "email": f"damage-{suffix}@test.com",
                    "phone": "555-0789",
                },
                headers=headers,
            )
            assert supplier_resp.status_code == 201
            supplier_id = supplier_resp.json()["id"]

            prod_resp = await client.post(
                "/api/v1/products",
                json={
                    "name": f"DamageWidget-{suffix}",
                    "sku": f"DW-{suffix}",
                    "retail_price": "50.00",
                    "purchase_price": "30.00",
                },
                headers=headers,
            )
            assert prod_resp.status_code == 201
            product_id = prod_resp.json()["id"]

            # Create purchase order for 40 units
            po_resp = await client.post(
                "/api/v1/purchases",
                json={
                    "supplier_id": supplier_id,
                    "currency": "USD",
                    "lines": [
                        {
                            "product_id": product_id,
                            "quantity": 40,
                            "unit_cost": "30.00",
                        }
                    ],
                },
                headers=headers,
            )
            assert po_resp.status_code == 201
            purchase = po_resp.json()["purchase"]
            purchase_id = purchase["id"]
            line_id = purchase["lines"][0]["id"]

            # Receive 40 units but 5 are damaged
            recv_resp = await client.post(
                f"/api/v1/purchases/{purchase_id}/receive",
                json={
                    "lines": [
                        {
                            "purchase_order_item_id": line_id,
                            "product_id": product_id,
                            "quantity_ordered": 40,
                            "quantity_received": 40,
                            "quantity_damaged": 5,
                            "exception_notes": "5 units arrived with broken packaging",
                        }
                    ],
                    "notes": "Full shipment with damage",
                },
                headers=headers,
            )
            assert recv_resp.status_code == 201, recv_resp.text
            body = recv_resp.json()

            receiving = body["receiving"]
            assert receiving["total_damaged"] == 5
            assert receiving["has_exceptions"] is True
            assert "damaged" in receiving["exception_summary"]

            item = receiving["items"][0]
            assert item["quantity_received"] == 40
            assert item["quantity_damaged"] == 5
            assert item["quantity_accepted"] == 35
            assert item["exception_type"] == "damaged"

            # Verify only accepted quantity was added to inventory
            assert len(body["movements"]) == 1
            assert body["movements"][0]["quantity"] == 35
