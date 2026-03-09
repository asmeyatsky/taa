"""Abstract repository interfaces (ports) for persistent entities.

These follow hexagonal architecture: domain defines the interface,
infrastructure provides the implementation.
"""

from __future__ import annotations

import abc
from datetime import datetime
from typing import Any


class OrganizationRepository(abc.ABC):
    """Port for organization (tenant) persistence."""

    @abc.abstractmethod
    async def get_by_id(self, org_id: str) -> dict[str, Any] | None:
        """Return organization dict or None."""
        ...

    @abc.abstractmethod
    async def get_by_slug(self, slug: str) -> dict[str, Any] | None:
        """Return organization by slug or None."""
        ...

    @abc.abstractmethod
    async def list_all(self) -> list[dict[str, Any]]:
        """Return all organizations."""
        ...

    @abc.abstractmethod
    async def create(self, org: dict[str, Any]) -> dict[str, Any]:
        """Create a new organization and return it."""
        ...

    @abc.abstractmethod
    async def update(self, org_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        """Update organization fields and return the updated record."""
        ...

    @abc.abstractmethod
    async def delete(self, org_id: str) -> bool:
        """Delete an organization. Return True if deleted."""
        ...


class UserRepository(abc.ABC):
    """Port for user persistence."""

    @abc.abstractmethod
    async def get_by_username(self, username: str) -> dict[str, Any] | None:
        """Return user dict or None."""
        ...

    @abc.abstractmethod
    async def get_by_id(self, user_id: str) -> dict[str, Any] | None:
        """Return user dict or None."""
        ...

    @abc.abstractmethod
    async def create(self, user: dict[str, Any]) -> dict[str, Any]:
        """Create a new user record and return it."""
        ...

    @abc.abstractmethod
    async def update(self, user_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        """Update user fields and return the updated record."""
        ...

    @abc.abstractmethod
    async def list_all(self, *, org_id: str | None = None) -> list[dict[str, Any]]:
        """Return all users, optionally filtered by org_id."""
        ...

    @abc.abstractmethod
    async def delete(self, user_id: str) -> bool:
        """Delete a user. Return True if deleted."""
        ...


class SchemaRepository(abc.ABC):
    """Port for uploaded schema persistence."""

    @abc.abstractmethod
    async def save(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Persist an uploaded schema record."""
        ...

    @abc.abstractmethod
    async def get_by_id(self, schema_id: str) -> dict[str, Any] | None:
        """Get a schema by ID."""
        ...

    @abc.abstractmethod
    async def list_all(self, limit: int = 100, *, org_id: str | None = None) -> list[dict[str, Any]]:
        """List schemas ordered by upload time descending."""
        ...

    @abc.abstractmethod
    async def delete(self, schema_id: str) -> bool:
        """Delete a schema. Return True if deleted."""
        ...


class MappingRepository(abc.ABC):
    """Port for vendor mapping result persistence."""

    @abc.abstractmethod
    async def save(self, mapping: dict[str, Any]) -> dict[str, Any]:
        """Persist a mapping result record."""
        ...

    @abc.abstractmethod
    async def get_by_schema_id(self, schema_id: str) -> list[dict[str, Any]]:
        """Get all mappings for a given schema upload."""
        ...

    @abc.abstractmethod
    async def list_all(self, limit: int = 100, *, org_id: str | None = None) -> list[dict[str, Any]]:
        """List mappings ordered by creation time descending."""
        ...


class ExportRepository(abc.ABC):
    """Port for export/download persistence."""

    @abc.abstractmethod
    async def save(self, export: dict[str, Any]) -> dict[str, Any]:
        """Persist an export record."""
        ...

    @abc.abstractmethod
    async def get_by_id(self, export_id: str) -> dict[str, Any] | None:
        """Get an export by its download ID."""
        ...

    @abc.abstractmethod
    async def list_by_user(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """List exports for a user."""
        ...


class AuditRepository(abc.ABC):
    """Port for audit log persistence."""

    @abc.abstractmethod
    async def log(
        self,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        details: str | None = None,
        username: str = "",
        ip_address: str | None = None,
        *,
        org_id: str | None = None,
    ) -> dict[str, Any]:
        """Record an audit event."""
        ...

    @abc.abstractmethod
    async def query(
        self,
        user_id: str | None = None,
        action: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
        *,
        org_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query audit log with optional filters."""
        ...

    @abc.abstractmethod
    async def count(
        self,
        user_id: str | None = None,
        action: str | None = None,
        since: datetime | None = None,
    ) -> int:
        """Count audit log entries matching filters."""
        ...
