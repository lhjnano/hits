"""Handover API routes - project-scoped session handover endpoints.

These endpoints enable AI tools to:
1. Get a structured handover summary for a specific project
2. List all projects with activity
3. Get project statistics

Typical flow:
  Session ending → POST /api/work-log (record work)
  Session starting → GET /api/handover?project_path=... (get context)
"""

from typing import Any, Optional
from pathlib import Path

from fastapi import APIRouter, Query
from pydantic import BaseModel

from hits_core.service.handover_service import HandoverService


router = APIRouter()

_service: Optional[HandoverService] = None


def get_service() -> HandoverService:
    global _service
    if _service is None:
        _service = HandoverService()
    return _service


class APIResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None


@router.get("/handover", response_model=APIResponse)
async def get_handover(
    project_path: str = Query(..., description="Absolute path to the project directory"),
    format: str = Query("dict", description="Output format: 'dict' (JSON) or 'text' (markdown)"),
    recent_count: int = Query(20, ge=1, le=100, description="Number of recent logs to include"),
):
    """Get a handover summary for a specific project.

    This is the primary endpoint for session continuity. When an AI tool
    starts a new session on a project, it calls this endpoint to get
    all relevant context from previous sessions.

    The project_path is used to scope all data to the specific project,
    so different projects get completely independent handovers.
    """
    service = get_service()

    # Validate path exists
    if not Path(project_path).exists():
        return APIResponse(
            success=False,
            error=f"Project path does not exist: {project_path}",
        )

    try:
        summary = await service.get_handover(
            project_path=project_path,
            recent_count=recent_count,
        )

        if format == "text":
            return APIResponse(
                success=True,
                data={"text": summary.to_text()},
            )

        return APIResponse(success=True, data=summary.to_dict())

    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.get("/handover/projects", response_model=APIResponse)
async def list_projects():
    """List all projects that have recorded work logs.

    Returns project paths with aggregated statistics, sorted by last activity.
    Useful for discovering which projects have accumulated context.
    """
    service = get_service()

    try:
        projects = await service.list_projects()
        return APIResponse(success=True, data=projects)
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.get("/handover/project-stats", response_model=APIResponse)
async def get_project_stats(
    project_path: str = Query(..., description="Absolute path to the project directory"),
):
    """Get aggregated statistics for a specific project.

    Returns counts, tags, performers, files modified, etc.
    Lighter than full handover - use this for quick project overview.
    """
    service = get_service()

    try:
        from hits_core.storage.file_store import FileStorage
        storage = FileStorage()
        stats = await storage.get_project_summary(
            str(Path(project_path).resolve())
        )
        return APIResponse(success=True, data=stats)
    except Exception as e:
        return APIResponse(success=False, error=str(e))
