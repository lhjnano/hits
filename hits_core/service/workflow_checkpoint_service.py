"""Workflow Checkpoint Service — manages multi-stage pipeline checkpoints.

Extends CheckpointService to support:
- Creating and tracking multi-stage workflow checkpoints
- Starting/completing/failing individual stages
- Resuming a failed workflow from the last successful stage
- Aggregating context across all completed stages
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from ..models.workflow_checkpoint import (
    WorkflowCheckpoint,
    StageDefinition,
    StageCheckpoint,
    StageStatus,
    WorkflowStatus,
)
from ..models.checkpoint import Checkpoint
from ..storage.base import BaseStorage
from ..storage.file_store import FileStorage


class WorkflowCheckpointService:
    """Manage workflow-level checkpoints for multi-agent pipelines.

    Storage layout:
        ~/.hits/data/workflows/
        ├── {workflow_id}.json          ← workflow metadata + stage states
        └── {workflow_id}/
            ├── stage_{id}.json          ← stage checkpoint data
            └── resume_context.json      ← pre-built resume context
    """

    WORKFLOW_DIR = "workflows"

    def __init__(self, storage: Optional[BaseStorage] = None):
        self.storage = storage or FileStorage()
        if isinstance(self.storage, FileStorage):
            self._base_path = self.storage.base_path
        else:
            self._base_path = Path(
                Path.home() / ".hits" / "data"
            )
        self._workflow_dir = self._base_path / self.WORKFLOW_DIR
        self._workflow_dir.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------------
    # CRUD
    # -----------------------------------------------------------------------

    async def create_workflow(
        self,
        project_path: str,
        name: str,
        stages: list[StageDefinition],
        performer: str = "coordinator",
        tags: Optional[list[str]] = None,
        metadata: Optional[dict] = None,
    ) -> WorkflowCheckpoint:
        """Create a new workflow with defined stages."""
        workflow = WorkflowCheckpoint(
            workflow_id=f"wf_{uuid4().hex[:8]}",
            project_path=str(Path(project_path).resolve()),
            project_name=Path(project_path).name,
            name=name,
            stages=stages,
            performer=performer,
            tags=tags or [],
            metadata=metadata or {},
        )
        await self._save_workflow(workflow)
        return workflow

    async def get_workflow(self, workflow_id: str) -> Optional[WorkflowCheckpoint]:
        """Load a workflow by ID."""
        path = self._workflow_dir / f"{workflow_id}.json"
        if not path.exists():
            return None
        try:
            return WorkflowCheckpoint.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    async def list_workflows(
        self,
        project_path: Optional[str] = None,
        limit: int = 20,
    ) -> list[WorkflowCheckpoint]:
        """List workflows, optionally filtered by project."""
        workflows = []
        for path in sorted(self._workflow_dir.glob("wf_*.json"), reverse=True):
            try:
                wf = WorkflowCheckpoint.model_validate_json(
                    path.read_text(encoding="utf-8")
                )
                if project_path and wf.project_path != project_path:
                    continue
                workflows.append(wf)
                if len(workflows) >= limit:
                    break
            except Exception:
                continue
        return workflows

    # -----------------------------------------------------------------------
    # Stage operations
    # -----------------------------------------------------------------------

    async def start_stage(
        self,
        workflow_id: str,
        stage_id: str,
        performer: Optional[str] = None,
    ) -> WorkflowCheckpoint:
        """Start a stage in the workflow."""
        wf = await self.get_workflow(workflow_id)
        if wf is None:
            raise ValueError(f"Workflow '{workflow_id}' not found")

        wf.start_stage(stage_id, performer=performer)
        await self._save_workflow(wf)
        return wf

    async def complete_stage(
        self,
        workflow_id: str,
        stage_id: str,
        checkpoint: Optional[Checkpoint] = None,
        tokens_used: int = 0,
    ) -> WorkflowCheckpoint:
        """Complete a stage and optionally attach a checkpoint."""
        wf = await self.get_workflow(workflow_id)
        if wf is None:
            raise ValueError(f"Workflow '{workflow_id}' not found")

        wf.complete_stage(stage_id, checkpoint=checkpoint, tokens_used=tokens_used)

        # Also save the stage checkpoint separately for quick access
        if checkpoint:
            stage_dir = self._workflow_dir / workflow_id
            stage_dir.mkdir(parents=True, exist_ok=True)
            stage_path = stage_dir / f"stage_{stage_id}.json"
            stage_path.write_text(checkpoint.model_dump_json(indent=2), encoding="utf-8")

        await self._save_workflow(wf)
        return wf

    async def fail_stage(
        self,
        workflow_id: str,
        stage_id: str,
        error: str,
    ) -> WorkflowCheckpoint:
        """Mark a stage as failed."""
        wf = await self.get_workflow(workflow_id)
        if wf is None:
            raise ValueError(f"Workflow '{workflow_id}' not found")

        wf.fail_stage(stage_id, error)
        await self._save_workflow(wf)
        return wf

    # -----------------------------------------------------------------------
    # Resume
    # -----------------------------------------------------------------------

    async def get_resume_context(
        self,
        workflow_id: str,
        max_tokens: int = 2000,
    ) -> Optional[str]:
        """Get aggregated resume context for continuing a workflow."""
        wf = await self.get_workflow(workflow_id)
        if wf is None:
            return None
        return wf.get_resume_context(max_tokens=max_tokens)

    async def resume_workflow(self, workflow_id: str) -> Optional[dict]:
        """Get everything needed to resume a workflow.

        Returns:
            {
                "workflow": WorkflowCheckpoint,
                "next_stage": StageDefinition or None,
                "resume_context": str,
                "completed_stages": int,
                "total_stages": int,
            }
        """
        wf = await self.get_workflow(workflow_id)
        if wf is None:
            return None

        next_stage = wf.get_next_pending_stage()
        context = wf.get_resume_context()

        return {
            "workflow": wf.model_dump(),
            "next_stage": next_stage.model_dump() if next_stage else None,
            "resume_context": context,
            "completed_stages": wf._completed_count(),
            "total_stages": len(wf.stages),
            "workflow_id": workflow_id,
            "status": wf.status,
        }

    # -----------------------------------------------------------------------
    # Persistence
    # -----------------------------------------------------------------------

    async def _save_workflow(self, wf: WorkflowCheckpoint) -> None:
        """Save workflow to disk."""
        path = self._workflow_dir / f"{wf.workflow_id}.json"
        path.write_text(wf.model_dump_json(indent=2), encoding="utf-8")
