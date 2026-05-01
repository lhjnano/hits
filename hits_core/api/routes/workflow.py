"""Workflow Pipeline HTTP routes — expose WorkflowCheckpointService via API.

Provides endpoints for:
- Listing / creating workflows
- Viewing workflow detail with stage pipeline visualization
- Starting / completing / failing stages
- Resuming a failed workflow
"""

from fastapi import APIRouter, Query as QueryParam
from typing import Optional

from hits_core.models.workflow_checkpoint import (
    StageDefinition,
    WorkflowStatus,
)
from hits_core.service.workflow_checkpoint_service import WorkflowCheckpointService
from pydantic import BaseModel
from typing import Optional


class APIResponse(BaseModel):
    success: bool = True
    data: Optional[dict | list] = None
    error: Optional[str] = None

router = APIRouter(prefix="/workflow", tags=["workflow"])

_svc: Optional[WorkflowCheckpointService] = None


def _get_service() -> WorkflowCheckpointService:
    global _svc
    if _svc is None:
        _svc = WorkflowCheckpointService()
    return _svc


@router.get("/list")
async def list_workflows(
    project_path: Optional[str] = QueryParam(default=None),
    limit: int = QueryParam(default=20, ge=1, le=100),
):
    """List all workflows, optionally filtered by project."""
    svc = _get_service()
    workflows = await svc.list_workflows(project_path=project_path, limit=limit)
    return APIResponse(
        success=True,
        data=[wf.model_dump() for wf in workflows],
    )


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str):
    """Get a single workflow with full stage details."""
    svc = _get_service()
    wf = await svc.get_workflow(workflow_id)
    if wf is None:
        return APIResponse(success=False, error=f"Workflow '{workflow_id}' not found")

    data = wf.model_dump()

    # Enrich with computed fields for the UI
    data["progress_pct"] = (
        round(wf._completed_count() / max(len(wf.stages), 1) * 100, 1)
    )
    data["completed_count"] = wf._completed_count()
    data["total_stages"] = len(wf.stages)
    data["next_stage"] = None
    ns = wf.get_next_pending_stage()
    if ns:
        data["next_stage"] = ns.model_dump()

    return APIResponse(success=True, data=data)


@router.post("/create")
async def create_workflow(body: dict):
    """Create a new workflow pipeline.

    Body:
        project_path: str
        name: str
        stages: list[{id, name, description?, agent?, depends_on?, estimated_tokens?}]
        performer?: str
        tags?: list[str]
        metadata?: dict
    """
    svc = _get_service()
    try:
        stage_defs = []
        for s in body.get("stages", []):
            stage_defs.append(StageDefinition(**s))

        wf = await svc.create_workflow(
            project_path=body["project_path"],
            name=body["name"],
            stages=stage_defs,
            performer=body.get("performer", "coordinator"),
            tags=body.get("tags"),
            metadata=body.get("metadata"),
        )
        return APIResponse(success=True, data=wf.model_dump())
    except Exception as e:
        return APIResponse(success=False, error=str(e))


@router.post("/{workflow_id}/start/{stage_id}")
async def start_stage(workflow_id: str, stage_id: str, body: dict = None):
    """Start a stage in the workflow."""
    svc = _get_service()
    performer = (body or {}).get("performer")
    try:
        wf = await svc.start_stage(workflow_id, stage_id, performer=performer)
        return APIResponse(success=True, data=wf.model_dump())
    except ValueError as e:
        return APIResponse(success=False, error=str(e))


@router.post("/{workflow_id}/complete/{stage_id}")
async def complete_stage(workflow_id: str, stage_id: str, body: dict = None):
    """Complete a stage."""
    svc = _get_service()
    tokens_used = (body or {}).get("tokens_used", 0)
    try:
        wf = await svc.complete_stage(workflow_id, stage_id, tokens_used=tokens_used)
        return APIResponse(success=True, data=wf.model_dump())
    except ValueError as e:
        return APIResponse(success=False, error=str(e))


@router.post("/{workflow_id}/fail/{stage_id}")
async def fail_stage(workflow_id: str, stage_id: str, body: dict):
    """Mark a stage as failed."""
    svc = _get_service()
    try:
        wf = await svc.fail_stage(workflow_id, stage_id, error=body.get("error", "Unknown error"))
        return APIResponse(success=True, data=wf.model_dump())
    except ValueError as e:
        return APIResponse(success=False, error=str(e))


@router.get("/{workflow_id}/resume")
async def resume_workflow(workflow_id: str):
    """Get everything needed to resume a workflow (next stage + context)."""
    svc = _get_service()
    result = await svc.resume_workflow(workflow_id)
    if result is None:
        return APIResponse(success=False, error=f"Workflow '{workflow_id}' not found")
    return APIResponse(success=True, data=result)


@router.get("/{workflow_id}/context")
async def get_resume_context(
    workflow_id: str,
    max_tokens: int = QueryParam(default=2000, ge=100, le=10000),
):
    """Get aggregated resume context from completed stages."""
    svc = _get_service()
    context = await svc.get_resume_context(workflow_id, max_tokens=max_tokens)
    if context is None:
        return APIResponse(success=False, error=f"Workflow '{workflow_id}' not found")
    return APIResponse(success=True, data={"context": context})
