from __future__ import annotations

from dataclasses import dataclass

from app.application.auth.ports import (
    PasswordHasherPort,
    RefreshTokenRepositoryPort,
    TokenProviderPort,
    UserRepositoryPort,
)
from app.core.login_lockout import LoginLockoutService
from app.domain.auth.entities import RefreshToken
from app.domain.common.errors import UnauthorizedError


@dataclass
class LoginInput:
    email: str
    password: str
    ip_address: str | None = None  # For lockout tracking


@dataclass
class LoginOutput:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginUseCase:
    def __init__(
        self,
        repo: UserRepositoryPort,
        hasher: PasswordHasherPort,
        tokens: TokenProviderPort,
        refresh_tokens: RefreshTokenRepositoryPort,
        lockout_service: LoginLockoutService | None = None,
    ):
        self._repo = repo
        self._hasher = hasher
        self._tokens = tokens
        self._refresh_repo = refresh_tokens
        self._lockout = lockout_service

    async def execute(self, data: LoginInput) -> LoginOutput:
        # Check if account is locked
        if self._lockout and await self._lockout.is_locked(data.email):
            remaining = await self._lockout.get_lockout_remaining(data.email)
            raise UnauthorizedError(
                f"Account temporarily locked. Try again in {remaining or 'a few'} seconds.",
                code="auth.account_locked",
            )
        
        user = await self._repo.get_by_email(data.email)
        if not user:
            # Record failure even for non-existent users (prevent enumeration)
            if self._lockout:
                await self._lockout.record_failure(data.email, data.ip_address)
            raise UnauthorizedError("invalid credentials")
        
        if not user.active:
            raise UnauthorizedError("account is deactivated", code="auth.account_inactive")
        
        if not self._hasher.verify(data.password, user.password_hash):
            # Record failed attempt
            if self._lockout:
                await self._lockout.record_failure(data.email, data.ip_address)
            raise UnauthorizedError("invalid credentials")
        
        # Clear failures on successful login
        if self._lockout:
            await self._lockout.clear_failures(data.email)
        
        access = self._tokens.create_access_token(
            subject=user.id,
            extra={
                "role": user.role,
                "tenant_id": user.tenant_id,
            },
        )
        refresh_token, refresh_id, refresh_expires = self._tokens.create_refresh_token_with_id(
            subject=user.id,
            tenant_id=user.tenant_id,
        )
        entity = RefreshToken.issue(user_id=user.id, expires_at=refresh_expires, token_id=refresh_id)
        await self._refresh_repo.add(entity)
        return LoginOutput(access_token=access, refresh_token=refresh_token)