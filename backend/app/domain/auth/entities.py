from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import ClassVar
from uuid import uuid4

from app.domain.common.errors import ValidationError
from app.domain.common.identifiers import new_ulid


class UserRole(str, Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    CASHIER = "CASHIER"
    INVENTORY = "INVENTORY"
    AUDITOR = "AUDITOR"


@dataclass(slots=True)
class User:
    id: str
    email: str
    password_hash: str
    role: UserRole
    active: bool
    tenant_id: str | None
    created_at: datetime
    updated_at: datetime
    version: int = 0

    EMAIL_MAX: ClassVar[int] = 255

    @staticmethod
    def create(
        email: str,
        password_hash: str,
        role: UserRole = UserRole.CASHIER,
        tenant_id: str | None = None,
    ) -> User:
        norm = User._normalize_email(email)
        if not password_hash or len(password_hash) < 10:  # argon2 hashes will be much longer
            raise ValidationError("Password hash invalid", code="user.invalid_password_hash")
        return User(
            id=new_ulid(),
            email=norm,
            password_hash=password_hash,
            role=role,
            active=True,
            tenant_id=tenant_id,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    def deactivate(self) -> None:
        if not self.active:
            return
        self.active = False
        self._touch()

    def activate(self) -> None:
        if self.active:
            return
        self.active = True
        self._touch()

    def change_role(self, new_role: UserRole) -> None:
        if self.role == new_role:
            return
        self.role = new_role
        self._touch()

    def set_password_hash(self, new_hash: str) -> None:
        if not new_hash or len(new_hash) < 10:
            raise ValidationError("Password hash invalid", code="user.invalid_password_hash")
        if new_hash == self.password_hash:
            return
        self.password_hash = new_hash
        self._touch()

    def _touch(self) -> None:
        self.version += 1
        self.updated_at = datetime.now(UTC)

    @staticmethod
    def _normalize_email(email: str) -> str:
        e = email.strip().lower()
        if not e or "@" not in e:
            raise ValidationError("Invalid email", code="user.invalid_email")
        if len(e) > User.EMAIL_MAX:
            raise ValidationError("Email too long", code="user.email_too_long")
        return e


@dataclass(slots=True)
class RefreshToken:
    id: str
    user_id: str
    revoked: bool
    created_at: datetime
    expires_at: datetime
    replaced_by: str | None = None
    version: int = 0

    ID_MAX: ClassVar[int] = 36

    @staticmethod
    def issue(user_id: str, expires_at: datetime, token_id: str | None = None) -> RefreshToken:
        return RefreshToken(
            id=token_id or str(uuid4()),
            user_id=user_id,
            revoked=False,
            created_at=datetime.now(UTC),
            expires_at=expires_at,
        )

    def mark_revoked(self, replacement_id: str | None = None) -> None:
        if self.revoked:
            return
        self.revoked = True
        self.replaced_by = replacement_id
        self.version += 1

    def is_expired(self, reference: datetime | None = None) -> bool:
        ref = reference or datetime.now(UTC)
        return self.expires_at <= ref
