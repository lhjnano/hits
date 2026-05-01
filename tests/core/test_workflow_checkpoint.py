"""Tests for WorkflowCheckpoint model and service.

Covers:
- WorkflowCheckpoint model: creation, stage lifecycle, dependency checks
- StageCheckpoint: status transitions
- WorkflowCheckpointService: CRUD, stage ops, resume
- Resume context generation
- Edge cases: circular deps, unknown stages, restart failed stage
"""

import sys
import tempfile
from pathlib import Path
from datetime import datetime

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from hits_core.models.workflow_checkpoint import (
    WorkflowCheckpoint,
    StageDefinition,
    StageCheckpoint,
    StageStatus,
    WorkflowStatus,
)
from hits_core.models.checkpoint import (
    Checkpoint,
    NextStep,
    StepPriority,
    FileDelta,
    ChangeType,
    Decision,
    Block,
)


# ============================================================================
# Test fixtures
# ============================================================================

def make_stages() -> list[StageDefinition]:
    """Create a typical 3-stage pipeline."""
    return [
        StageDefinition(id="s1", name="Data Collection", agent="data-collector"),
        StageDefinition(id="s2", name="Model Design", agent="designer", depends_on=["s1"]),
        StageDefinition(id="s3", name="Training", agent="trainer", depends_on=["s2"]),
    ]


def make_parallel_stages() -> list[StageDefinition]:
    """Create a pipeline with parallel stages."""
    return [
        StageDefinition(id="collect", name="Data Collection", agent="collector"),
        StageDefinition(id="analyze", name="Analysis", agent="analyst"),
        StageDefinition(id="design", name="Design", agent="designer", depends_on=["collect", "analyze"]),
    ]


def make_checkpoint(
    purpose: str = "Test checkpoint",
    performer: str = "test-agent",
    completion: int = 80,
) -> Checkpoint:
    return Checkpoint(
        id=f"cp_test_{completion}",
        project_path="/test/project",
        project_name="project",
        performer=performer,
        purpose=purpose,
        current_state=f"Completed {completion}%",
        completion_pct=completion,
        next_steps=[
            NextStep(action="Do next thing", priority=StepPriority.HIGH),
        ],
        files_delta=[
            FileDelta(path="src/main.py", change_type=ChangeType.MODIFIED),
        ],
        decisions_made=[
            Decision(decision="Use FastAPI", rationale="Better async support"),
        ],
        blocks=[],
    )


def make_workflow(stages: list[StageDefinition] = None) -> WorkflowCheckpoint:
    return WorkflowCheckpoint(
        workflow_id="wf_test123",
        project_path="/test/project",
        project_name="project",
        name="Test Pipeline",
        stages=stages or make_stages(),
    )


# ============================================================================
# Model: WorkflowCheckpoint creation
# ============================================================================

class TestWorkflowCheckpointCreation:

    def test_basic_creation(self):
        wf = make_workflow()
        assert wf.workflow_id == "wf_test123"
        assert wf.status == WorkflowStatus.PENDING
        assert len(wf.stages) == 3

    def test_empty_workflow(self):
        wf = WorkflowCheckpoint(
            workflow_id="wf_empty",
            project_path="/test",
        )
        assert len(wf.stages) == 0
        assert wf.status == WorkflowStatus.PENDING

    def test_parallel_stages(self):
        wf = make_workflow(make_parallel_stages())
        assert len(wf.stages) == 3
        # design depends on both collect and analyze
        design = next(s for s in wf.stages if s.id == "design")
        assert "collect" in design.depends_on
        assert "analyze" in design.depends_on


# ============================================================================
# Model: Stage lifecycle
# ============================================================================

