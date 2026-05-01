"""Workflow Checkpoint model — multi-agent pipeline tracking.

Extends the existing Checkpoint system to support multi-stage pipelines
like Agent Factory workflows, CI/CD pipelines, and parallel subagent tasks.

Key concepts:
- WorkflowCheckpoint: the overall pipeline (contains stages)
- StageCheckpoint: a single stage's state (wraps a regular Checkpoint)
- Stage status: pending → running → completed | failed | skipped

Usage:
    wf = WorkflowCheckpoint(
        workflow_id="wf_abc123",
        project_path="/home/user/project",
        name="ML Development Pipeline",
        stages=[
            StageDefinition(id="s1", name="Data Collection", agent="data-collector"),
            StageDefinition(id="s2", name="Model Design", agent="designer"),
        ],
    )

    # Start a stage
    wf.start_stage("s1", performer="opencode")

    # Complete a stage (creates a checkpoint)
    wf.complete_stage("s1", checkpoint=regular_checkpoint)

    # Get resume context for next stage
    context = wf.get_resume_context()
"""

from enum import Enum
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

from .checkpoint import Checkpoint, StepPriority


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIALLY_COMPLETED = "partially_completed"


# ---------------------------------------------------------------------------
# Stage definition
# ---------------------------------------------------------------------------

class StageDefinition(BaseModel):
    """Defines a single stage in a workflow pipeline."""
    model_config = ConfigDict(use_enum_values=True)

    id: str = Field(..., description="Unique stage ID within workflow")
    name: str = Field(..., description="Human-readable stage name")
    description: Optional[str] = Field(default=None)
    agent: Optional[str] = Field(default=None, description="Assigned agent/tool name")
    depends_on: list[str] = Field(default_factory=list, description="Stage IDs this depends on")
    estimated_tokens: Optional[int] = Field(default=None)


class StageCheckpoint(BaseModel):
    """A stage's state within a workflow — wraps a regular Checkpoint."""
    model_config = ConfigDict(use_enum_values=True)

    stage_id: str = Field(..., description="Reference to StageDefinition.id")
    status: StageStatus = Field(default=StageStatus.PENDING)
    performer: Optional[str] = Field(default=None, description="AI tool that ran this stage")
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    checkpoint: Optional[Checkpoint] = Field(default=None, description="Checkpoint at stage completion")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    stage_index: int = Field(default=0, description="Order in the pipeline")


# ---------------------------------------------------------------------------
# WorkflowCheckpoint
# ---------------------------------------------------------------------------

