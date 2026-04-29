"""Cash drawer application ports."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from app.domain.cash_drawer import CashDrawerSession, CashMovement


class ICashDrawerRepository(ABC):
    """Cash drawer repository interface."""

    @abstractmethod
    async def add(self, session: CashDrawerSession) -> None:
        """Add a new cash drawer session."""
        ...

    @abstractmethod
    async def get_by_id(self, session_id: str) -> CashDrawerSession | None:
        """Get a cash drawer session by ID."""
        ...

    @abstractmethod
    async def get_open_session_for_terminal(self, terminal_id: str) -> CashDrawerSession | None:
        """Get the currently open session for a terminal."""
        ...

    @abstractmethod
    async def update(self, session: CashDrawerSession) -> None:
        """Update a cash drawer session."""
        ...

    @abstractmethod
    async def add_movement(self, movement: CashMovement) -> None:
        """Add a cash movement to a session."""
        ...

    @abstractmethod
    async def get_movements(self, session_id: str) -> Sequence[CashMovement]:
        """Get all movements for a session."""
        ...

    @abstractmethod
    async def list_sessions(
        self,
        *,
        terminal_id: str | None = None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[CashDrawerSession], int]:
        """List cash drawer sessions with optional filters."""
        ...
