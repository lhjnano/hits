"""API routes for checkpoint management."""

from fastapi import APIRouter, Depends, Query
from typing import Optional

from ...service.checkpoint_service import CheckpointService
from ...service.signal_service import SignalService
from ...ai.checkpoint_compressor import CheckpointCompressor
from ...storage.file_store import FileStorage
from hits_core.auth.dependencies import require_auth

router = APIRouter()

_storage = FileStorage()
_cp_service = CheckpointService(storage=_storage)
_sig_service = SignalService()
_compressor = CheckpointCompressor()


@router.get("/checkpoint/resume")
async def get_resume(
    project_path: str = Query(..., description="Project absolute path"),
    token_budget: int = Query(default=2000, description="Token budget"),
    performer: Optional[str] = Query(default=None, description="Tool name for consuming signals"),
):
    """Get latest checkpoint + pending signals for project resume."""
    result = {
        "project_path": project_path,
        "signals": [],
        "checkpoint": None,
        "compressed": None,
    }

    # Check signals
    signals = await _sig_service.check_signals(recipient="any", project_path=project_path)
    if signals:
        result["signals"] = [
            {
                "id": s.id,
                "sender": s.sender,
                "summary": s.summary,
                "priority": s.priority,
                "pending_items": s.pending_items,
            }
            for s in signals
        ]

        # Auto-consume if performer specified
        if performer:
            for sig in signals:
                await _sig_service.consume_signal(sig.id, performer)

    # Get checkpoint
    checkpoint = await _cp_service.get_latest_checkpoint(project_path)
    if checkpoint:
        result["checkpoint"] = checkpoint.model_dump()
        result["compressed"] = _compressor.compress_checkpoint(checkpoint, token_budget)

    return {"success": True, "data": result}


@router.get("/checkpoint/latest")
async def get_latest_checkpoint(
    project_path: str = Query(..., description="Project absolute path"),
    token_budget: int = Query(default=2000, description="Token budget"),
    format: str = Query(default="text", description="Output format: text or json"),
):
    """Get the latest checkpoint for a project."""
    checkpoint = await _cp_service.get_latest_checkpoint(project_path)

    if not checkpoint:
        return {"success": False, "error": "No checkpoint found"}

    if format == "text":
        return {"success": True, "data": _compressor.compress_checkpoint(checkpoint, token_budget)}
    else:
        return {"success": True, "data": checkpoint.model_dump()}


@router.get("/checkpoint/list")
async def list_checkpoints(
    project_path: str = Query(..., description="Project absolute path"),
    limit: int = Query(default=10, description="Max results"),
):
    """List available checkpoints for a project."""
    checkpoints = await _cp_service.list_checkpoints(project_path, limit=limit)

    return {
        "success": True,
        "data": [
            {
                "id": cp.id,
                "created_at": cp.created_at.isoformat(),
                "performer": cp.performer,
                "purpose": cp.purpose,
                "completion_pct": cp.completion_pct,
                "git_branch": cp.git_branch,
                "next_steps_count": len(cp.next_steps),
                "first_next_step": cp.next_steps[0].action if cp.next_steps else None,
            }
            for cp in checkpoints
        ],
    }


@router.post("/checkpoint/auto")
async def auto_checkpoint(
    body: dict,
    _auth=Depends(require_auth),
):
    """Generate an auto-checkpoint for the current session."""
    from uuid import uuid4
    from ...models.work_log import WorkLog, WorkLogSource, WorkLogResultType
    from ...models.checkpoint import NextStep, Block, Decision

    project_path = body.get("project_path", "")
    performer = body.get("performer", "unknown")

    # Record work log
    log = WorkLog(
        id=str(uuid4())[:8],
        source=WorkLogSource.AI_SESSION,
        performed_by=performer,
        request_text=body.get("purpose", "Session checkpoint"),
        context=body.get("current_state"),
        tags=["checkpoint", "auto"],
        project_path=project_path,
        result_type=WorkLogResultType.AI_RESPONSE,
        result_data={
            "files_modified": body.get("files_modified", []),
            "commands_run": body.get("commands_run", []),
        },
    )
    await _storage.save_work_log(log)

    # Build next steps
    next_steps = []
    for step in body.get("next_steps", []):
        next_steps.append(NextStep(
            action=step["action"],
            command=step.get("command"),
            file=step.get("file"),
            priority=step.get("priority", "medium"),
        ))

    # Build blocks
    blocks = []
    for b in body.get("blocks", []):
        blocks.append(Block(
            issue=b["issue"],
            workaround=b.get("workaround"),
            severity=b.get("severity", "medium"),
        ))

    # Build decisions
    decisions = []
    for d in body.get("decisions", []):
        decisions.append(Decision(
            decision=d["decision"],
            rationale=d.get("rationale"),
        ))

    # Generate checkpoint
    checkpoint = await _cp_service.auto_checkpoint(
        project_path=project_path,
        performer=performer,
        purpose=body.get("purpose", ""),
        current_state=body.get("current_state", ""),
        completion_pct=body.get("completion_pct", 0),
        additional_context=body.get("required_context", []),
        additional_steps=next_steps,
        files_modified=body.get("files_modified", []),
        commands_run=body.get("commands_run", []),
    )

    if blocks:
        checkpoint.blocks = blocks
    if decisions:
        checkpoint.decisions_made = decisions

    # Send signal
    signal = None
    if body.get("send_signal", True):
        token_budget = body.get("token_budget", 2000)
        signal = await _sig_service.send_signal(
            sender=performer,
            recipient=body.get("signal_recipient", "any"),
            signal_type="session_end",
            project_path=project_path,
            summary=body.get("purpose", checkpoint.purpose),
            context=checkpoint.to_compact(token_budget=500),
            pending_items=[s.action for s in checkpoint.next_steps[:3]],
            tags=["checkpoint", "auto"],
        )

    return {
        "success": True,
        "data": {
            "checkpoint_id": checkpoint.id,
            "log_id": log.id,
            "signal_id": signal.id if signal else None,
            "compressed": _compressor.compress_checkpoint(
                checkpoint, body.get("token_budget", 2000)
            ),
        },
    }


@router.get("/checkpoint/projects")
async def list_checkpoint_projects():
    """List all projects with checkpoint history. No auth required — project names/paths only."""
    projects = await _cp_service.list_all_projects()
    return {"success": True, "data": projects}
