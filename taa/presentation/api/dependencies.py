"""FastAPI dependency injection."""

from __future__ import annotations

from functools import lru_cache

from taa.infrastructure.config.container import Container


@lru_cache(maxsize=1)
def get_container() -> Container:
    """Return the singleton DI container."""
    return Container()
