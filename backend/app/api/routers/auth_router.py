from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user, require_roles
from app.application.auth.ports import PasswordHasherPort, TokenProviderPort
from app.application.auth.use_cases.activate_user import ActivateUserInput, ActivateUserUseCase
from app.application.auth.use_cases.change_user_role import ChangeUserRoleInput, ChangeUserRoleUseCase
from app.application.auth.use_cases.create_user import CreateUserInput, CreateUserUseCase
from app.application.auth.use_cases.deactivate_user import DeactivateUserInput, DeactivateUserUseCase
from app.application.auth.use_cases.list_admin_actions import ListAdminActionsInput, ListAdminActionsUseCase
from app.application.auth.use_cases.list_users import ListUsersInput, ListUsersUseCase
from app.application.auth.use_cases.login import LoginInput, LoginOutput, LoginUseCase
from app.application.auth.use_cases.logout import LogoutInput, LogoutUseCase
from app.application.auth.use_cases.logout_all_sessions import (
    LogoutAllSessionsInput,
    LogoutAllSessionsUseCase,
)
from app.application.auth.use_cases.record_admin_action import (
    RecordAdminActionInput,
    RecordAdminActionUseCase,
)
from app.application.auth.use_cases.refresh_token import RefreshTokenInput, RefreshTokenUseCase
from app.application.auth.use_cases.reset_user_password import (
    ResetUserPasswordInput,
    ResetUserPasswordUseCase,
)
from app.core.settings import get_settings
from app.domain.auth.admin_action_log import AdminActionLog
from app.domain.auth.entities import User, UserRole
from app.infrastructure.auth.password_hasher import PasswordHasher
from app.infrastructure.auth.token_provider import TokenProvider
from app.infrastructure.db.repositories.admin_action_log_repository import AdminActionLogRepository
from app.infrastructure.db.repositories.refresh_token_repository import RefreshTokenRepository
from app.infrastructure.db.repositories.user_repository import UserRepository
from app.infrastructure.db.session import get_session
from app.shared.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page, PageParams


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str
    role: UserRole = UserRole.CASHIER


class UserOut(BaseModel):
    id: str
    email: EmailStr
    role: str
    active: bool
    version: int


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class UserVersionRequest(BaseModel):
    expected_version: int


class ChangeRoleRequest(UserVersionRequest):
    role: UserRole


class ResetPasswordRequest(UserVersionRequest):
    new_password: str


class AdminActionLogOut(BaseModel):
    id: str
    actor_user_id: str
    target_user_id: str | None
    action: str
    details: dict[str, Any]
    trace_id: str | None
    created_at: datetime


router = APIRouter(prefix="/auth", tags=["auth"])

ADMIN_ROLES: tuple[UserRole, ...] = (UserRole.ADMIN,)


def get_password_hasher() -> PasswordHasherPort:  # simple DI wrappers
    return PasswordHasher()


def get_token_provider() -> TokenProviderPort:
    s = get_settings()
    return TokenProvider(secret=s.JWT_SECRET_KEY, issuer=getattr(s, "JWT_ISSUER", "pos-backend"))


def _user_to_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        role=user.role.value,
        active=user.active,
        version=user.version,
    )


def _normalize_datetime(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _log_to_out(log: AdminActionLog) -> AdminActionLogOut:
    return AdminActionLogOut(
        id=log.id,
        actor_user_id=log.actor_user_id,
        target_user_id=log.target_user_id,
        action=log.action,
        details=log.details,
        trace_id=log.trace_id,
        created_at=log.created_at,
    )


async def _record_admin_action(
    session: AsyncSession,
    *,
    actor_user_id: str,
    target_user_id: str | None,
    action: str,
    details: dict[str, Any] | None,
    trace_id: str | None,
) -> None:
    use_case = RecordAdminActionUseCase(AdminActionLogRepository(session))
    await use_case.execute(
        RecordAdminActionInput(
            actor_user_id=actor_user_id,
            target_user_id=target_user_id,
            action=action,
            details=details,
            trace_id=trace_id,
        )
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest, session: AsyncSession = Depends(get_session)) -> UserOut:
    use_case = CreateUserUseCase(UserRepository(session), get_password_hasher())
    user = await use_case.execute(CreateUserInput(email=req.email, password=req.password))
    return _user_to_out(user)


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: CreateUserRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_admin: User = Depends(require_roles(*ADMIN_ROLES)),
) -> UserOut:
    use_case = CreateUserUseCase(UserRepository(session), get_password_hasher())
    user = await use_case.execute(
        CreateUserInput(email=payload.email, password=payload.password, role=payload.role)
    )
    await _record_admin_action(
        session,
        actor_user_id=current_admin.id,
        target_user_id=user.id,
        action="user.create",
        details={"role": payload.role.value},
        trace_id=getattr(request.state, "trace_id", None),
    )
    return _user_to_out(user)


@router.post("/token", response_model=LoginOutput)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
) -> LoginOutput:
    """
    OAuth2 compatible token login, get an access token for future requests.
    """
    repo = UserRepository(session)
    hasher = get_password_hasher()
    token_provider = get_token_provider()
    refresh_repo = RefreshTokenRepository(session)
    use_case = LoginUseCase(repo, hasher, token_provider, refresh_repo)
    
    # Map username to email as our system uses email for login
    return await use_case.execute(LoginInput(email=form_data.username, password=form_data.password))


