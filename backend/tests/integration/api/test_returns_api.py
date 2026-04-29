from __future__ import annotations

from uuid import uuid4
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.domain.auth.entities import UserRole
from tests.integration.api.helpers import login_as


async def _register_and_login(
    async_session,
    client: AsyncClient,
    *,
    role: UserRole = UserRole.CASHIER,
    label: str | None = None,
) -> str:
    prefix = label or f"user_{uuid4().hex[:6]}"
    return await login_as(async_session, client, role, email_prefix=prefix)


async def _create_product(client: AsyncClient, token: str, *, name: str = "Prod1", sku: str | None = None) -> dict:
    unique_sku = sku or f"SKU{uuid4().hex[:8]}"
    resp = await client.post(
        "/api/v1/products",
        json={
            "name": name,
            "sku": unique_sku,
            "retail_price": "10.00",
            "purchase_price": "5.00",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _add_stock(client: AsyncClient, token: str, product_id: str, quantity: int) -> None:
    resp = await client.post(
        f"/api/v1/products/{product_id}/inventory/movements",
        json={
            "quantity": quantity,
            "direction": "in",
            "reason": "initial_stock",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text


async def _record_sale(
    client: AsyncClient,
    token: str,
    *,
    product_id: str,
    quantity: int,
    unit_price: str = "12.00",
    payments: list[dict] | None = None,
) -> dict:
    payload = {
        "currency": "USD",
        "lines": [
            {
                "product_id": product_id,
                "quantity": quantity,
                "unit_price": unit_price,
            }
        ],
    }

    if payments is None:
        payload["payments"] = [
            {
                "payment_method": "cash",
                "amount": str(Decimal(unit_price) * quantity),
            }
        ]
    else:
        payload["payments"] = payments

    resp = await client.post(
        "/api/v1/sales",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["sale"]


async def _login_returns_and_manager(async_session, client: AsyncClient) -> tuple[str, str]:
    returns_token = await _register_and_login(async_session, client, role=UserRole.CASHIER)
    manager_token = await _register_and_login(async_session, client, role=UserRole.MANAGER)
    return returns_token, manager_token


@pytest.mark.asyncio
async def test_record_return_restocks_inventory_and_returns_summary(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        returns_token, manager_token = await _login_returns_and_manager(async_session, client)
        product = await _create_product(client, manager_token)
        await _add_stock(client, manager_token, product["id"], quantity=5)
        sale = await _record_sale(client, returns_token, product_id=product["id"], quantity=2, unit_price="15.00")

        sale_item_id = sale["items"][0]["id"]
        resp = await client.post(
            "/api/v1/returns",
            json={
                "sale_id": sale["id"],
                "lines": [
                    {
                        "sale_item_id": sale_item_id,
                        "quantity": 1,
                    }
                ],
            },
            headers={"Authorization": f"Bearer {returns_token}"},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        returned = body["return"]
        assert returned["sale_id"] == sale["id"]
        assert returned["total_quantity"] == 1
        assert returned["total_amount"] == "15.00"
        assert len(returned["items"]) == 1
        assert body["movements"][0]["direction"] == "in"

        stock_resp = await client.get(
            f"/api/v1/products/{product['id']}/stock",
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert stock_resp.status_code == 200, stock_resp.text
        stock = stock_resp.json()
        assert stock["quantity_on_hand"] == 4


@pytest.mark.asyncio
async def test_record_return_cannot_exceed_remaining_quantity(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        returns_token, manager_token = await _login_returns_and_manager(async_session, client)
        product = await _create_product(client, manager_token)
        await _add_stock(client, manager_token, product["id"], quantity=5)
        sale = await _record_sale(client, returns_token, product_id=product["id"], quantity=2)
        sale_item_id = sale["items"][0]["id"]

        first = await client.post(
            "/api/v1/returns",
            json={
                "sale_id": sale["id"],
                "lines": [
                    {
                        "sale_item_id": sale_item_id,
                        "quantity": 1,
                    }
                ],
            },
            headers={"Authorization": f"Bearer {returns_token}"},
        )
        assert first.status_code == 201, first.text

        second = await client.post(
            "/api/v1/returns",
            json={
                "sale_id": sale["id"],
                "lines": [
                    {
                        "sale_item_id": sale_item_id,
                        "quantity": 2,
                    }
                ],
            },
            headers={"Authorization": f"Bearer {returns_token}"},
        )
        assert second.status_code == 400, second.text
        payload = second.json()
        assert payload["code"] == "validation_error"


@pytest.mark.asyncio
async def test_record_return_unknown_sale_returns_404(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        returns_token = await _register_and_login(async_session, client)

        resp = await client.post(
            "/api/v1/returns",
            json={
                "sale_id": f"01{uuid4().hex[:24]}",
                "lines": [
                    {
                        "sale_item_id": f"01{uuid4().hex[:24]}",
                        "quantity": 1,
                    }
                ],
            },
            headers={"Authorization": f"Bearer {returns_token}"},
        )
        assert resp.status_code == 404, resp.text
        payload = resp.json()
        assert payload["code"] == "not_found"


@pytest.mark.asyncio
async def test_record_return_rejects_unknown_sale_item(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        returns_token, manager_token = await _login_returns_and_manager(async_session, client)
        product = await _create_product(client, manager_token)
        await _add_stock(client, manager_token, product["id"], quantity=3)
        sale = await _record_sale(client, returns_token, product_id=product["id"], quantity=1)

        resp = await client.post(
            "/api/v1/returns",
            json={
                "sale_id": sale["id"],
                "lines": [
                    {
                        "sale_item_id": f"01{uuid4().hex[:24]}",
                        "quantity": 1,
                    }
                ],
            },
            headers={"Authorization": f"Bearer {returns_token}"},
        )
        assert resp.status_code == 400, resp.text
        payload = resp.json()
        assert payload["code"] == "validation_error"


@pytest.mark.asyncio
async def test_list_returns_requires_authentication():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/returns")
        assert resp.status_code == 401
        body = resp.json()
        assert body["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_list_returns_returns_history(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        returns_token, manager_token = await _login_returns_and_manager(async_session, client)
        product = await _create_product(client, manager_token)
        await _add_stock(client, manager_token, product["id"], quantity=4)
        sale = await _record_sale(client, returns_token, product_id=product["id"], quantity=2)
        sale_item_id = sale["items"][0]["id"]

        first_resp = await client.post(
            "/api/v1/returns",
            json={
                "sale_id": sale["id"],
                "lines": [
                    {
                        "sale_item_id": sale_item_id,
                        "quantity": 1,
                    }
                ],
            },
            headers={"Authorization": f"Bearer {returns_token}"},
        )
        assert first_resp.status_code == 201, first_resp.text
        first_return_id = first_resp.json()["return"]["id"]

        second_resp = await client.post(
            "/api/v1/returns",
            json={
                "sale_id": sale["id"],
                "lines": [
                    {
                        "sale_item_id": sale_item_id,
                        "quantity": 1,
                    }
                ],
            },
            headers={"Authorization": f"Bearer {returns_token}"},
        )
        assert second_resp.status_code == 201, second_resp.text
        second_return = second_resp.json()["return"]

        list_resp = await client.get(
            "/api/v1/returns",
            params={"sale_id": sale["id"], "limit": 1},
            headers={"Authorization": f"Bearer {returns_token}"},
        )
        assert list_resp.status_code == 200, list_resp.text
        listing = list_resp.json()
        assert listing["meta"] == {"page": 1, "limit": 1, "total": 2, "pages": 2}
        assert len(listing["items"]) == 1
        assert listing["items"][0]["id"] == second_return["id"]
        assert listing["items"][0]["total_quantity"] == second_return["total_quantity"]

        page_two = await client.get(
            "/api/v1/returns",
            params={"sale_id": sale["id"], "page": 2, "limit": 1},
            headers={"Authorization": f"Bearer {returns_token}"},
        )
        assert page_two.status_code == 200, page_two.text
        listing_two = page_two.json()
        assert len(listing_two["items"]) == 1
        assert listing_two["items"][0]["id"] == first_return_id


@pytest.mark.asyncio
async def test_get_return_returns_detail(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        returns_token, manager_token = await _login_returns_and_manager(async_session, client)
        product = await _create_product(client, manager_token)
        await _add_stock(client, manager_token, product["id"], quantity=3)
        sale = await _record_sale(client, returns_token, product_id=product["id"], quantity=1, unit_price="18.00")
        sale_item_id = sale["items"][0]["id"]

        record_resp = await client.post(
            "/api/v1/returns",
            json={
                "sale_id": sale["id"],
                "lines": [
                    {
                        "sale_item_id": sale_item_id,
                        "quantity": 1,
                    }
                ],
            },
            headers={"Authorization": f"Bearer {returns_token}"},
        )
        assert record_resp.status_code == 201, record_resp.text
        return_id = record_resp.json()["return"]["id"]

        detail_resp = await client.get(
            f"/api/v1/returns/{return_id}",
            headers={"Authorization": f"Bearer {returns_token}"},
        )
        assert detail_resp.status_code == 200, detail_resp.text
        detail = detail_resp.json()
        assert detail["id"] == return_id
        assert detail["sale_id"] == sale["id"]
        assert detail["total_amount"] == "18.00"
        assert len(detail["items"]) == 1
        assert detail["items"][0]["sale_item_id"] == sale_item_id


@pytest.mark.asyncio
async def test_get_return_requires_authentication(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        returns_token, manager_token = await _login_returns_and_manager(async_session, client)
        product = await _create_product(client, manager_token)
        await _add_stock(client, manager_token, product["id"], quantity=1)
        sale = await _record_sale(client, returns_token, product_id=product["id"], quantity=1)
        sale_item_id = sale["items"][0]["id"]

        record_resp = await client.post(
            "/api/v1/returns",
            json={
                "sale_id": sale["id"],
                "lines": [
                    {
                        "sale_item_id": sale_item_id,
                        "quantity": 1,
                    }
                ],
            },
            headers={"Authorization": f"Bearer {returns_token}"},
        )
        assert record_resp.status_code == 201, record_resp.text
        return_id = record_resp.json()["return"]["id"]

        resp = await client.get(f"/api/v1/returns/{return_id}")
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_return_unknown_returns_404(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _register_and_login(async_session, client)
        resp = await client.get(
            "/api/v1/returns/01HZZUNKNOWNRETURN",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404, resp.text
        payload = resp.json()
        assert payload["code"] == "not_found"
