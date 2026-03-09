"""Audit log API endpoints for compliance tracking.

Provides read-only access to the audit trail with filtering, pagination,
summary statistics, and CSV export.  All endpoints require ``audit:view``
permission.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from taa.presentation.api.auth import UserRecord, require_permission
from taa.presentation.api.dependencies import get_container

router = APIRouter()


def _audit_viewer() -> UserRecord:
    """Dependency: require audit:view permission."""
    return require_permission("audit:view")


# ------------------------------------------------------------------
# GET /api/audit/ - list recent audit entries (paginated)
# ------------------------------------------------------------------

@router.get("/")
async def list_audit_entries(
    user: Annotated[UserRecord, Depends(require_permission("audit:view"))],
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    user_id: str | None = Query(None, description="Filter by user ID"),
    action: str | None = Query(None, description="Filter by action type"),
    since: str | None = Query(None, description="Filter entries since ISO datetime"),
) -> dict[str, Any]:
    """List recent audit entries with pagination and optional filters."""
    container = get_container()

    since_dt = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError:
            since_dt = None

    offset = (page - 1) * page_size

    entries = await container.audit_repo.query(
        user_id=user_id,
        action=action,
        since=since_dt,
        limit=page_size,
        offset=offset,
    )
    total = await container.audit_repo.count(
        user_id=user_id,
        action=action,
        since=since_dt,
    )

    return {
        "entries": entries,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    }


# ------------------------------------------------------------------
# GET /api/audit/user/{user_id} - entries for a specific user
# ------------------------------------------------------------------

@router.get("/user/{target_user_id}")
async def get_user_audit(
    target_user_id: str,
    user: Annotated[UserRecord, Depends(require_permission("audit:view"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """Get audit entries for a specific user."""
    container = get_container()
    offset = (page - 1) * page_size

    entries = await container.audit_repo.query(
        user_id=target_user_id,
        limit=page_size,
        offset=offset,
    )
    total = await container.audit_repo.count(user_id=target_user_id)

    return {
        "entries": entries,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
        "user_id": target_user_id,
    }


# ------------------------------------------------------------------
# GET /api/audit/action/{action} - entries by action type
# ------------------------------------------------------------------

@router.get("/action/{action_type}")
async def get_action_audit(
    action_type: str,
    user: Annotated[UserRecord, Depends(require_permission("audit:view"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """Get audit entries filtered by action type."""
    container = get_container()
    offset = (page - 1) * page_size

    entries = await container.audit_repo.query(
        action=action_type,
        limit=page_size,
        offset=offset,
    )
    total = await container.audit_repo.count(action=action_type)

    return {
        "entries": entries,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
        "action": action_type,
    }


# ------------------------------------------------------------------
# GET /api/audit/stats - summary statistics
# ------------------------------------------------------------------

@router.get("/stats")
async def get_audit_stats(
    user: Annotated[UserRecord, Depends(require_permission("audit:view"))],
) -> dict[str, Any]:
    """Get audit log summary statistics."""
    container = get_container()

    total = await container.audit_repo.count()

    # Get entries for today
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_count = await container.audit_repo.count(since=today_start)

    # Get recent entries to compute top users and top actions
    recent = await container.audit_repo.query(limit=1000)

    # Top users (by entry count)
    user_counts: dict[str, int] = {}
    for entry in recent:
        uid = entry.get("username") or entry.get("user_id", "unknown")
        user_counts[uid] = user_counts.get(uid, 0) + 1
    top_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    # Top actions
    action_counts: dict[str, int] = {}
    for entry in recent:
        act = entry.get("action", "unknown")
        action_counts[act] = action_counts.get(act, 0) + 1
    top_actions = sorted(action_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    # Entries per day (last 7 days from recent entries)
    day_counts: dict[str, int] = {}
    for entry in recent:
        created = entry.get("created_at", "")
        if created:
            day = created[:10]  # YYYY-MM-DD
            day_counts[day] = day_counts.get(day, 0) + 1
    entries_per_day = sorted(day_counts.items(), key=lambda x: x[0], reverse=True)[:7]

    # Unique users in recent entries
    unique_users = len(user_counts)

    return {
        "total_entries": total,
        "today_entries": today_count,
        "unique_users": unique_users,
        "top_users": [{"user": u, "count": c} for u, c in top_users],
        "top_actions": [{"action": a, "count": c} for a, c in top_actions],
        "entries_per_day": [{"date": d, "count": c} for d, c in entries_per_day],
    }


# ------------------------------------------------------------------
# GET /api/audit/export - export audit log as CSV
# ------------------------------------------------------------------

@router.get("/export")
async def export_audit_csv(
    user: Annotated[UserRecord, Depends(require_permission("audit:view"))],
    user_id: str | None = Query(None),
    action: str | None = Query(None),
    since: str | None = Query(None),
) -> StreamingResponse:
    """Export audit log entries as a CSV file."""
    container = get_container()

    since_dt = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError:
            since_dt = None

    entries = await container.audit_repo.query(
        user_id=user_id,
        action=action,
        since=since_dt,
        limit=10000,
    )

    # Build CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "timestamp", "user_id", "username", "action", "resource_type", "resource_id", "ip_address", "details"])

    for entry in entries:
        writer.writerow([
            entry.get("id", ""),
            entry.get("created_at", ""),
            entry.get("user_id", ""),
            entry.get("username", ""),
            entry.get("action", ""),
            entry.get("resource_type", ""),
            entry.get("resource_id", ""),
            entry.get("ip_address", ""),
            entry.get("details", ""),
        ])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_log.csv"},
    )
