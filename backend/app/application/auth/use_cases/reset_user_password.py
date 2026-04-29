from __future__ import annotations

from dataclasses import dataclass

from app.application.auth.ports import PasswordHasherPort, UserRepositoryPort
from app.core.password_policy import validate_password
from app.domain.auth.entities import User
from app.domain.common.errors import ConflictError, NotFoundError, ValidationError


@dataclass(slots=True)
class ResetUserPasswordInput:
    user_id: str
    expected_version: int
    new_password: str


class ResetUserPasswordUseCase:
    def __init__(self, users: UserRepositoryPort, hasher: PasswordHasherPort):
        self._users = users
        self._hasher = hasher

    async def execute(self, data: ResetUserPasswordInput) -> User:
        # Validate password policy
        password_errors = validate_password(data.new_password)
        if password_errors:
            raise ValidationError(
                "Password does not meet security requirements",
                code="auth.weak_password",
                details={"errors": password_errors},
            )
        
        user = await self._users.get_by_id(data.user_id)
        if user is None:
            raise NotFoundError("user not found")
        if user.version != data.expected_version:
            raise ConflictError("user modified by another transaction")
        if self._hasher.verify(data.new_password, user.password_hash):
            raise ValidationError("new password must differ from the current password", code="password_unchanged")
        hashed = self._hasher.hash(data.new_password)
        user.set_password_hash(hashed)
        updated = await self._users.update(user, expected_version=data.expected_version)
        if not updated:
            raise ConflictError("user modified by another transaction")
        return user
