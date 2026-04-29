import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.application.auth.use_cases.create_user import CreateUserInput, CreateUserUseCase
from app.domain.auth.entities import UserRole
from app.infrastructure.auth.password_hasher import PasswordHasher
from app.infrastructure.db.repositories.user_repository import UserRepository


async def _create_user(session, email: str, password: str, role: UserRole) -> None:
    use_case = CreateUserUseCase(UserRepository(session), PasswordHasher())
    await use_case.execute(CreateUserInput(email=email, password=password, role=role))
    await session.commit()


@pytest.mark.asyncio
async def test_cashier_cannot_create_product(async_session):
    email = f"cashier_{uuid.uuid4().hex[:8]}@example.com"
    password = "Password123!"

    await _create_user(async_session, email, password, UserRole.CASHIER)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert login.status_code == 200, login.text
        tokens = login.json()

        create_resp = await client.post(
            "/api/v1/products",
            json={
                "name": "Widget",
                "sku": f"SKU-{uuid.uuid4().hex[:6]}",
                "retail_price": "9.99",
                "purchase_price": "5.00",
                "currency": "USD",
            },
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )

        assert create_resp.status_code == 403
        payload = create_resp.json()
        assert payload["code"] == "insufficient_role"


@pytest.mark.asyncio
async def test_manager_can_create_product(async_session):
    email = f"manager_{uuid.uuid4().hex[:8]}@example.com"
    password = "Password123!"

    await _create_user(async_session, email, password, UserRole.MANAGER)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert login.status_code == 200, login.text
        tokens = login.json()

        create_resp = await client.post(
            "/api/v1/products",
            json={
                "name": "Gadget",
                "sku": f"SKU-{uuid.uuid4().hex[:6]}",
                "retail_price": "19.99",
                "purchase_price": "10.00",
                "currency": "USD",
            },
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )

        assert create_resp.status_code == 201, create_resp.text
        data = create_resp.json()
        assert data["name"] == "Gadget"
        assert data["sku"].startswith("SKU-")


@pytest.mark.asyncio
async def test_admin_can_create_cashier_user(async_session):
    admin_email = f"admin_{uuid.uuid4().hex[:8]}@example.com"
    cashier_email = f"cashier_{uuid.uuid4().hex[:8]}@example.com"
    password = "Password123!"

    await _create_user(async_session, admin_email, password, UserRole.ADMIN)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login = await client.post("/api/v1/auth/login", json={"email": admin_email, "password": password})
        assert login.status_code == 200, login.text
        admin_tokens = login.json()

        create_resp = await client.post(
            "/api/v1/auth/users",
            json={"email": cashier_email, "password": password, "role": "CASHIER"},
            headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
        )

        assert create_resp.status_code == 201, create_resp.text
        body = create_resp.json()
        assert body["email"] == cashier_email
        assert body["role"] == "CASHIER"
        assert body["active"] is True

        # New cashier can log in with provided credentials
        cashier_login = await client.post(
            "/api/v1/auth/login",
            json={"email": cashier_email, "password": password},
        )
        assert cashier_login.status_code == 200, cashier_login.text