@router.post("/login", response_model=LoginOutput)
async def login(req: LoginRequest, session: AsyncSession = Depends(get_session)) -> LoginOutput:
    use_case = LoginUseCase(
        UserRepository(session),
        get_password_hasher(),
        get_token_provider(),
        RefreshTokenRepository(session),
    )
    return await use_case.execute(LoginInput(email=req.email, password=req.password))


@router.post("/refresh", response_model=LoginOutput)
async def refresh(req: RefreshRequest, session: AsyncSession = Depends(get_session)) -> LoginOutput:
    use_case = RefreshTokenUseCase(
        UserRepository(session),
        RefreshTokenRepository(session),
        get_token_provider(),
    )
    return await use_case.execute(RefreshTokenInput(refresh_token=req.refresh_token))


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return _user_to_out(current_user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(req: LogoutRequest, session: AsyncSession = Depends(get_session)) -> Response:
    use_case = LogoutUseCase(get_token_provider(), RefreshTokenRepository(session))
    await use_case.execute(LogoutInput(refresh_token=req.refresh_token))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    use_case = LogoutAllSessionsUseCase(RefreshTokenRepository(session))
    await use_case.execute(LogoutAllSessionsInput(user_id=current_user.id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/users/{user_id}/deactivate", response_model=UserOut)
async def deactivate_user(
    user_id: str,
    payload: UserVersionRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_admin: User = Depends(require_roles(*ADMIN_ROLES)),
) -> UserOut:
    use_case = DeactivateUserUseCase(UserRepository(session))
    user = await use_case.execute(
        DeactivateUserInput(user_id=user_id, expected_version=payload.expected_version)
    )
    await _record_admin_action(
        session,
        actor_user_id=current_admin.id,
        target_user_id=user.id,
        action="user.deactivate",
        details={
            "expected_version": payload.expected_version,
            "resulting_version": user.version,
        },
        trace_id=getattr(request.state, "trace_id", None),
    )
    return _user_to_out(user)


@router.post("/users/{user_id}/activate", response_model=UserOut)
async def activate_user(
    user_id: str,
    payload: UserVersionRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_admin: User = Depends(require_roles(*ADMIN_ROLES)),
) -> UserOut:
    use_case = ActivateUserUseCase(UserRepository(session))
    user = await use_case.execute(
        ActivateUserInput(user_id=user_id, expected_version=payload.expected_version)
    )
    await _record_admin_action(
        session,
        actor_user_id=current_admin.id,
        target_user_id=user.id,
        action="user.activate",
        details={
            "expected_version": payload.expected_version,
            "resulting_version": user.version,
        },
        trace_id=getattr(request.state, "trace_id", None),
    )
    return _user_to_out(user)


@router.post("/users/{user_id}/role", response_model=UserOut)
async def change_user_role(
    user_id: str,
    payload: ChangeRoleRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_admin: User = Depends(require_roles(*ADMIN_ROLES)),
) -> UserOut:
    use_case = ChangeUserRoleUseCase(UserRepository(session))
    user = await use_case.execute(
        ChangeUserRoleInput(
            user_id=user_id,
            expected_version=payload.expected_version,
            role=payload.role,
        )
    )
    await _record_admin_action(
        session,
        actor_user_id=current_admin.id,
        target_user_id=user.id,
        action="user.change_role",
        details={
            "expected_version": payload.expected_version,
            "role": payload.role.value,
        },
        trace_id=getattr(request.state, "trace_id", None),
    )
    return _user_to_out(user)


@router.post("/users/{user_id}/password", response_model=UserOut)
async def reset_user_password(
    user_id: str,
    payload: ResetPasswordRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_admin: User = Depends(require_roles(*ADMIN_ROLES)),
) -> UserOut:
    use_case = ResetUserPasswordUseCase(UserRepository(session), get_password_hasher())
    user = await use_case.execute(
        ResetUserPasswordInput(
            user_id=user_id,
            expected_version=payload.expected_version,
            new_password=payload.new_password,
        )
    )
    await _record_admin_action(
        session,
        actor_user_id=current_admin.id,
        target_user_id=user.id,
        action="user.reset_password",
        details={
            "expected_version": payload.expected_version,
            "password_reset": True,
        },
        trace_id=getattr(request.state, "trace_id", None),
    )
    return _user_to_out(user)


@router.get("/users", response_model=Page)
async def list_users(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    page: int = Query(1, ge=1),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    search: str | None = None,
    role: UserRole | None = None,
    active: bool | None = None,
) -> Page:
    params = PageParams(page=page, limit=limit)
    use_case = ListUsersUseCase(UserRepository(session))
    result = await use_case.execute(
        ListUsersInput(
            params=params,
            email=search,
            role=role,
            active=active,
        )
    )
    items = [_user_to_out(user) for user in result.items]
    return Page(items=items, meta=result.meta)


@router.get("/admin-actions", response_model=Page)
async def list_admin_actions(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_roles(*ADMIN_ROLES)),
    page: int = Query(1, ge=1),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    actor_user_id: str | None = None,
    target_user_id: str | None = None,
    action: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> Page:
    params = PageParams(page=page, limit=limit)
    use_case = ListAdminActionsUseCase(AdminActionLogRepository(session))
    normalized_start = _normalize_datetime(start)
    normalized_end = _normalize_datetime(end)
    result = await use_case.execute(
        ListAdminActionsInput(
            params=params,
            actor_user_id=actor_user_id,
            target_user_id=target_user_id,
            action=action,
            start=normalized_start,
            end=normalized_end,
        )
    )
    items = [_log_to_out(log) for log in result.items]
    return Page(items=items, meta=result.meta)
