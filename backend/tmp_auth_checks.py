import asyncio
import uuid
from httpx import ASGITransport, AsyncClient
from app.api.main import app
from app.application.auth.use_cases.create_user import CreateUserInput, CreateUserUseCase
from app.domain.auth.entities import UserRole
from app.infrastructure.auth.password_hasher import PasswordHasher
from app.infrastructure.db.repositories.user_repository import UserRepository
from app.infrastructure.db.session import async_session_factory

ADMIN_EMAIL = f"check_admin_{uuid.uuid4().hex[:6]}@example.com"
PASSWORD = "Password123!"

async def ensure_admin() -> None:
    async with async_session_factory() as session:
        repo = UserRepository(session)
        existing = await repo.get_by_email(ADMIN_EMAIL)
        if existing:
            return
        use_case = CreateUserUseCase(repo, PasswordHasher())
        await use_case.execute(CreateUserInput(email=ADMIN_EMAIL, password=PASSWORD, role=UserRole.ADMIN))
        await session.commit()


def pretty(label: str, status: int, body) -> None:
    print(f"{label} -> {status}: {body}")


async def main() -> None:
    await ensure_admin()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login = await client.post("/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": PASSWORD})
        pretty("login", login.status_code, login.json() if login.headers.get("content-type", "").startswith("application/json") else login.text)
        tokens = login.json()
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        me = await client.get("/api/v1/auth/me", headers=headers)
        pretty("me", me.status_code, me.json() if me.headers.get("content-type", "").startswith("application/json") else me.text)

        refresh = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens['refresh_token']})
        pretty("refresh", refresh.status_code, refresh.json() if refresh.headers.get("content-type", "").startswith("application/json") else refresh.text)

        # Admin smoke: products list should be allowed
        products_admin = await client.get("/api/v1/products", headers=headers)
        pretty("products_admin", products_admin.status_code, products_admin.json() if products_admin.headers.get("content-type", "").startswith("application/json") else products_admin.text)

        # Weak password should return 400 with auth.weak_password
        weak_email = f"weak_{uuid.uuid4().hex[:6]}@example.com"
        weak_resp = await client.post(
            "/api/v1/auth/users",
            json={"email": weak_email, "password": "short", "role": "CASHIER"},
            headers=headers,
        )
        pretty("create_weak", weak_resp.status_code, weak_resp.json() if weak_resp.headers.get("content-type", "").startswith("application/json") else weak_resp.text)

        # Strong password should create cashier and allow login
        strong_email = f"cashier_{uuid.uuid4().hex[:6]}@example.com"
        strong_pass = "StrongPass123!"
        strong_resp = await client.post(
            "/api/v1/auth/users",
            json={"email": strong_email, "password": strong_pass, "role": "CASHIER"},
            headers=headers,
        )
        pretty("create_strong", strong_resp.status_code, strong_resp.json() if strong_resp.headers.get("content-type", "").startswith("application/json") else strong_resp.text)

        if strong_resp.status_code == 201:
            cashier_login = await client.post(
                "/api/v1/auth/login",
                json={"email": strong_email, "password": strong_pass},
            )
            pretty("cashier_login", cashier_login.status_code, cashier_login.json() if cashier_login.headers.get("content-type", "").startswith("application/json") else cashier_login.text)

            cashier_tokens = cashier_login.json()
            cashier_headers = {"Authorization": f"Bearer {cashier_tokens['access_token']}"}

            # Cashier smoke: products list should be allowed (read)
            products_cashier = await client.get("/api/v1/products", headers=cashier_headers)
            pretty("products_cashier", products_cashier.status_code, products_cashier.json() if products_cashier.headers.get("content-type", "").startswith("application/json") else products_cashier.text)

            # Cashier create product should be forbidden
            create_payload = {
                "name": "Widget",
                "sku": f"SKU-{uuid.uuid4().hex[:6]}",
                "retail_price": "10.00",
                "purchase_price": "5.00",
                "currency": "USD",
            }
            product_cashier = await client.post(
                "/api/v1/products",
                json=create_payload,
                headers=cashier_headers,
            )
            pretty("create_product_cashier", product_cashier.status_code, product_cashier.json() if product_cashier.headers.get("content-type", "").startswith("application/json") else product_cashier.text)

            # Admin create product should succeed
            product_admin = await client.post(
                "/api/v1/products",
                json={**create_payload, "sku": f"SKU-{uuid.uuid4().hex[:6]}"},
                headers=headers,
            )
            pretty("create_product_admin", product_admin.status_code, product_admin.json() if product_admin.headers.get("content-type", "").startswith("application/json") else product_admin.text)

if __name__ == "__main__":
    asyncio.run(main())
