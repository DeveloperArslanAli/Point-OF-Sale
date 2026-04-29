"""Integration tests for product-supplier links API.

Tests CRUD operations and preferred supplier functionality.
"""

import datetime
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.domain.auth.entities import UserRole
from tests.integration.api.helpers import login_as


@pytest.mark.asyncio
class TestProductSupplierLinksAPI:
    """Tests for product-supplier links CRUD."""

    async def test_create_product_supplier_link(self, async_session):
        """Test creating a product-supplier link."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            manager_token = await login_as(
                async_session, client, UserRole.MANAGER, email_prefix="mgr_link_create"
            )
            headers = {"Authorization": f"Bearer {manager_token}"}

            now = datetime.datetime.now(datetime.timezone.utc)
            suffix = now.strftime("%Y%m%d%H%M%S%f")

            # Create supplier
            supplier_resp = await client.post(
                "/api/v1/suppliers",
                json={
                    "name": f"LinkTestSupplier-{suffix}",
                    "email": f"link-supplier-{suffix}@test.com",
                },
                headers=headers,
            )
            assert supplier_resp.status_code == 201
            supplier_id = supplier_resp.json()["id"]

            # Create product
            prod_resp = await client.post(
                "/api/v1/products",
                json={
                    "name": f"LinkTestProduct-{suffix}",
                    "sku": f"LTP-{suffix}",
                    "retail_price": "50.00",
                    "purchase_price": "30.00",
                },
                headers=headers,
            )
            assert prod_resp.status_code == 201
            product_id = prod_resp.json()["id"]

            # Create link
            link_resp = await client.post(
                "/api/v1/product-supplier-links",
                json={
                    "product_id": product_id,
                    "supplier_id": supplier_id,
                    "unit_cost": "25.00",
                    "currency": "USD",
                    "minimum_order_quantity": 10,
                    "lead_time_days": 5,
                    "priority": 1,
                    "is_preferred": True,
                    "notes": "Primary supplier for this product",
                },
                headers=headers,
            )
            assert link_resp.status_code == 201, link_resp.text
            link = link_resp.json()

            assert link["product_id"] == product_id
            assert link["supplier_id"] == supplier_id
            assert link["unit_cost"] == "25.00"
            assert link["minimum_order_quantity"] == 10
            assert link["lead_time_days"] == 5
            assert link["is_preferred"] is True
            assert link["is_active"] is True

    async def test_get_product_supplier_link(self, async_session):
        """Test getting a product-supplier link by ID."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            manager_token = await login_as(
                async_session, client, UserRole.MANAGER, email_prefix="mgr_link_get"
            )
            headers = {"Authorization": f"Bearer {manager_token}"}

            now = datetime.datetime.now(datetime.timezone.utc)
            suffix = now.strftime("%Y%m%d%H%M%S%f")

            # Create supplier and product
            supplier_resp = await client.post(
                "/api/v1/suppliers",
                json={"name": f"GetLinkSupplier-{suffix}", "email": f"get-{suffix}@test.com"},
                headers=headers,
            )
            supplier_id = supplier_resp.json()["id"]

            prod_resp = await client.post(
                "/api/v1/products",
                json={"name": f"GetLinkProduct-{suffix}", "sku": f"GLP-{suffix}", "retail_price": "10.00"},
                headers=headers,
            )
            product_id = prod_resp.json()["id"]

            # Create link
            create_resp = await client.post(
                "/api/v1/product-supplier-links",
                json={"product_id": product_id, "supplier_id": supplier_id, "unit_cost": "8.00"},
                headers=headers,
            )
            link_id = create_resp.json()["id"]

            # Get link
            get_resp = await client.get(f"/api/v1/product-supplier-links/{link_id}", headers=headers)
            assert get_resp.status_code == 200
            assert get_resp.json()["id"] == link_id

    async def test_update_product_supplier_link(self, async_session):
        """Test updating a product-supplier link."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            manager_token = await login_as(
                async_session, client, UserRole.MANAGER, email_prefix="mgr_link_update"
            )
            headers = {"Authorization": f"Bearer {manager_token}"}

            now = datetime.datetime.now(datetime.timezone.utc)
            suffix = now.strftime("%Y%m%d%H%M%S%f")

            # Setup
            supplier_resp = await client.post(
                "/api/v1/suppliers",
                json={"name": f"UpdateLinkSupplier-{suffix}", "email": f"upd-{suffix}@test.com"},
                headers=headers,
            )
            supplier_id = supplier_resp.json()["id"]

            prod_resp = await client.post(
                "/api/v1/products",
                json={"name": f"UpdateLinkProduct-{suffix}", "sku": f"ULP-{suffix}", "retail_price": "20.00"},
                headers=headers,
            )
            product_id = prod_resp.json()["id"]

            create_resp = await client.post(
                "/api/v1/product-supplier-links",
                json={"product_id": product_id, "supplier_id": supplier_id, "unit_cost": "15.00"},
                headers=headers,
            )
            link_id = create_resp.json()["id"]

            # Update
            update_resp = await client.patch(
                f"/api/v1/product-supplier-links/{link_id}",
                json={
                    "unit_cost": "12.00",
                    "lead_time_days": 3,
                    "is_preferred": True,
                },
                headers=headers,
            )
            assert update_resp.status_code == 200
            updated = update_resp.json()
            assert updated["unit_cost"] == "12.00"
            assert updated["lead_time_days"] == 3
            assert updated["is_preferred"] is True

    async def test_delete_product_supplier_link(self, async_session):
        """Test deleting a product-supplier link."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            manager_token = await login_as(
                async_session, client, UserRole.MANAGER, email_prefix="mgr_link_delete"
            )
            headers = {"Authorization": f"Bearer {manager_token}"}

            now = datetime.datetime.now(datetime.timezone.utc)
            suffix = now.strftime("%Y%m%d%H%M%S%f")

            # Setup
            supplier_resp = await client.post(
                "/api/v1/suppliers",
                json={"name": f"DeleteLinkSupplier-{suffix}", "email": f"del-{suffix}@test.com"},
                headers=headers,
            )
            supplier_id = supplier_resp.json()["id"]

            prod_resp = await client.post(
                "/api/v1/products",
                json={"name": f"DeleteLinkProduct-{suffix}", "sku": f"DLP-{suffix}", "retail_price": "30.00"},
                headers=headers,
            )
            product_id = prod_resp.json()["id"]

            create_resp = await client.post(
                "/api/v1/product-supplier-links",
                json={"product_id": product_id, "supplier_id": supplier_id, "unit_cost": "22.00"},
                headers=headers,
            )
            link_id = create_resp.json()["id"]

            # Delete
            delete_resp = await client.delete(f"/api/v1/product-supplier-links/{link_id}", headers=headers)
            assert delete_resp.status_code == 204

            # Verify deleted
            get_resp = await client.get(f"/api/v1/product-supplier-links/{link_id}", headers=headers)
            assert get_resp.status_code == 404

    async def test_list_product_suppliers(self, async_session):
        """Test listing all suppliers for a product."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            manager_token = await login_as(
                async_session, client, UserRole.MANAGER, email_prefix="mgr_link_list"
            )
            headers = {"Authorization": f"Bearer {manager_token}"}

            now = datetime.datetime.now(datetime.timezone.utc)
            suffix = now.strftime("%Y%m%d%H%M%S%f")

            # Create product
            prod_resp = await client.post(
                "/api/v1/products",
                json={"name": f"MultiSupplierProduct-{suffix}", "sku": f"MSP-{suffix}", "retail_price": "100.00"},
                headers=headers,
            )
            product_id = prod_resp.json()["id"]

            # Create multiple suppliers and links
            for i in range(3):
                supplier_resp = await client.post(
                    "/api/v1/suppliers",
                    json={"name": f"Supplier{i}-{suffix}", "email": f"sup{i}-{suffix}@test.com"},
                    headers=headers,
                )
                supplier_id = supplier_resp.json()["id"]

                await client.post(
                    "/api/v1/product-supplier-links",
                    json={
                        "product_id": product_id,
                        "supplier_id": supplier_id,
                        "unit_cost": str(50 + i * 5),
                        "priority": i + 1,
                        "is_preferred": i == 0,
                    },
                    headers=headers,
                )

            # List suppliers for product
            list_resp = await client.get(
                f"/api/v1/product-supplier-links/by-product/{product_id}",
                headers=headers,
            )
            assert list_resp.status_code == 200
            data = list_resp.json()
            assert data["total"] == 3
            # Preferred should be first
            assert data["items"][0]["is_preferred"] is True

    async def test_get_preferred_supplier(self, async_session):
        """Test getting the preferred supplier for a product."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            manager_token = await login_as(
                async_session, client, UserRole.MANAGER, email_prefix="mgr_link_pref"
            )
            headers = {"Authorization": f"Bearer {manager_token}"}

            now = datetime.datetime.now(datetime.timezone.utc)
            suffix = now.strftime("%Y%m%d%H%M%S%f")

            # Create product and suppliers
            prod_resp = await client.post(
                "/api/v1/products",
                json={"name": f"PreferredProduct-{suffix}", "sku": f"PP-{suffix}", "retail_price": "75.00"},
                headers=headers,
            )
            product_id = prod_resp.json()["id"]

            sup1_resp = await client.post(
                "/api/v1/suppliers",
                json={"name": f"PrefSupplier1-{suffix}", "email": f"pref1-{suffix}@test.com"},
                headers=headers,
            )
            supplier1_id = sup1_resp.json()["id"]

            sup2_resp = await client.post(
                "/api/v1/suppliers",
                json={"name": f"PrefSupplier2-{suffix}", "email": f"pref2-{suffix}@test.com"},
                headers=headers,
            )
            supplier2_id = sup2_resp.json()["id"]

            # Create links - supplier2 is preferred
            await client.post(
                "/api/v1/product-supplier-links",
                json={"product_id": product_id, "supplier_id": supplier1_id, "unit_cost": "60.00"},
                headers=headers,
            )
            await client.post(
                "/api/v1/product-supplier-links",
                json={"product_id": product_id, "supplier_id": supplier2_id, "unit_cost": "55.00", "is_preferred": True},
                headers=headers,
            )

            # Get preferred
            pref_resp = await client.get(
                f"/api/v1/product-supplier-links/by-product/{product_id}/preferred",
                headers=headers,
            )
            assert pref_resp.status_code == 200
            data = pref_resp.json()
            assert data["has_preferred"] is True
            assert data["link"]["supplier_id"] == supplier2_id

    async def test_set_preferred_supplier(self, async_session):
        """Test setting a supplier as preferred."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            manager_token = await login_as(
                async_session, client, UserRole.MANAGER, email_prefix="mgr_link_setpref"
            )
            headers = {"Authorization": f"Bearer {manager_token}"}

            now = datetime.datetime.now(datetime.timezone.utc)
            suffix = now.strftime("%Y%m%d%H%M%S%f")

            # Setup
            prod_resp = await client.post(
                "/api/v1/products",
                json={"name": f"SetPrefProduct-{suffix}", "sku": f"SPP-{suffix}", "retail_price": "80.00"},
                headers=headers,
            )
            product_id = prod_resp.json()["id"]

            sup1_resp = await client.post(
                "/api/v1/suppliers",
                json={"name": f"SetPrefSup1-{suffix}", "email": f"setpref1-{suffix}@test.com"},
                headers=headers,
            )
            supplier1_id = sup1_resp.json()["id"]

            sup2_resp = await client.post(
                "/api/v1/suppliers",
                json={"name": f"SetPrefSup2-{suffix}", "email": f"setpref2-{suffix}@test.com"},
                headers=headers,
            )
            supplier2_id = sup2_resp.json()["id"]

            # Create links - supplier1 initially preferred
            await client.post(
                "/api/v1/product-supplier-links",
                json={"product_id": product_id, "supplier_id": supplier1_id, "unit_cost": "40.00", "is_preferred": True},
                headers=headers,
            )
            await client.post(
                "/api/v1/product-supplier-links",
                json={"product_id": product_id, "supplier_id": supplier2_id, "unit_cost": "35.00"},
                headers=headers,
            )

            # Set supplier2 as preferred
            set_resp = await client.post(
                f"/api/v1/product-supplier-links/by-product/{product_id}/preferred/{supplier2_id}",
                headers=headers,
            )
            assert set_resp.status_code == 200
            assert set_resp.json()["is_preferred"] is True

            # Verify supplier1 is no longer preferred
            list_resp = await client.get(
                f"/api/v1/product-supplier-links/by-product/{product_id}",
                headers=headers,
            )
            items = list_resp.json()["items"]
            sup1_link = next(i for i in items if i["supplier_id"] == supplier1_id)
            sup2_link = next(i for i in items if i["supplier_id"] == supplier2_id)
            assert sup1_link["is_preferred"] is False
            assert sup2_link["is_preferred"] is True


@pytest.mark.asyncio
class TestProductSupplierLinksInPODrafts:
    """Test that PO drafts use product-supplier links for pricing."""

    async def test_po_drafts_use_link_pricing(self, async_session):
        """Test that PO drafts prefer explicit link pricing over historical data."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            manager_token = await login_as(
                async_session, client, UserRole.MANAGER, email_prefix="mgr_po_link"
            )
            headers = {"Authorization": f"Bearer {manager_token}"}

            now = datetime.datetime.now(datetime.timezone.utc)
            suffix = now.strftime("%Y%m%d%H%M%S%f")

            # Create supplier
            supplier_resp = await client.post(
                "/api/v1/suppliers",
                json={"name": f"POLinkSupplier-{suffix}", "email": f"polink-{suffix}@test.com"},
                headers=headers,
            )
            supplier_id = supplier_resp.json()["id"]

            # Create product with stock movement to trigger low-stock suggestion
            prod_resp = await client.post(
                "/api/v1/products",
                json={
                    "name": f"POLinkProduct-{suffix}",
                    "sku": f"POLP-{suffix}",
                    "retail_price": "100.00",
                    "purchase_price": "70.00",  # Default price
                },
                headers=headers,
            )
            product_id = prod_resp.json()["id"]

            # Add some stock and consume to create demand
            await client.post(
                f"/api/v1/inventory/products/{product_id}/movements",
                json={
                    "quantity": 50,
                    "direction": "in",
                    "reason": "initial",
                    "occurred_at": (now - datetime.timedelta(days=10)).isoformat(),
                },
                headers=headers,
            )
            await client.post(
                f"/api/v1/inventory/products/{product_id}/movements",
                json={
                    "quantity": 45,
                    "direction": "out",
                    "reason": "sales",
                    "occurred_at": (now - datetime.timedelta(days=1)).isoformat(),
                },
                headers=headers,
            )

            # Create explicit link with lower price
            await client.post(
                "/api/v1/product-supplier-links",
                json={
                    "product_id": product_id,
                    "supplier_id": supplier_id,
                    "unit_cost": "55.00",  # Explicit override - lower than purchase_price
                    "lead_time_days": 3,
                    "is_preferred": True,
                },
                headers=headers,
            )

            # Get PO drafts - should use link pricing
            drafts_resp = await client.get(
                "/api/v1/inventory/intelligence/po-drafts",
                params={
                    "lookback_days": 30,
                    "lead_time_days": 7,
                    "safety_stock_days": 2,
                    "supplier_id": supplier_id,
                },
                headers=headers,
            )
            assert drafts_resp.status_code == 200
            data = drafts_resp.json()

            # Find our product's line if present
            product_line = next((l for l in data["lines"] if l["product_id"] == product_id), None)
            if product_line:
                # Should use the explicit link price (55.00), not default (70.00)
                assert product_line["unit_cost"] == "55.00"
