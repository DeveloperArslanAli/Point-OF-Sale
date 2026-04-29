from __future__ import annotations

from uuid import uuid4

from app.application.auth.use_cases.create_user import CreateUserInput, CreateUserUseCase
from app.domain.auth.entities import UserRole
from app.infrastructure.auth.password_hasher import PasswordHasher
from app.infrastructure.db.repositories.user_repository import UserRepository
from app.infrastructure.db.session import async_session_factory


async def create_user(async_session, email: str, password: str, role: UserRole) -> None:
    """Seed a user directly via the application layer with the desired role."""
    _ = async_session  # the fixture keeps DB configured; creation uses an isolated session
    async with async_session_factory.begin() as session:
        use_case = CreateUserUseCase(UserRepository(session), PasswordHasher())
        await use_case.execute(CreateUserInput(email=email, password=password, role=role))


async def create_user_and_login(async_session, client, email: str, password: str, role: UserRole) -> str:
    await create_user(async_session, email, password, role)
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


async def login_as(
    async_session,
    client,
    role: UserRole,
    *,
    email_prefix: str = "user",
    password: str = "Secretp@ss1",
) -> str:
    email = f"{email_prefix}_{role.value}_{uuid4().hex[:6]}@example.com"
    return await create_user_and_login(async_session, client, email, password, role)
