from __future__ import annotations


class DomainError(Exception):
    status_code: int = 400
    error_code: str = "domain_error"

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: str | None = None,
        details: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        if status_code is not None:
            self.status_code = status_code
        if error_code is not None:
            self.error_code = error_code

    def to_dict(self) -> dict[str, str | dict]:
        base: dict[str, str | dict] = {"detail": self.message, "code": self.error_code}
        if self.details is not None:
            base["details"] = self.details
        return base


class ValidationError(DomainError):
    def __init__(self, message: str, code: str = "validation_error", details: dict | None = None) -> None:
        super().__init__(message, status_code=400, error_code=code, details=details)


class UnauthorizedError(DomainError):
    def __init__(self, message: str, code: str = "unauthorized") -> None:
        super().__init__(message, status_code=401, error_code=code)


class ForbiddenError(DomainError):
    def __init__(self, message: str, code: str = "forbidden") -> None:
        super().__init__(message, status_code=403, error_code=code)


class NotFoundError(DomainError):
    def __init__(self, message: str, code: str = "not_found") -> None:
        super().__init__(message, status_code=404, error_code=code)


class ConflictError(DomainError):
    def __init__(self, message: str, code: str = "conflict") -> None:
        super().__init__(message, status_code=409, error_code=code)


class TokenError(UnauthorizedError):
    def __init__(self, message: str, code: str = "invalid_token") -> None:
        super().__init__(message, code=code)


class InactiveUserError(UnauthorizedError):
    def __init__(self, message: str = "user inactive", code: str = "user_inactive") -> None:
        super().__init__(message, code=code)


class RefreshTokenNotFoundError(TokenError):
    def __init__(self, message: str = "refresh token not found", code: str = "refresh_token_not_found") -> None:
        super().__init__(message, code=code)


class RoleForbiddenError(ForbiddenError):
    def __init__(self, message: str = "insufficient role", code: str = "insufficient_role") -> None:
        super().__init__(message, code=code)
