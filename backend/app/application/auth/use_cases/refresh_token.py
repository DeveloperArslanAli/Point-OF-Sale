from __future__ import annotations

from dataclasses import dataclass

import jwt

from app.application.auth.ports import (
    RefreshTokenRepositoryPort,
    TokenProviderPort,
    UserRepositoryPort,
)
from app.application.auth.use_cases.login import LoginOutput
from app.domain.auth.entities import RefreshToken
from app.domain.common.errors import TokenError, UnauthorizedError


@dataclass
class RefreshTokenInput:
    refresh_token: str


class RefreshTokenUseCase:
    def __init__(
        self,
        users: UserRepositoryPort,
        refresh_tokens: RefreshTokenRepositoryPort,
        tokens: TokenProviderPort,
    ):
        self._users = users
        self._refresh_repo = refresh_tokens
        self._tokens = tokens

    async def execute(self, data: RefreshTokenInput) -> LoginOutput:
        try:
            payload = self._tokens.decode_token(data.refresh_token)
        except jwt.PyJWTError as exc:  # includes expired signature, invalid signature, etc.
            raise TokenError("invalid token") from exc

        if payload.get("type") != "refresh":
            raise TokenError("invalid token type")

        user_id = payload.get("sub")
        if not user_id:
            raise TokenError("invalid token")

        token_id = payload.get("jti")
        if not token_id:
            raise TokenError("invalid token")

        stored = await self._refresh_repo.get_by_id(token_id)
        if stored is None:
            raise TokenError("invalid token")
        if stored.revoked or stored.replaced_by is not None:
            raise TokenError("token already revoked", code="token_revoked")
        if stored.user_id != user_id:
            raise TokenError("invalid token")
        if stored.is_expired():
            raise TokenError("token expired", code="token_expired")

        user = await self._users.get_by_id(user_id)
        if user is None or not user.active:
            raise UnauthorizedError("invalid user")

        access = self._tokens.create_access_token(
            subject=user.id,
            extra={
                "role": user.role,
                "tenant_id": user.tenant_id,
            },
        )
        new_refresh_value, new_refresh_id, new_refresh_exp = self._tokens.create_refresh_token_with_id(
            user.id,
            tenant_id=user.tenant_id,
        )
        replacement = RefreshToken.issue(user_id=user.id, expires_at=new_refresh_exp, token_id=new_refresh_id)
        await self._refresh_repo.revoke_and_replace(stored.id, replacement)

        return LoginOutput(access_token=access, refresh_token=new_refresh_value)
