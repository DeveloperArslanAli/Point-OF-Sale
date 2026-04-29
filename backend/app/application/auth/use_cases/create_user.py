from __future__ import annotations

from dataclasses import dataclass

from app.application.auth.ports import PasswordHasherPort, UserRepositoryPort
from app.core.password_policy import validate_password
from app.domain.auth.entities import User, UserRole
from app.domain.common.errors import ConflictError, ValidationError


@dataclass
class CreateUserInput:
    email: str
    password: str
    role: UserRole = UserRole.CASHIER


class CreateUserUseCase:
    def __init__(self, repo: UserRepositoryPort, hasher: PasswordHasherPort):
        self._repo = repo
        self._hasher = hasher

    async def execute(self, data: CreateUserInput) -> User:
        # Validate password policy
        password_errors = validate_password(data.password)
        if password_errors:
            raise ValidationError(
                "Password does not meet security requirements",
                code="auth.weak_password",
                details={"errors": password_errors},
            )
        
        if await self._repo.get_by_email(data.email):
            raise ConflictError("email already registered")
        hashed = self._hasher.hash(data.password)
        user = User.create(email=data.email, password_hash=hashed, role=data.role)
        await self._repo.add(user)
        return user