class TestStageLifecycle:

    def test_start_first_stage(self):
        wf = make_workflow()
        sc = wf.start_stage("s1", performer="opencode")
        assert sc.status == StageStatus.RUNNING
        assert sc.performer == "opencode"
        assert wf.status == WorkflowStatus.RUNNING

    def test_complete_stage(self):
        wf = make_workflow()
        wf.start_stage("s1")
        cp = make_checkpoint()
        sc = wf.complete_stage("s1", checkpoint=cp)
        assert sc.status == StageStatus.COMPLETED
        assert sc.checkpoint is not None
        assert wf.status == WorkflowStatus.RUNNING  # not all done

    def test_complete_all_stages(self):
        wf = make_workflow()
        for sid in ["s1", "s2", "s3"]:
            wf.start_stage(sid)
            wf.complete_stage(sid, checkpoint=make_checkpoint(purpose=f"Stage {sid}"))
        assert wf.status == WorkflowStatus.COMPLETED
        assert wf.completed_at is not None

    def test_fail_stage(self):
        wf = make_workflow()
        wf.start_stage("s1")
        sc = wf.fail_stage("s1", error="OOM error")
        assert sc.status == StageStatus.FAILED
        assert sc.error == "OOM error"
        assert wf.status == WorkflowStatus.FAILED

    def test_fail_without_start_auto_starts(self):
        wf = make_workflow()
        sc = wf.fail_stage("s1", error="Crashed")
        assert sc.status == StageStatus.FAILED

    def test_get_current_stage(self):
        wf = make_workflow()
        assert wf.get_current_stage() is None
        wf.start_stage("s1")
        current = wf.get_current_stage()
        assert current is not None
        assert current.stage_id == "s1"

    def test_get_stage_status_default_pending(self):
        wf = make_workflow()
        assert wf.get_stage_status("s1") == StageStatus.PENDING


# ============================================================================
# Model: Dependency enforcement
# ============================================================================

class TestDependencies:

    def test_cannot_start_with_unmet_deps(self):
        wf = make_workflow()
        with pytest.raises(ValueError, match="requires"):
            wf.start_stage("s2")  # s2 depends on s1

    def test_can_start_after_dep_completed(self):
        wf = make_workflow()
        wf.start_stage("s1")
        wf.complete_stage("s1", checkpoint=make_checkpoint())
        # Now s2 should be startable
        sc = wf.start_stage("s2")
        assert sc.status == StageStatus.RUNNING

    def test_parallel_stages_independent(self):
        wf = make_workflow(make_parallel_stages())
        # collect and analyze have no deps — both can start
        wf.start_stage("collect")
        wf.start_stage("analyze")
        assert wf.get_stage_status("collect") == StageStatus.RUNNING
        assert wf.get_stage_status("analyze") == StageStatus.RUNNING

    def test_parallel_merge_after_both_complete(self):
        wf = make_workflow(make_parallel_stages())
        wf.start_stage("collect")
        wf.complete_stage("collect", checkpoint=make_checkpoint())
        wf.start_stage("analyze")
        wf.complete_stage("analyze", checkpoint=make_checkpoint())
        # Now design should be startable
        sc = wf.start_stage("design")
        assert sc.status == StageStatus.RUNNING

    def test_unknown_stage_raises(self):
        wf = make_workflow()
        with pytest.raises(ValueError, match="Unknown stage"):
            wf.start_stage("nonexistent")


# ============================================================================
# Model: get_next_pending_stage
# ============================================================================

class TestGetNextPending:

    def test_first_stage_is_pending(self):
        wf = make_workflow()
        next_s = wf.get_next_pending_stage()
        assert next_s is not None
        assert next_s.id == "s1"

    def test_no_pending_after_all_complete(self):
        wf = make_workflow()
        for sid in ["s1", "s2", "s3"]:
            wf.start_stage(sid)
            wf.complete_stage(sid, checkpoint=make_checkpoint())
        assert wf.get_next_pending_stage() is None

    def test_skips_running_stage(self):
        wf = make_workflow()
        wf.start_stage("s1")
        # s1 is running, so get_next_pending should not return it
        next_s = wf.get_next_pending_stage()
        assert next_s is None  # s1 is running, s2/s3 blocked


# ============================================================================
# Model: Aggregated results
# ============================================================================

