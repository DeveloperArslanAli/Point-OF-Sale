"""Shift application ports."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from app.domain.shifts import Shift


class IShiftRepository(ABC):
    """Shift repository interface."""

    @abstractmethod
    async def add(self, shift: Shift) -> None:
        """Add a new shift."""
        ...

    @abstractmethod
    async def get_by_id(self, shift_id: str) -> Shift | None:
        """Get a shift by ID."""
        ...

    @abstractmethod
    async def get_active_shift_for_user(self, user_id: str) -> Shift | None:
        """Get the currently active shift for a user."""
        ...

    @abstractmethod
    async def get_active_shift_for_terminal(self, terminal_id: str) -> Shift | None:
        """Get the currently active shift for a terminal."""
        ...

    @abstractmethod
    async def update(self, shift: Shift) -> None:
        """Update a shift."""
        ...

    @abstractmethod
    async def list_shifts(
        self,
        *,
        user_id: str | None = None,
        terminal_id: str | None = None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[Shift], int]:
        """List shifts with optional filters."""
        ...
