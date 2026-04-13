"""Signal API routes for cross-tool handover.

Endpoints:
- POST /api/signals/send          → Send a handover signal
- GET  /api/signals/check         → Check pending signals
- POST /api/signals/consume       → Consume (acknowledge) a signal
- GET  /api/signals/pending       → List all pending signals (raw)
- DELETE /api/signals/{signal_id} → Delete a signal
"""

import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, Response, HTTPException, status
from pydantic import BaseModel, Field

from hits_core.service.signal_service import SignalService

router = APIRouter(prefix="/signals")


def _get_signal_service() -> SignalService:
    return SignalService()


# --- Request Models ---

class SendSignalRequest(BaseModel):
    sender: str = Field(..., min_length=1, max_length=32, description="AI tool name: claude, opencode, cursor, etc.")
    recipient: str = Field(default="any", max_length=32, description="Target tool name or 'any'")
    signal_type: str = Field(default="session_end", description="session_end, task_ready, question, urgent")
    project_path: Optional[str] = Field(default=None, description="Project absolute path")
    summary: str = Field(..., min_length=1, max_length=2000, description="Brief summary")
    context: Optional[str] = Field(default=None, description="Detailed context")
    pending_items: list[str] = Field(default_factory=list, description="Unfinished tasks")
    tags: list[str] = Field(default_factory=list, description="Tags")
    priority: str = Field(default="normal", description="normal, high, urgent")


class ConsumeSignalRequest(BaseModel):
    signal_id: str = Field(..., min_length=1, description="Signal ID to consume")
    consumed_by: str = Field(..., min_length=1, max_length=32, description="Your tool name")


class APIResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None


# --- Endpoints ---

@router.post("/send", response_model=APIResponse)
async def send_signal(body: SendSignalRequest):
    """Send a handover signal to another AI tool."""
    svc = _get_signal_service()

    signal = await svc.send_signal(
        sender=body.sender,
        recipient=body.recipient,
        signal_type=body.signal_type,
        project_path=body.project_path,
        summary=body.summary,
        context=body.context,
        pending_items=body.pending_items,
        tags=body.tags,
        priority=body.priority,
    )

    return APIResponse(
        success=True,
        data={
            "id": signal.id,
            "sender": signal.sender,
            "recipient": signal.recipient,
            "signal_type": signal.signal_type,
            "priority": signal.priority,
            "project_path": signal.project_path,
            "summary": signal.summary,
            "pending_items": signal.pending_items,
            "created_at": signal.created_at.isoformat(),
        },
    )


@router.get("/check", response_model=APIResponse)
async def check_signals(
    recipient: str = "any",
    project_path: Optional[str] = None,
    limit: int = 10,
):
    """Check for pending signals."""
    svc = _get_signal_service()

    signals = await svc.check_signals(
        recipient=recipient,
        project_path=project_path,
        limit=limit,
    )

    return APIResponse(
        success=True,
        data={
            "count": len(signals),
            "signals": [
                {
                    "id": s.id,
                    "sender": s.sender,
                    "recipient": s.recipient,
                    "signal_type": s.signal_type,
                    "priority": s.priority,
                    "project_path": s.project_path,
                    "summary": s.summary,
                    "context": s.context,
                    "pending_items": s.pending_items,
                    "tags": s.tags,
                    "handover_available": s.handover_available,
                    "created_at": s.created_at.isoformat(),
                }
                for s in signals
            ],
        },
    )


@router.post("/consume", response_model=APIResponse)
async def consume_signal(body: ConsumeSignalRequest):
    """Consume (acknowledge and archive) a signal."""
    svc = _get_signal_service()

    signal = await svc.consume_signal(
        signal_id=body.signal_id,
        consumed_by=body.consumed_by,
    )

    if not signal:
        return APIResponse(success=False, error=f"Signal not found: {body.signal_id}")

    return APIResponse(
        success=True,
        data={
            "id": signal.id,
            "status": signal.status,
            "consumed_by": signal.consumed_by,
            "consumed_at": signal.consumed_at.isoformat() if signal.consumed_at else None,
        },
    )


@router.get("/pending", response_model=APIResponse)
async def list_pending_signals(
    project_path: Optional[str] = None,
    limit: int = 50,
):
    """List all pending signals (raw list)."""
    svc = _get_signal_service()

    signals = await svc.check_signals(recipient="any", project_path=project_path, limit=limit)

    return APIResponse(
        success=True,
        data={
            "count": len(signals),
            "signals": [
                {
                    "id": s.id,
                    "sender": s.sender,
                    "recipient": s.recipient,
                    "signal_type": s.signal_type,
                    "priority": s.priority,
                    "project_path": s.project_path,
                    "summary": s.summary,
                    "context": s.context,
                    "pending_items": s.pending_items,
                    "tags": s.tags,
                    "created_at": s.created_at.isoformat(),
                }
                for s in signals
            ],
        },
    )


@router.delete("/{signal_id}", response_model=APIResponse)
async def delete_signal(signal_id: str):
    """Delete a pending signal."""
    import json

    svc = _get_signal_service()

    for path in svc.pending_dir.glob("*.json"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("id") == signal_id:
                path.unlink()
                return APIResponse(success=True, data={"deleted": signal_id})
        except Exception:
            continue

    return APIResponse(success=False, error=f"Signal not found: {signal_id}")