class TestAggregatedResults:

    def test_files_aggregated_across_stages(self):
        wf = make_workflow()
        cp1 = make_checkpoint()
        cp1.files_delta = [FileDelta(path="a.py"), FileDelta(path="b.py")]

        wf.start_stage("s1")
        wf.complete_stage("s1", checkpoint=cp1)

        cp2 = make_checkpoint()
        cp2.files_delta = [FileDelta(path="c.py"), FileDelta(path="a.py")]  # a.py duplicated

        wf.start_stage("s2")
        wf.complete_stage("s2", checkpoint=cp2)

        assert "a.py" in wf.total_files_modified
        assert "b.py" in wf.total_files_modified
        assert "c.py" in wf.total_files_modified
        assert len(wf.total_files_modified) == 3  # no duplicates

    def test_decisions_aggregated(self):
        wf = make_workflow()
        cp = make_checkpoint()
        wf.start_stage("s1")
        wf.complete_stage("s1", checkpoint=cp)
        assert len(wf.total_decisions) > 0

    def test_errors_aggregated(self):
        wf = make_workflow()
        wf.start_stage("s1")
        wf.fail_stage("s1", error="Test error")
        assert "Test error" in wf.total_errors

    def test_tokens_tracked(self):
        wf = make_workflow()
        wf.start_stage("s1")
        wf.complete_stage("s1", tokens_used=500)
        assert wf.total_tokens_used == 500


# ============================================================================
# Model: Resume context generation
# ============================================================================

class TestResumeContext:

    def test_empty_workflow_context(self):
        wf = make_workflow()
        ctx = wf.get_resume_context()
        assert "WORKFLOW" in ctx
        assert "Test Pipeline" in ctx

    def test_completed_stages_in_context(self):
        wf = make_workflow()
        wf.start_stage("s1")
        wf.complete_stage("s1", checkpoint=make_checkpoint(purpose="Collected data"))
        ctx = wf.get_resume_context()
        assert "STAGE" in ctx
        assert "Collected data" in ctx

    def test_next_stage_in_context(self):
        wf = make_workflow()
        wf.start_stage("s1")
        wf.complete_stage("s1", checkpoint=make_checkpoint())
        ctx = wf.get_resume_context()
        assert "NEXT STAGE" in ctx
        assert "Model Design" in ctx

    def test_token_budget_truncation(self):
        wf = make_workflow()
        wf.start_stage("s1")
        big_cp = make_checkpoint(purpose="x" * 5000)
        wf.complete_stage("s1", checkpoint=big_cp)
        ctx = wf.get_resume_context(max_tokens=100)
        # Should be truncated (roughly 100 * 3 = 300 chars)
        assert len(ctx) < 1000

    def test_files_in_context(self):
        wf = make_workflow()
        cp = make_checkpoint()
        wf.start_stage("s1")
        wf.complete_stage("s1", checkpoint=cp)
        ctx = wf.get_resume_context()
        assert "main.py" in ctx


# ============================================================================
# Service: WorkflowCheckpointService
# ============================================================================

