from __future__ import annotations

from typing import Awaitable, Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.auth.use_cases.get_current_user import (
    GetCurrentUserInput,
    GetCurrentUserUseCase,
)
from app.core.settings import get_settings
from app.domain.auth.entities import User, UserRole
from app.domain.common.errors import RoleForbiddenError, TokenError, UnauthorizedError
from app.infrastructure.auth.token_provider import TokenProvider
from app.infrastructure.db.repositories.user_repository import UserRepository
from app.infrastructure.db.session import get_session

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedError("not authenticated")
    token = credentials.credentials
    settings = get_settings()
    provider = TokenProvider(secret=settings.JWT_SECRET_KEY, issuer=getattr(settings, "JWT_ISSUER", "pos-backend"))
    try:
        payload = provider.decode_token(token)
    except Exception:  # broad: jwt.InvalidTokenError etc.
        raise TokenError("invalid token") from None
    if payload.get("type") != "access":
        raise TokenError("invalid token type")
    sub = payload.get("sub")
    if not sub:
        raise TokenError("invalid token subject")
    repo = UserRepository(session)
    use_case = GetCurrentUserUseCase(repo)
    return await use_case.execute(GetCurrentUserInput(user_id=sub))


def require_roles(*roles: UserRole) -> Callable[..., Awaitable[User]]:
    async def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise RoleForbiddenError()
        return user

    return dependency


# Role groupings shared by API routers.
#
# The assumptions here follow current domain guidance:
# - Catalog and inventory mutations sit with managers or dedicated inventory staff.
# - Sales and returns flows stay open to cashier-level users.
# - Purchasing mirrors inventory permissions while still granting managers control.
# - Auditors receive read-only access alongside managers/admins.

ADMIN_ROLE: tuple[UserRole, ...] = (UserRole.ADMIN,)
MANAGEMENT_ROLES: tuple[UserRole, ...] = (UserRole.ADMIN, UserRole.MANAGER)
MANAGER_ROLES: tuple[UserRole, ...] = MANAGEMENT_ROLES  # Alias for consistency
INVENTORY_ROLES: tuple[UserRole, ...] = (UserRole.ADMIN, UserRole.MANAGER, UserRole.INVENTORY)
SALES_ROLES: tuple[UserRole, ...] = (UserRole.ADMIN, UserRole.MANAGER, UserRole.CASHIER)
RETURNS_ROLES: tuple[UserRole, ...] = SALES_ROLES
PURCHASING_ROLES: tuple[UserRole, ...] = (UserRole.ADMIN, UserRole.MANAGER, UserRole.INVENTORY)
AUDIT_ROLES: tuple[UserRole, ...] = (UserRole.ADMIN, UserRole.MANAGER, UserRole.AUDITOR)
ALL_AUTHENTICATED_ROLES: tuple[UserRole, ...] = tuple(UserRole)
