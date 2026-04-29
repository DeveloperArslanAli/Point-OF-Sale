from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, cast
from uuid import uuid4

import jwt

from app.core.settings import get_settings


class TokenProvider:
    def __init__(self, secret: str | None = None, issuer: str | None = None):
        s = get_settings()
        self.secret = secret or s.JWT_SECRET_KEY
        self.issuer = issuer or s.JWT_ISSUER
        self.access_minutes = s.ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_minutes = s.REFRESH_TOKEN_EXPIRE_MINUTES
        self.algorithm = s.JWT_ALGORITHM

    def _build_access_payload(
        self,
        subject: str,
        extra: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], datetime]:
        expire = datetime.now(tz=timezone.utc) + timedelta(minutes=self.access_minutes)
        payload = {"sub": subject, "exp": expire, "type": "access", "iss": self.issuer}
        if extra:
            payload.update(extra)
        return payload, expire

    def create_access_token(self, subject: str, extra: dict[str, Any] | None = None) -> str:
        payload, _ = self._build_access_payload(subject, extra)
        return jwt.encode(payload, self.secret, algorithm=self.algorithm)

    def create_refresh_token(self, subject: str, *, tenant_id: str | None = None) -> str:
        expire = datetime.now(tz=timezone.utc) + timedelta(minutes=self.refresh_minutes)
        payload: dict[str, Any] = {"sub": subject, "exp": expire, "type": "refresh", "iss": self.issuer}
        if tenant_id:
            payload["tenant_id"] = tenant_id
        return jwt.encode(payload, self.secret, algorithm=self.algorithm)

    def create_refresh_token_with_id(
        self,
        subject: str,
        *,
        token_id: str | None = None,
        tenant_id: str | None = None,
    ) -> tuple[str, str, datetime]:
        jti = token_id or str(uuid4())
        expire = datetime.now(tz=timezone.utc) + timedelta(minutes=self.refresh_minutes)
        payload: dict[str, Any] = {
            "sub": subject,
            "exp": expire,
            "type": "refresh",
            "iss": self.issuer,
            "jti": jti,
        }
        if tenant_id:
            payload["tenant_id"] = tenant_id
        token = jwt.encode(payload, self.secret, algorithm=self.algorithm)
        return token, jti, expire

    def decode_token(self, token: str) -> dict[str, Any]:
        payload = cast(
            dict[str, Any],
            jwt.decode(token, self.secret, algorithms=[self.algorithm], options={"require": ["exp", "sub"]}),
        )
        return payload


# Backwards compatible functions
_default_provider: TokenProvider | None = None


def _get_default() -> TokenProvider:  # pragma: no cover
    global _default_provider
    if _default_provider is None:
        _default_provider = TokenProvider()
    return _default_provider


def create_access_token(subject: str) -> str:  # pragma: no cover
    return _get_default().create_access_token(subject)


def create_refresh_token(subject: str) -> str:  # pragma: no cover
    return _get_default().create_refresh_token(subject)


def decode_token(token: str) -> dict[str, Any]:  # pragma: no cover
    return _get_default().decode_token(token)
