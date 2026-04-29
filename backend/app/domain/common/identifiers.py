from __future__ import annotations

import ulid


def new_ulid() -> str:
    return str(ulid.ULID())


def generate_ulid() -> str:
    """Alias retained for backwards compatibility."""
    return new_ulid()
