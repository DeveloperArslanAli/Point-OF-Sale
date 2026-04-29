from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

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


async def _create_customer(
    client: AsyncClient,
    token: str,
    *,
    email: str | None = None,
    first_name: str = "Jane",
    last_name: str = "Doe",
    phone: str = "+15551234",
) -> dict:
    payload = {
        "first_name": first_name,
        "last_name": last_name,
        "email": email or f"{uuid4().hex[:8]}@example.com",
        "phone": phone,
    }
    resp = await client.post(
        "/api/v1/customers",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_product(
    client: AsyncClient,
    token: str,
    *,
    name: str = "Prod1",
    sku: str | None = None,
    retail_price: str = "10.00",
) -> dict:
    unique_sku = sku or f"SKU{uuid4().hex[:8]}"
    resp = await client.post(
        "/api/v1/products",
        json={
            "name": name,
            "sku": unique_sku,
            "retail_price": retail_price,
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
    customer_id: str,
    product_id: str,
    quantity: int,
    unit_price: str,
    currency: str = "USD",
    payments: list[dict] | None = None,
) -> dict:
    payload = {
        "currency": currency,
        "customer_id": customer_id,
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


@pytest.mark.asyncio
async def test_register_customer_creates_record_and_allows_fetching_by_id(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _register_and_login(async_session, client)

        unique = uuid4().hex[:8]
        payload = {
            "first_name": "jane",
            "last_name": "doe",
            "email": f"{unique}@EXAMPLE.com",
            "phone": "  +15550001111  ",
        }
        resp = await client.post(
            "/api/v1/customers",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()

        assert body["first_name"] == "Jane"
        assert body["last_name"] == "Doe"
        assert body["email"] == f"{unique}@example.com"
        assert body["phone"] == "+15550001111"
        assert body["active"] is True
        assert body["full_name"] == "Jane Doe"
        assert body["version"] == 0

        customer_id = body["id"]
        fetch = await client.get(
            f"/api/v1/customers/{customer_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert fetch.status_code == 200, fetch.text
        detail = fetch.json()
        assert detail["id"] == customer_id
        assert detail["email"] == f"{unique}@example.com"
        assert detail["full_name"] == "Jane Doe"
        assert detail["version"] == 0
        assert detail["active"] is True


@pytest.mark.asyncio
async def test_register_customer_rejects_duplicate_email_case_insensitive(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _register_and_login(async_session, client)
        existing_email = f"dup_{uuid4().hex[:8]}@example.com"
        await _create_customer(client, token, email=existing_email)

        resp = await client.post(
            "/api/v1/customers",
            json={
                "first_name": "John",
                "last_name": "Smith",
                "email": existing_email.upper(),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409, resp.text
        payload = resp.json()
        assert payload["code"] == "conflict"
        assert payload["trace_id"] == resp.headers.get("X-Trace-Id")


@pytest.mark.asyncio
async def test_list_customers_supports_search_and_pagination(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _register_and_login(async_session, client)

        marker = uuid4().hex[:6]
        await _create_customer(client, token, first_name=f"Alice{marker}", last_name=f"Zephyr-{marker}")
        await _create_customer(client, token, first_name=f"Bob{marker}", last_name=f"Yellow-{marker}")
        await _create_customer(client, token, first_name=f"Charlie{marker}", last_name=f"Xavier-{marker}")

        page1 = await client.get(
            "/api/v1/customers",
            params={"page": 1, "limit": 2, "search": marker},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert page1.status_code == 200, page1.text
        data1 = page1.json()
        assert data1["meta"] == {"page": 1, "limit": 2, "total": 3, "pages": 2}
        assert len(data1["items"]) == 2
        assert all("version" in item for item in data1["items"])

        page2 = await client.get(
            "/api/v1/customers",
            params={"page": 2, "limit": 2, "search": marker},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert page2.status_code == 200, page2.text
        data2 = page2.json()
        assert data2["meta"] == {"page": 2, "limit": 2, "total": 3, "pages": 2}
        assert len(data2["items"]) == 1
        assert "version" in data2["items"][0]

        search_resp = await client.get(
            "/api/v1/customers",
            params={"search": f"alice{marker.lower()}"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert search_resp.status_code == 200, search_resp.text
        search_data = search_resp.json()
        assert search_data["meta"]["total"] == 1
        assert search_data["items"][0]["first_name"].lower() == f"alice{marker}"


@pytest.mark.asyncio
async def test_update_customer_modifies_details_and_increments_version(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _register_and_login(async_session, client)

        customer = await _create_customer(
            client,
            token,
            first_name="alice",
            last_name="smith",
            email=f"alice_{uuid4().hex[:8]}@example.com",
            phone="+15550001122",
        )

        new_email = f"updated_{uuid4().hex[:8]}@Example.com"
        resp = await client.patch(
            f"/api/v1/customers/{customer['id']}",
            json={
                "expected_version": customer["version"],
                "first_name": "alicia",
                "last_name": "SMITHERS",
                "email": new_email,
                "phone": " +15559998888 ",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["first_name"] == "Alicia"
        assert body["last_name"] == "Smithers"
        assert body["email"] == new_email.strip().lower()
        assert body["phone"] == "+15559998888"
        assert body["version"] == customer["version"] + 2

        detail = await client.get(
            f"/api/v1/customers/{customer['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert detail.status_code == 200, detail.text
        detail_body = detail.json()
        assert detail_body["version"] == body["version"]
        assert detail_body["full_name"] == "Alicia Smithers"


@pytest.mark.asyncio
async def test_update_customer_rejects_duplicate_email(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _register_and_login(async_session, client)

        primary = await _create_customer(client, token)
        secondary = await _create_customer(client, token)

        resp = await client.patch(
            f"/api/v1/customers/{secondary['id']}",
            json={
                "expected_version": secondary["version"],
                "email": primary["email"],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409, resp.text
        payload = resp.json()
        assert payload["code"] == "conflict"


@pytest.mark.asyncio
async def test_update_customer_requires_changes(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _register_and_login(async_session, client)
        customer = await _create_customer(client, token)

        resp = await client.patch(
            f"/api/v1/customers/{customer['id']}",
            json={"expected_version": customer["version"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400, resp.text
        payload = resp.json()
        assert payload["code"] == "validation_error"


@pytest.mark.asyncio
async def test_update_customer_detects_stale_version(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _register_and_login(async_session, client)
        customer = await _create_customer(client, token)

        first_update = await client.patch(
            f"/api/v1/customers/{customer['id']}",
            json={
                "expected_version": customer["version"],
                "phone": "+15556667777",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert first_update.status_code == 200, first_update.text

        resp = await client.patch(
            f"/api/v1/customers/{customer['id']}",
            json={
                "expected_version": customer["version"],
                "phone": "+15557778888",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409, resp.text
        payload = resp.json()
        assert payload["code"] == "conflict"


@pytest.mark.asyncio
async def test_deactivate_customer_sets_inactive_and_blocks_repeat(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _register_and_login(async_session, client)
        customer = await _create_customer(client, token)

        deactivate_resp = await client.post(
            f"/api/v1/customers/{customer['id']}/deactivate",
            json={"expected_version": customer["version"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert deactivate_resp.status_code == 200, deactivate_resp.text
        body = deactivate_resp.json()
        assert body["active"] is False
        assert body["version"] == customer["version"] + 1

        verify = await client.get(
            f"/api/v1/customers/{customer['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert verify.status_code == 200, verify.text
        detail = verify.json()
        assert detail["active"] is False

        repeat = await client.post(
            f"/api/v1/customers/{customer['id']}/deactivate",
            json={"expected_version": body["version"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert repeat.status_code == 400, repeat.text
        repeat_payload = repeat.json()
        assert repeat_payload["code"] == "validation_error"


@pytest.mark.asyncio
async def test_get_customer_returns_404_for_unknown_id(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _register_and_login(async_session, client)

        resp = await client.get(
            "/api/v1/customers/01HZZUNKNOWNCUSTOMER",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404, resp.text
        payload = resp.json()
        assert payload["code"] == "not_found"


@pytest.mark.asyncio
async def test_list_customer_sales_returns_paginated_history(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sales_token = await _register_and_login(async_session, client)
        manager_token = await _register_and_login(async_session, client, role=UserRole.MANAGER)
        customer = await _create_customer(client, sales_token)
        product = await _create_product(client, manager_token)
        await _add_stock(client, manager_token, product["id"], quantity=5)

        sale1 = await _record_sale(
            client,
            sales_token,
            customer_id=customer["id"],
            product_id=product["id"],
            quantity=1,
            unit_price="7.50",
        )
        sale2 = await _record_sale(
            client,
            sales_token,
            customer_id=customer["id"],
            product_id=product["id"],
            quantity=2,
            unit_price="5.00",
        )

        page1 = await client.get(
            f"/api/v1/customers/{customer['id']}/sales",
            params={"page": 1, "limit": 1},
            headers={"Authorization": f"Bearer {sales_token}"},
        )
        assert page1.status_code == 200, page1.text
        data1 = page1.json()
        assert data1["meta"] == {"page": 1, "limit": 1, "total": 2, "pages": 2}
        assert len(data1["items"]) == 1
        first_sale = data1["items"][0]
        assert first_sale["id"] == sale2["id"]
        assert first_sale["total_amount"] == sale2["total_amount"]
        assert len(first_sale["items"]) == 1

        page2 = await client.get(
            f"/api/v1/customers/{customer['id']}/sales",
            params={"page": 2, "limit": 1},
            headers={"Authorization": f"Bearer {sales_token}"},
        )
        assert page2.status_code == 200, page2.text
        data2 = page2.json()
        assert data2["meta"] == {"page": 2, "limit": 1, "total": 2, "pages": 2}
        assert len(data2["items"]) == 1
        assert data2["items"][0]["id"] == sale1["id"]


@pytest.mark.asyncio
async def test_list_customer_sales_unknown_customer_returns_404(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _register_and_login(async_session, client)

        resp = await client.get(
            "/api/v1/customers/01HZZUNKNOWNCUSTOMER/sales",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404, resp.text
        payload = resp.json()
        assert payload["code"] == "not_found"


@pytest.mark.asyncio
async def test_list_customer_sales_validates_pagination_inputs(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _register_and_login(async_session, client)
        customer = await _create_customer(client, token)

        invalid_page = await client.get(
            f"/api/v1/customers/{customer['id']}/sales",
            params={"page": 0},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert invalid_page.status_code == 422, invalid_page.text
        page_payload = invalid_page.json()
        assert page_payload["detail"][0]["loc"] == ["query", "page"]

        invalid_limit = await client.get(
            f"/api/v1/customers/{customer['id']}/sales",
            params={"limit": 0},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert invalid_limit.status_code == 422, invalid_limit.text
        limit_payload = invalid_limit.json()
        assert limit_payload["detail"][0]["loc"] == ["query", "limit"]


@pytest.mark.asyncio
async def test_get_customer_summary_requires_authentication():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/customers/01HZZUNKNOWN/summary")
        assert resp.status_code == 401
        body = resp.json()
        assert body["code"] == "unauthorized"
        assert body["trace_id"] == resp.headers.get("X-Trace-Id")


@pytest.mark.asyncio
async def test_get_customer_summary_returns_aggregates(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sales_token = await _register_and_login(async_session, client)
        manager_token = await _register_and_login(async_session, client, role=UserRole.MANAGER, label="manager")
        customer = await _create_customer(client, sales_token)
        product = await _create_product(client, manager_token, retail_price="20.00")
        await _add_stock(client, manager_token, product["id"], quantity=10)

        sale1 = await _record_sale(
            client,
            sales_token,
            customer_id=customer["id"],
            product_id=product["id"],
            quantity=2,
            unit_price="15.00",
        )
        sale2 = await _record_sale(
            client,
            sales_token,
            customer_id=customer["id"],
            product_id=product["id"],
            quantity=1,
            unit_price="12.50",
        )

        summary_resp = await client.get(
            f"/api/v1/customers/{customer['id']}/summary",
            headers={"Authorization": f"Bearer {sales_token}"},
        )
        assert summary_resp.status_code == 200, summary_resp.text
        summary = summary_resp.json()

        total_quantity = sale1["total_quantity"] + sale2["total_quantity"]
        lifetime_value = Decimal(sale1["total_amount"]) + Decimal(sale2["total_amount"])

        assert summary["customer_id"] == customer["id"]
        assert summary["currency"] == "USD"
        assert summary["total_sales"] == 2
        assert summary["total_quantity"] == total_quantity
        assert summary["lifetime_value"] == format(lifetime_value, "0.2f")
        assert summary["average_order_value"] == format(lifetime_value / Decimal(2), "0.2f")
        assert summary["last_sale_id"] == sale2["id"]
        assert summary["last_sale_amount"] == format(Decimal(sale2["total_amount"]), "0.2f")
        assert summary["first_purchase_at"] is not None
        assert summary["last_purchase_at"] is not None


@pytest.mark.asyncio
async def test_get_customer_summary_handles_no_sales(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _register_and_login(async_session, client)
        customer = await _create_customer(client, token)

        summary_resp = await client.get(
            f"/api/v1/customers/{customer['id']}/summary",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert summary_resp.status_code == 200, summary_resp.text
        summary = summary_resp.json()

        assert summary["customer_id"] == customer["id"]
        assert summary["total_sales"] == 0
        assert summary["total_quantity"] == 0
        assert summary["lifetime_value"] == "0.00"
        assert summary["average_order_value"] is None
        assert summary["currency"] is None
        assert summary["last_sale_id"] is None
        assert summary["last_sale_amount"] is None
        assert summary["first_purchase_at"] is None
        assert summary["last_purchase_at"] is None