class WorkflowCheckpoint(BaseModel):
    """Complete pipeline state — tracks all stages and their checkpoints.

    This is the top-level object for multi-agent workflows. It enables:
    1. Tracking parallel/sequential stage execution
    2. Resuming a failed pipeline from the last successful stage
    3. Aggregating context from all completed stages for the next stage
    4. Cost tracking across the entire pipeline
    """
    model_config = ConfigDict(use_enum_values=True, extra="ignore")

    # Identity
    workflow_id: str = Field(..., description="Unique workflow ID")
    project_path: str = Field(..., description="Project absolute path")
    project_name: str = Field(default="")
    name: str = Field(default="", description="Workflow name (e.g. 'ML Pipeline')")

    # Pipeline definition
    stages: list[StageDefinition] = Field(default_factory=list)
    stage_checkpoints: list[StageCheckpoint] = Field(default_factory=list)

    # Overall status
    status: WorkflowStatus = Field(default=WorkflowStatus.PENDING)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = Field(default=None)

    # Creator info
    performer: str = Field(default="coordinator", description="Who initiated the workflow")

    # Aggregated results
    total_files_modified: list[str] = Field(default_factory=list)
    total_decisions: list[str] = Field(default_factory=list)
    total_errors: list[str] = Field(default_factory=list)

    # Token tracking
    total_tokens_used: int = Field(default=0)

    # Metadata
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)

    # --- Operations ---

    def start_stage(self, stage_id: str, performer: Optional[str] = None) -> StageCheckpoint:
        """Mark a stage as running. Returns the StageCheckpoint."""
        self._validate_stage(stage_id)
        self._check_dependencies(stage_id)

        sc = StageCheckpoint(
            stage_id=stage_id,
            status=StageStatus.RUNNING,
            performer=performer,
            started_at=datetime.now(),
            stage_index=self._get_stage_index(stage_id),
        )

        # Remove existing if restarting
        self.stage_checkpoints = [s for s in self.stage_checkpoints if s.stage_id != stage_id]
        self.stage_checkpoints.append(sc)

        # Update overall status
        if self.status == WorkflowStatus.PENDING:
            self.status = WorkflowStatus.RUNNING
        self.updated_at = datetime.now()

        return sc

    def complete_stage(
        self,
        stage_id: str,
        checkpoint: Optional[Checkpoint] = None,
        tokens_used: int = 0,
    ) -> StageCheckpoint:
        """Mark a stage as completed with its checkpoint."""
        sc = self._get_stage_checkpoint(stage_id)
        if sc is None:
            raise ValueError(f"Stage '{stage_id}' has not been started")

        sc.status = StageStatus.COMPLETED
        sc.completed_at = datetime.now()
        if checkpoint:
            sc.checkpoint = checkpoint

        # Aggregate results
        if checkpoint:
            for fd in checkpoint.files_delta:
                if fd.path not in self.total_files_modified:
                    self.total_files_modified.append(fd.path)
            for d in checkpoint.decisions_made:
                self.total_decisions.append(d.decision)
            for b in checkpoint.blocks:
                self.total_errors.append(b.issue)

        self.total_tokens_used += tokens_used
        self.updated_at = datetime.now()

        # Check if all stages done
        self._update_overall_status()
        return sc

    def fail_stage(self, stage_id: str, error: str) -> StageCheckpoint:
        """Mark a stage as failed."""
        sc = self._get_stage_checkpoint(stage_id)
        if sc is None:
            # Auto-start and immediately fail
            sc = self.start_stage(stage_id)

        sc.status = StageStatus.FAILED
        sc.error = error
        sc.completed_at = datetime.now()
        self.total_errors.append(error)
        self.status = WorkflowStatus.FAILED
        self.updated_at = datetime.now()
        return sc

    def get_stage_status(self, stage_id: str) -> StageStatus:
        """Get current status of a stage."""
        sc = self._get_stage_checkpoint(stage_id)
        return sc.status if sc else StageStatus.PENDING

    def get_current_stage(self) -> Optional[StageCheckpoint]:
        """Get the currently running stage, if any."""
        for sc in self.stage_checkpoints:
            if sc.status == StageStatus.RUNNING:
                return sc
        return None

    def get_next_pending_stage(self) -> Optional[StageDefinition]:
        """Get the next stage that can be started (dependencies met)."""
        for stage_def in self.stages:
            sc = self._get_stage_checkpoint(stage_def.id)
            if sc and sc.status in (StageStatus.COMPLETED, StageStatus.RUNNING):
                continue
            # Check dependencies
            if self._dependencies_met(stage_def.id):
                return stage_def
        return None

    def get_resume_context(self, max_tokens: int = 2000) -> str:
        """Build aggregated resume context from all completed stages.

        This is the key feature: it concatenates the essential context
        from each completed stage into a single prompt for the next agent.
        """
        lines = []
        lines.append(f"## WORKFLOW: {self.name}")
        lines.append(f"project: {self.project_path}")
        lines.append(f"status: {self.status} | stages: {len(self.stages)}")
        lines.append(f"completed: {self._completed_count()}/{len(self.stages)}")
        lines.append("")

        # Completed stages summaries
        for sc in sorted(self.stage_checkpoints, key=lambda s: s.stage_index):
            if sc.status != StageStatus.COMPLETED or not sc.checkpoint:
                continue

            cp = sc.checkpoint
            lines.append(f"### STAGE: {sc.stage_id} [{sc.performer}]")
            lines.append(f"purpose: {cp.purpose[:150]}")
            if cp.current_state:
                lines.append(f"achieved: {cp.current_state[:150]}")
            if cp.next_steps:
                # Carry forward only critical/high from completed stages
                for step in cp.next_steps:
                    if step.priority in ("critical", "high"):
                        lines.append(f"  ⚡ {step.action[:100]}")
            lines.append("")

        # Current stage info
        current = self.get_current_stage()
        if current:
            lines.append(f"### CURRENT STAGE: {current.stage_id}")
            lines.append(f"status: running | by: {current.performer}")
            if current.checkpoint:
                lines.append(current.checkpoint.to_compact(token_budget=500))
            lines.append("")

        # Next pending
        next_stage = self.get_next_pending_stage()
        if next_stage:
            lines.append(f"### NEXT STAGE: {next_stage.name}")
            if next_stage.description:
                lines.append(f"description: {next_stage.description}")
            if next_stage.agent:
                lines.append(f"agent: {next_stage.agent}")
            lines.append("")

        # Aggregated info
        if self.total_files_modified:
            lines.append(f"### ALL FILES ({len(self.total_files_modified)})")
            for f in self.total_files_modified[:15]:
                lines.append(f"  {f}")
            lines.append("")

        if self.total_decisions:
            lines.append(f"### KEY DECISIONS")
            for d in self.total_decisions[:5]:
                lines.append(f"  ★ {d[:100]}")
            lines.append("")

        if self.total_errors:
            lines.append(f"### ERRORS")
            for e in self.total_errors[:3]:
                lines.append(f"  ⚠ {e[:100]}")
            lines.append("")

        text = "\n".join(lines)

        # Rough token truncation
        estimated_tokens = len(text) // 3
        if estimated_tokens > max_tokens:
            text = text[: max_tokens * 3]

        return text

    # --- Private helpers ---

    def _validate_stage(self, stage_id: str) -> None:
        valid_ids = {s.id for s in self.stages}
        if stage_id not in valid_ids:
            raise ValueError(f"Unknown stage '{stage_id}'. Valid: {valid_ids}")

    def _check_dependencies(self, stage_id: str) -> None:
        stage_def = next(s for s in self.stages if s.id == stage_id)
        for dep_id in stage_def.depends_on:
            sc = self._get_stage_checkpoint(dep_id)
            if not sc or sc.status != StageStatus.COMPLETED:
                raise ValueError(
                    f"Stage '{stage_id}' requires '{dep_id}' to be completed first. "
                    f"Current status: {sc.status if sc else 'pending'}"
                )

    def _dependencies_met(self, stage_id: str) -> bool:
        stage_def = next((s for s in self.stages if s.id == stage_id), None)
        if not stage_def:
            return False
        for dep_id in stage_def.depends_on:
            sc = self._get_stage_checkpoint(dep_id)
            if not sc or sc.status != StageStatus.COMPLETED:
                return False
        return True

    def _get_stage_checkpoint(self, stage_id: str) -> Optional[StageCheckpoint]:
        for sc in self.stage_checkpoints:
            if sc.stage_id == stage_id:
                return sc
        return None

    def _get_stage_index(self, stage_id: str) -> int:
        for i, s in enumerate(self.stages):
            if s.id == stage_id:
                return i
        return 0

    def _completed_count(self) -> int:
        return sum(1 for sc in self.stage_checkpoints if sc.status == StageStatus.COMPLETED)

    def _update_overall_status(self) -> None:
        completed = self._completed_count()
        total = len(self.stages)

        if any(sc.status == StageStatus.FAILED for sc in self.stage_checkpoints):
            self.status = WorkflowStatus.FAILED
        elif completed == total:
            self.status = WorkflowStatus.COMPLETED
            self.completed_at = datetime.now()
        elif completed > 0:
            self.status = WorkflowStatus.RUNNING

        self.updated_at = datetime.now()