class TestWorkflowCheckpointService:

    @pytest.fixture
    def service(self, tmp_path):
        from hits_core.service.workflow_checkpoint_service import WorkflowCheckpointService
        from hits_core.storage.file_store import FileStorage
        storage = FileStorage(base_path=tmp_path)
        return WorkflowCheckpointService(storage=storage)

    @pytest.mark.asyncio
    async def test_create_workflow(self, service):
        wf = await service.create_workflow(
            project_path="/test/project",
            name="Test Pipeline",
            stages=make_stages(),
        )
        assert wf.workflow_id.startswith("wf_")
        assert wf.status == WorkflowStatus.PENDING

    @pytest.mark.asyncio
    async def test_get_workflow(self, service):
        created = await service.create_workflow(
            project_path="/test/project",
            name="Test Pipeline",
            stages=make_stages(),
        )
        loaded = await service.get_workflow(created.workflow_id)
        assert loaded is not None
        assert loaded.workflow_id == created.workflow_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_workflow(self, service):
        assert await service.get_workflow("wf_nonexistent") is None

    @pytest.mark.asyncio
    async def test_list_workflows(self, service):
        await service.create_workflow("/test/p1", "Pipeline 1", make_stages())
        await service.create_workflow("/test/p2", "Pipeline 2", make_stages())
        wfs = await service.list_workflows()
        assert len(wfs) == 2

    @pytest.mark.asyncio
    async def test_list_workflows_filtered(self, service):
        await service.create_workflow("/test/p1", "Pipeline 1", make_stages())
        await service.create_workflow("/test/p2", "Pipeline 2", make_stages())
        wfs = await service.list_workflows(project_path="/test/p1")
        assert len(wfs) == 1

    @pytest.mark.asyncio
    async def test_start_stage_via_service(self, service):
        wf = await service.create_workflow("/test/p1", "Test", make_stages())
        updated = await service.start_stage(wf.workflow_id, "s1", performer="claude")
        assert updated.get_stage_status("s1") == StageStatus.RUNNING

    @pytest.mark.asyncio
    async def test_complete_stage_via_service(self, service):
        wf = await service.create_workflow("/test/p1", "Test", make_stages())
        await service.start_stage(wf.workflow_id, "s1")
        updated = await service.complete_stage(
            wf.workflow_id, "s1", checkpoint=make_checkpoint()
        )
        assert updated.get_stage_status("s1") == StageStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_fail_stage_via_service(self, service):
        wf = await service.create_workflow("/test/p1", "Test", make_stages())
        await service.start_stage(wf.workflow_id, "s1")
        updated = await service.fail_stage(wf.workflow_id, "s1", "API error")
        assert updated.get_stage_status("s1") == StageStatus.FAILED
        assert updated.status == WorkflowStatus.FAILED

    @pytest.mark.asyncio
    async def test_resume_workflow(self, service):
        wf = await service.create_workflow("/test/p1", "Test", make_stages())
        await service.start_stage(wf.workflow_id, "s1")
        await service.complete_stage(wf.workflow_id, "s1", checkpoint=make_checkpoint())

        result = await service.resume_workflow(wf.workflow_id)
        assert result is not None
        assert result["next_stage"] is not None
        assert result["next_stage"]["id"] == "s2"
        assert result["completed_stages"] == 1
        assert "resume_context" in result

    @pytest.mark.asyncio
    async def test_resume_nonexistent(self, service):
        result = await service.resume_workflow("wf_nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_resume_context(self, service):
        wf = await service.create_workflow("/test/p1", "Test", make_stages())
        await service.start_stage(wf.workflow_id, "s1")
        await service.complete_stage(wf.workflow_id, "s1", checkpoint=make_checkpoint())

        ctx = await service.get_resume_context(wf.workflow_id)
        assert ctx is not None
        assert "WORKFLOW" in ctx

    @pytest.mark.asyncio
    async def test_full_pipeline_lifecycle(self, service):
        """End-to-end: create → run all stages → completed."""
        wf = await service.create_workflow("/test/ml", "ML Pipeline", make_stages())

        for sid in ["s1", "s2", "s3"]:
            await service.start_stage(wf.workflow_id, sid, performer="agent")
            await service.complete_stage(
                wf.workflow_id, sid,
                checkpoint=make_checkpoint(purpose=f"Stage {sid} done"),
                tokens_used=1000,
            )

        final = await service.get_workflow(wf.workflow_id)
        assert final.status == WorkflowStatus.COMPLETED
        assert final.total_tokens_used == 3000
        assert final.completed_at is not None

    @pytest.mark.asyncio
    async def test_restart_after_failure(self, service):
        """Failed stage can be restarted."""
        wf = await service.create_workflow("/test/p1", "Test", make_stages())
        await service.start_stage(wf.workflow_id, "s1")
        await service.fail_stage(wf.workflow_id, "s1", "Transient error")

        # Restart
        updated = await service.start_stage(wf.workflow_id, "s1", performer="retry-agent")
        assert updated.get_stage_status("s1") == StageStatus.RUNNING

        # Complete
        await service.complete_stage(wf.workflow_id, "s1", checkpoint=make_checkpoint())
        final = await service.get_workflow(wf.workflow_id)
        assert final.get_stage_status("s1") == StageStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_workflow_not_found_raises(self, service):
        with pytest.raises(ValueError, match="not found"):
            await service.start_stage("wf_nonexistent", "s1")

        with pytest.raises(ValueError, match="not found"):
            await service.complete_stage("wf_nonexistent", "s1")

        with pytest.raises(ValueError, match="not found"):
            await service.fail_stage("wf_nonexistent", "s1", "error")
