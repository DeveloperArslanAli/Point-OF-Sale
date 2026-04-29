from __future__ import annotations

from datetime import UTC, datetime
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


async def _create_customer(client: AsyncClient, token: str) -> dict:
    resp = await client.post(
        "/api/v1/customers",
        json={
            "first_name": "Alice",
            "last_name": "Buyer",
            "email": f"alice_{uuid4().hex[:8]}@example.com",
            "phone": "+15550000000",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _deactivate_customer(client: AsyncClient, token: str, customer: dict) -> dict:
    resp = await client.post(
        f"/api/v1/customers/{customer['id']}/deactivate",
        json={"expected_version": customer["version"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _purchase_and_activate_gift_card(
    client: AsyncClient,
    token: str,
    *,
    amount: str = "50.00",
    currency: str = "USD",
) -> dict:
    purchase_resp = await client.post(
        "/api/v1/gift-cards/purchase",
        json={
            "amount": amount,
            "currency": currency,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert purchase_resp.status_code == 201, purchase_resp.text
    gift_card = purchase_resp.json()

    activate_resp = await client.post(
        "/api/v1/gift-cards/activate",
        json={"code": gift_card["code"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert activate_resp.status_code == 200, activate_resp.text
    return activate_resp.json()


async def _record_sale(
    client: AsyncClient,
    token: str,
    *,
    product_id: str,
    quantity: int,
    unit_price: str,
    currency: str = "USD",
    customer_id: str | None = None,
    payments: list[dict] | None = None,
) -> dict:
    payload: dict[str, object] = {
        "currency": currency,
        "lines": [
            {
                "product_id": product_id,
                "quantity": quantity,
                "unit_price": unit_price,
            }
        ],
    }
    if customer_id is not None:
        payload["customer_id"] = customer_id

    if payments is None:
        total_amount = Decimal(unit_price) * quantity
        payload["payments"] = [
            {
                "payment_method": "cash",
                "amount": str(total_amount),
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


async def _login_sales_and_manager(async_session, client: AsyncClient) -> tuple[str, str]:
    sales_token = await _register_and_login(async_session, client, role=UserRole.CASHIER)
    manager_token = await _register_and_login(async_session, client, role=UserRole.MANAGER)
    return sales_token, manager_token


@pytest.mark.asyncio
async def test_record_sale_decrements_inventory_and_returns_summary(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sales_token, manager_token = await _login_sales_and_manager(async_session, client)
        product = await _create_product(client, manager_token)
        await _add_stock(client, manager_token, product["id"], quantity=5)

        payload = {
            "currency": "USD",
            "lines": [
                {
                    "product_id": product["id"],
                    "quantity": 2,
                    "unit_price": "15.00",
                }
            ],
            "payments": [
                {
                    "payment_method": "cash",
                    "amount": "30.00",
                }
            ],
        }
        resp = await client.post(
            "/api/v1/sales",
            json=payload,
            headers={"Authorization": f"Bearer {sales_token}"},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()

        sale = body["sale"]
        assert sale["currency"] == "USD"
        assert sale["total_quantity"] == 2
        assert sale["total_amount"] == "30.00"
        assert len(sale["items"]) == 1
        item = sale["items"][0]
        assert sale["customer_id"] is None
        assert item["product_id"] == product["id"]
        assert item["unit_price"] == "15.00"
        assert item["line_total"] == "30.00"
        assert sale["closed_at"] is not None
        assert datetime.fromisoformat(sale["created_at"]) <= datetime.fromisoformat(sale["closed_at"])

        movements = body["movements"]
        assert len(movements) == 1
        movement = movements[0]
        assert movement["product_id"] == product["id"]
        assert movement["direction"] == "out"
        assert movement["quantity"] == 2
        assert movement["reason"] == "sale"

        stock_resp = await client.get(
            f"/api/v1/products/{product['id']}/stock",
            headers={"Authorization": f"Bearer {manager_token}"},
        )

        assert stock_resp.status_code == 200, stock_resp.text
        stock = stock_resp.json()
        assert stock["quantity_on_hand"] == 3


@pytest.mark.asyncio
async def test_record_sale_with_customer_links_sale_to_customer(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sales_token, manager_token = await _login_sales_and_manager(async_session, client)
        product = await _create_product(client, manager_token)
        await _add_stock(client, manager_token, product["id"], quantity=3)
        customer = await _create_customer(client, sales_token)

        payload = {
            "currency": "USD",
            "customer_id": customer["id"],
            "lines": [
                {
                    "product_id": product["id"],
                    "quantity": 1,
                    "unit_price": "12.50",
                }
            ],
            "payments": [
                {
                    "payment_method": "cash",
                    "amount": "12.50",
                }
            ],
        }
        resp = await client.post(
            "/api/v1/sales",
            json=payload,
            headers={"Authorization": f"Bearer {sales_token}"},
        )
        assert resp.status_code == 201, resp.text
        sale = resp.json()["sale"]
        assert sale["customer_id"] == customer["id"]
        assert sale["total_amount"] == "12.50"
        assert sale["total_quantity"] == 1


@pytest.mark.asyncio
async def test_record_sale_rejects_unknown_customer(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sales_token, manager_token = await _login_sales_and_manager(async_session, client)
        product = await _create_product(client, manager_token)
        await _add_stock(client, manager_token, product["id"], quantity=2)

        resp = await client.post(
            "/api/v1/sales",
            json={
                "currency": "USD",
                "customer_id": f"01{uuid4().hex[:24]}",
                "lines": [
                    {
                        "product_id": product["id"],
                        "quantity": 1,
                        "unit_price": "9.99",
                    }
                ],
                "payments": [
                    {
                        "payment_method": "cash",
                        "amount": "9.99",
                    }
                ],
            },
            headers={"Authorization": f"Bearer {sales_token}"},
        )
        assert resp.status_code == 404, resp.text
        payload = resp.json()
        assert payload["code"] == "not_found"


@pytest.mark.asyncio
async def test_record_sale_rejects_inactive_customer(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sales_token, manager_token = await _login_sales_and_manager(async_session, client)
        product = await _create_product(client, manager_token)
        await _add_stock(client, manager_token, product["id"], quantity=2)
        customer = await _create_customer(client, sales_token)
        inactive = await _deactivate_customer(client, sales_token, customer)

        resp = await client.post(
            "/api/v1/sales",
            json={
                "currency": "USD",
                "customer_id": inactive["id"],
                "lines": [
                    {
                        "product_id": product["id"],
                        "quantity": 1,
                        "unit_price": "9.99",
                    }
                ],
                "payments": [
                    {
                        "payment_method": "cash",
                        "amount": "9.99",
                    }
                ],
            },
            headers={"Authorization": f"Bearer {sales_token}"},
        )
        assert resp.status_code == 400, resp.text
        payload = resp.json()
        assert payload["code"] == "validation_error"


@pytest.mark.asyncio
async def test_record_sale_insufficient_stock_returns_error(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sales_token, manager_token = await _login_sales_and_manager(async_session, client)
        product = await _create_product(client, manager_token)
        await _add_stock(client, manager_token, product["id"], quantity=1)

        resp = await client.post(
            "/api/v1/sales",
            json={
                "currency": "USD",
                "lines": [
                    {
                        "product_id": product["id"],
                        "quantity": 5,
                        "unit_price": "10.00",
                    }
                ],
                "payments": [
                    {
                        "payment_method": "cash",
                        "amount": "50.00",
                    }
                ],
            },
            headers={"Authorization": f"Bearer {sales_token}"},
        )
        assert resp.status_code == 400, resp.text
        payload = resp.json()
        assert payload["code"] == "validation_error"


@pytest.mark.asyncio
async def test_record_sale_requires_existing_product(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sales_token = await _register_and_login(async_session, client, role=UserRole.CASHIER)

        resp = await client.post(
            "/api/v1/sales",
            json={
                "lines": [
                    {
                        "product_id": "01HZZINVALIDPRODUCTID9",
                        "quantity": 1,
                        "unit_price": "12.00",
                    }
                ],
                "payments": [
                    {
                        "payment_method": "cash",
                        "amount": "12.00",
                    }
                ],
            },
            headers={"Authorization": f"Bearer {sales_token}"},
        )
        assert resp.status_code == 404, resp.text
        payload = resp.json()
        assert payload["code"] == "not_found"


@pytest.mark.asyncio
async def test_list_sales_supports_filters(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sales_token, manager_token = await _login_sales_and_manager(async_session, client)
        product = await _create_product(client, manager_token)
        await _add_stock(client, manager_token, product["id"], quantity=10)
        customer = await _create_customer(client, sales_token)

        baseline_resp = await client.get(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {sales_token}"},
        )
        assert baseline_resp.status_code == 200, baseline_resp.text
        baseline_total = baseline_resp.json()["meta"]["total"]

        marker = datetime.now(UTC)
        sale_with_customer = await _record_sale(
            client,
            sales_token,
            product_id=product["id"],
            quantity=3,
            unit_price="14.00",
            customer_id=customer["id"],
        )
        await _record_sale(
            client,
            sales_token,
            product_id=product["id"],
            quantity=2,
            unit_price="11.50",
        )

        list_resp = await client.get(
            "/api/v1/sales",
            headers={"Authorization": f"Bearer {sales_token}"},
        )
        assert list_resp.status_code == 200, list_resp.text
        body = list_resp.json()
        assert body["meta"]["total"] >= baseline_total + 2
        ids = {item["id"] for item in body["items"]}
        assert sale_with_customer["id"] in ids

        filter_resp = await client.get(
            "/api/v1/sales",
            params={
                "customer_id": customer["id"],
                "date_from": marker.isoformat().replace("+00:00", "Z"),
            },
            headers={"Authorization": f"Bearer {sales_token}"},
        )
        assert filter_resp.status_code == 200, filter_resp.text
        filtered = filter_resp.json()
        assert filtered["meta"]["total"] >= 1
        assert all(item["customer_id"] == customer["id"] for item in filtered["items"])


@pytest.mark.asyncio
async def test_record_sale_with_gift_card_payment_redeems_balance(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sales_token, manager_token = await _login_sales_and_manager(async_session, client)
        product = await _create_product(client, manager_token)
        await _add_stock(client, manager_token, product["id"], quantity=5)

        gift_card = await _purchase_and_activate_gift_card(
            client,
            manager_token,
            amount="50.00",
            currency="USD",
        )

        sale_total = Decimal("20.00")
        sale_resp = await client.post(
            "/api/v1/sales",
            json={
                "currency": "USD",
                "lines": [
                    {
                        "product_id": product["id"],
                        "quantity": 2,
                        "unit_price": "10.00",
                    }
                ],
                "payments": [
                    {
                        "payment_method": "gift_card",
                        "amount": str(sale_total),
                        "gift_card_code": gift_card["code"],
                    }
                ],
            },
            headers={"Authorization": f"Bearer {sales_token}"},
        )
        assert sale_resp.status_code == 201, sale_resp.text
        sale_body = sale_resp.json()["sale"]
        assert sale_body["total_amount"] == str(sale_total)
        assert sale_body["payments"], "Expected payments in sale response"
        payment = sale_body["payments"][0]
        assert payment["payment_method"] == "gift_card"
        assert payment["gift_card_id"] == gift_card["id"]
        assert payment["gift_card_code"] == gift_card["code"]

        balance_resp = await client.get(
            f"/api/v1/gift-cards/{gift_card['code']}/balance",
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert balance_resp.status_code == 200, balance_resp.text
        balance = balance_resp.json()
        assert Decimal(str(balance["current_balance"])) == Decimal("30.00")
        assert balance["is_usable"] is True


@pytest.mark.asyncio
async def test_record_sale_split_payment_gift_card_and_cash(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sales_token, manager_token = await _login_sales_and_manager(async_session, client)
        product = await _create_product(client, manager_token)
        await _add_stock(client, manager_token, product["id"], quantity=4)

        gift_card = await _purchase_and_activate_gift_card(
            client,
            manager_token,
            amount="25.00",
            currency="USD",
        )

        sale_resp = await client.post(
            "/api/v1/sales",
            json={
                "currency": "USD",
                "lines": [
                    {
                        "product_id": product["id"],
                        "quantity": 2,
                        "unit_price": "15.00",
                    }
                ],
                "payments": [
                    {
                        "payment_method": "gift_card",
                        "amount": "25.00",
                        "gift_card_code": gift_card["code"],
                    },
                    {
                        "payment_method": "cash",
                        "amount": "5.00",
                    },
                ],
            },
            headers={"Authorization": f"Bearer {sales_token}"},
        )
        assert sale_resp.status_code == 201, sale_resp.text
        sale = sale_resp.json()["sale"]

        assert sale["total_amount"] == "30.00"
        assert len(sale["payments"]) == 2

        gc_payment = next(p for p in sale["payments"] if p["payment_method"] == "gift_card")
        cash_payment = next(p for p in sale["payments"] if p["payment_method"] == "cash")

        assert gc_payment["gift_card_id"] == gift_card["id"]
        assert gc_payment["gift_card_code"] == gift_card["code"]
        assert cash_payment["reference_number"] is None

        balance_resp = await client.get(
            f"/api/v1/gift-cards/{gift_card['code']}/balance",
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert balance_resp.status_code == 200, balance_resp.text
        balance = balance_resp.json()
        assert Decimal(str(balance["current_balance"])) == Decimal("0")
        assert balance["status"] == "redeemed"
        assert balance["is_usable"] is False


@pytest.mark.asyncio
async def test_get_sale_returns_detail(async_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        sales_token, manager_token = await _login_sales_and_manager(async_session, client)
        product = await _create_product(client, manager_token)
        await _add_stock(client, manager_token, product["id"], quantity=4)

        sale = await _record_sale(
            client,
            sales_token,
            product_id=product["id"],
            quantity=2,
            unit_price="13.75",
        )

        resp = await client.get(
            f"/api/v1/sales/{sale['id']}",
            headers={"Authorization": f"Bearer {sales_token}"},
        )
        assert resp.status_code == 200, resp.text
        detail = resp.json()
        assert detail["id"] == sale["id"]
        assert detail["total_amount"] == sale["total_amount"]
        assert len(detail["items"]) == 1
        assert detail["items"][0]["product_id"] == product["id"]