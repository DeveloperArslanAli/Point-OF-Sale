from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.domain.auth.entities import UserRole
from tests.integration.api.helpers import create_user_and_login


async def _register_and_login(
    async_session,
    client: AsyncClient,
    email: str,
    password: str = "Secretp@ss1",
    role: UserRole = UserRole.INVENTORY,
) -> str:
    return await create_user_and_login(async_session, client, email, password, role)


async def _create_product(async_session, client: AsyncClient) -> dict:
    manager_token = await create_user_and_login(
        async_session,
        client,
        f"manager_seed_{uuid4().hex[:6]}@example.com",
        "Secretp@ss1",
        UserRole.MANAGER,
    )
    unique_sku = f"SKU{uuid4().hex[:8]}"
    resp = await client.post(
        "/api/v1/products",
        json={
            "name": "Prod1",
            "sku": unique_sku,
            "retail_price": "10.00",
            "purchase_price": "5.00",
        },
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_record_inventory_movement_updates_stock_levels(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        inventory_token = await _register_and_login(
            async_session,
            client,
            f"inventory_{uuid4().hex[:6]}@example.com",
            role=UserRole.INVENTORY,
        )
        sales_token = await _register_and_login(
            async_session,
            client,
            f"sales_{uuid4().hex[:6]}@example.com",
            role=UserRole.CASHIER,
        )
        product = await _create_product(async_session, client)

        resp_in = await client.post(
            f"/api/v1/products/{product['id']}/inventory/movements",
            json={
                "quantity": 5,
                "direction": "in",
                "reason": "initial_stock",
            },
            headers={"Authorization": f"Bearer {inventory_token}"},
        )
        assert resp_in.status_code == 201, resp_in.text
        data_in = resp_in.json()
        assert data_in["movement"]["quantity"] == 5
        assert data_in["stock"]["quantity_on_hand"] == 5
        first_occurred = datetime.fromisoformat(data_in["movement"]["occurred_at"])

        resp_out = await client.post(
            f"/api/v1/products/{product['id']}/inventory/movements",
            json={
                "quantity": 2,
                "direction": "out",
                "reason": "sale",
            },
            headers={"Authorization": f"Bearer {inventory_token}"},
        )
        assert resp_out.status_code == 201, resp_out.text
        data_out = resp_out.json()
        assert data_out["stock"]["quantity_on_hand"] == 3
        assert data_out["movement"]["direction"] == "out"
        assert data_out["movement"]["quantity"] == 2

        stock_resp = await client.get(
            f"/api/v1/products/{product['id']}/stock",
            headers={"Authorization": f"Bearer {sales_token}"},
        )
        assert stock_resp.status_code == 200, stock_resp.text
        stock_data = stock_resp.json()
        assert stock_data["quantity_on_hand"] == 3
        assert stock_data["product_id"] == product["id"]

        past_resp = await client.get(
            f"/api/v1/products/{product['id']}/stock",
            params={"as_of": (first_occurred - timedelta(seconds=1)).isoformat()},
            headers={"Authorization": f"Bearer {sales_token}"},
        )
        assert past_resp.status_code == 200, past_resp.text
        assert past_resp.json()["quantity_on_hand"] == 0

        as_of_first_resp = await client.get(
            f"/api/v1/products/{product['id']}/stock",
            params={"as_of": first_occurred.isoformat()},
            headers={"Authorization": f"Bearer {sales_token}"},
        )
        assert as_of_first_resp.status_code == 200, as_of_first_resp.text
        assert as_of_first_resp.json()["quantity_on_hand"] == 5

        history_resp = await client.get(
            f"/api/v1/products/{product['id']}/inventory/movements",
            headers={"Authorization": f"Bearer {inventory_token}"},
        )
        assert history_resp.status_code == 200, history_resp.text
        history_data = history_resp.json()
        assert history_data["meta"]["total"] == 2
        assert len(history_data["items"]) == 2
        occurred_order = [datetime.fromisoformat(item["occurred_at"]) for item in history_data["items"]]
        assert occurred_order == sorted(occurred_order, reverse=True)


@pytest.mark.asyncio
async def test_record_inventory_movement_validation_errors(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _register_and_login(async_session, client, f"user_{uuid4().hex[:6]}@example.com")
        product = await _create_product(async_session, client)

        resp = await client.post(
            f"/api/v1/products/{product['id']}/inventory/movements",
            json={
                "quantity": 0,
                "direction": "in",
                "reason": "bad",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422  # Pydantic validation

        resp_missing_reason = await client.post(
            f"/api/v1/products/{product['id']}/inventory/movements",
            json={
                "quantity": 1,
                "direction": "in",
                "reason": " ",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp_missing_reason.status_code == 400
        payload = resp_missing_reason.json()
        assert payload["code"] == "inventory.invalid_reason"
        assert payload["trace_id"] == resp_missing_reason.headers.get("X-Trace-Id")


@pytest.mark.asyncio
async def test_inventory_endpoints_require_valid_product(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        inventory_token = await _register_and_login(
            async_session,
            client,
            f"inventory_{uuid4().hex[:6]}@example.com",
            role=UserRole.INVENTORY,
        )
        sales_token = await _register_and_login(
            async_session,
            client,
            f"sales_{uuid4().hex[:6]}@example.com",
            role=UserRole.CASHIER,
        )
        missing_id = "01HZZINVALIDPRODUCTID9"

        resp_post = await client.post(
            f"/api/v1/products/{missing_id}/inventory/movements",
            json={
                "quantity": 1,
                "direction": "in",
                "reason": "adjust",
            },
            headers={"Authorization": f"Bearer {inventory_token}"},
        )
        assert resp_post.status_code == 404
        payload_post = resp_post.json()
        assert payload_post["code"] == "not_found"

        resp_get = await client.get(
            f"/api/v1/products/{missing_id}/stock",
            headers={"Authorization": f"Bearer {sales_token}"},
        )
        assert resp_get.status_code == 404
        payload_get = resp_get.json()
        assert payload_get["code"] == "not_found"

        resp_history = await client.get(
            f"/api/v1/products/{missing_id}/inventory/movements",
            headers={"Authorization": f"Bearer {inventory_token}"},
        )
        assert resp_history.status_code == 404
        payload_history = resp_history.json()
        assert payload_history["code"] == "not_found"


@pytest.mark.asyncio
async def test_inventory_movement_history_pagination(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _register_and_login(async_session, client, f"user_{uuid4().hex[:6]}@example.com")
        product = await _create_product(async_session, client)

        base_time = datetime.now(UTC)
        payloads = [
            {
                "quantity": 10,
                "direction": "in",
                "reason": "first",
                "occurred_at": (base_time + timedelta(minutes=0)).isoformat(),
            },
            {
                "quantity": 3,
                "direction": "out",
                "reason": "second",
                "occurred_at": (base_time + timedelta(minutes=1)).isoformat(),
            },
            {
                "quantity": 5,
                "direction": "in",
                "reason": "third",
                "occurred_at": (base_time + timedelta(minutes=2)).isoformat(),
            },
        ]

        for payload in payloads:
            resp = await client.post(
                f"/api/v1/products/{product['id']}/inventory/movements",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 201, resp.text

        page1 = await client.get(
            f"/api/v1/products/{product['id']}/inventory/movements",
            params={"limit": 2, "page": 1},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert page1.status_code == 200, page1.text
        data1 = page1.json()
        assert data1["meta"] == {"page": 1, "limit": 2, "total": 3, "pages": 2}
        assert [item["reason"] for item in data1["items"]] == ["third", "second"]

        page2 = await client.get(
            f"/api/v1/products/{product['id']}/inventory/movements",
            params={"limit": 2, "page": 2},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert page2.status_code == 200, page2.text
        data2 = page2.json()
        assert data2["meta"] == {"page": 2, "limit": 2, "total": 3, "pages": 2}
        assert [item["reason"] for item in data2["items"]] == ["first"]
