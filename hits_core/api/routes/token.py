"""API routes for token tracking and budget management."""

from fastapi import APIRouter, Query
from typing import Optional

from ...service.token_tracker import TokenTrackerService
from ...storage.file_store import FileStorage

router = APIRouter()

_tracker = TokenTrackerService()


@router.get("/token/stats/{project_path:path}")
async def get_project_stats(project_path: str):
    """Get aggregated token statistics for a project."""
    stats = _tracker.get_project_stats("/" + project_path)
    return {"success": True, "data": stats.model_dump()}


@router.get("/token/daily")
async def get_daily_usage(
    project_path: str = "",
    days: int = Query(default=7, ge=1, le=90),
):
    """Get daily aggregated usage for the last N days."""
    result = _tracker.get_daily_usage(project_path=project_path, days=days)
    return {
        "success": True,
        "data": [d.model_dump() for d in result],
    }


@router.get("/token/top-projects")
async def get_top_projects(limit: int = Query(default=10, ge=1, le=50)):
    """Get top projects by total token usage."""
    result = _tracker.get_top_projects(limit=limit)
    return {
        "success": True,
        "data": [s.model_dump() for s in result],
    }


@router.get("/token/budget/{project_path:path}")
async def get_budget(project_path: str):
    """Get budget configuration for a project."""
    budget = _tracker.get_budget("/" + project_path)
    if budget is None:
        return {"success": True, "data": None}
    remaining = _tracker.get_remaining_budget("/" + project_path)
    alert = _tracker.check_budget_alert("/" + project_path)
    return {
        "success": True,
        "data": {
            **budget.model_dump(),
            "remaining": remaining,
            "alert": alert,
        },
    }


@router.post("/token/budget")
async def set_budget(data: dict):
    """Set or update token budget for a project."""
    project_path = data.get("project_path", "")
    monthly = data.get("monthly_token_limit", 0)
    daily = data.get("daily_token_limit", 0)
    threshold = data.get("alert_threshold_pct", 80.0)

    budget = _tracker.set_budget(
        project_path=project_path,
        monthly_token_limit=monthly,
        daily_token_limit=daily,
        alert_threshold_pct=threshold,
    )
    return {"success": True, "data": budget.model_dump()}


@router.get("/token/alert/{project_path:path}")
async def check_budget_alert(project_path: str):
    """Check if budget usage exceeds alert threshold."""
    alert = _tracker.check_budget_alert("/" + project_path)
    return {"success": True, "data": {"alert": alert}}


@router.post("/token/record")
async def record_usage(data: dict):
    """Record a token usage event."""
    rec = _tracker.record(
        project_path=data.get("project_path", ""),
        performer=data.get("performer", ""),
        tokens_in=data.get("tokens_in", 0),
        tokens_out=data.get("tokens_out", 0),
        model=data.get("model"),
        operation=data.get("operation"),
        session_id=data.get("session_id"),
        tags=data.get("tags"),
    )
    return {"success": True, "data": rec.model_dump()}
