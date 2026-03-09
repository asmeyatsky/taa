"""Organization entity for multi-tenant support."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Organization:
    """An organization (tenant) that owns users and resources."""

    id: str
    name: str
    slug: str
    plan: str = "free"  # free, pro, enterprise
    max_users: int = 5
    is_active: bool = True
    created_at: str = ""

    def can_add_user(self, current_count: int) -> bool:
        """Check if the organization can add another user."""
        return current_count < self.max_users

    def is_enterprise(self) -> bool:
        """Check if this is an enterprise-tier organization."""
        return self.plan == "enterprise"
