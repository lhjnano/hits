"""Tests for checkpoint model, service, and compressor."""

import pytest
import asyncio
from pathlib import Path
from datetime import datetime

from hits_core.models.checkpoint import (
    Checkpoint, NextStep, FileDelta, Block, Decision,
    StepPriority, ChangeType,
)
from hits_core.ai.checkpoint_compressor import CheckpointCompressor
from hits_core.storage.file_store import FileStorage


class TestCheckpointModel:
    def test_checkpoint_creation(self):
        cp = Checkpoint(
            id="cp_test123",
            project_path="/test/project",
            performer="claude",
            purpose="Test checkpoint",
            completion_pct=50,
        )
        assert cp.id == "cp_test123"
        assert cp.performer == "claude"
        assert cp.completion_pct == 50
        assert cp.next_steps == []
        assert cp.files_delta == []

    def test_checkpoint_with_steps(self):
        cp = Checkpoint(
            id="cp_test",
            project_path="/test",
            performer="opencode",
            purpose="Test",
            next_steps=[
                NextStep(action="Do A", command="cmd_a", priority="high"),
                NextStep(action="Do B", file="b.py", priority="critical"),
                NextStep(action="Do C", priority="low"),
            ],
        )
        assert len(cp.next_steps) == 3
        assert cp.next_steps[0].priority == "high"
        assert cp.next_steps[1].priority == "critical"
        assert cp.next_steps[1].file == "b.py"

    def test_checkpoint_to_text(self):
        cp = Checkpoint(
            id="cp_test",
            project_path="/test/proj",
            project_name="proj",
            performer="claude",
            purpose="Build auth system",
            current_state="JWT working",
            completion_pct=70,
            next_steps=[
                NextStep(action="Add refresh tokens", command="edit auth.py", priority="high"),
            ],
            required_context=["Using Argon2id"],
            files_delta=[
                FileDelta(path="auth.py", change_type="modified", description="Added JWT"),
            ],
            decisions_made=[
                Decision(decision="Use HttpOnly cookies", rationale="Security"),
            ],
            blocks=[
                Block(issue="Redis down", workaround="Use mock"),
            ],
        )
        text = cp.to_text()
        assert "Build auth system" in text
        assert "JWT working" in text
        assert "Add refresh tokens" in text
        assert "edit auth.py" in text
        assert "Using Argon2id" in text
        assert "HttpOnly cookies" in text
        assert "Redis down" in text
        assert "auth.py" in text

    def test_checkpoint_to_compact(self):
        cp = Checkpoint(
            id="cp_test",
            project_path="/test/proj",
            project_name="proj",
            performer="claude",
            purpose="Test purpose",
            completion_pct=30,
            next_steps=[
                NextStep(action="Step A", priority="critical"),
                NextStep(action="Step B", priority="high"),
                NextStep(action="Step C", priority="low"),
            ],
            required_context=["Context 1"],
        )
        compact = cp.to_compact(token_budget=2000)
        assert "Test purpose" in compact

        ultra = cp.to_compact(token_budget=50)
        assert "Test purpose" in ultra
        assert len(ultra) < len(compact)

    def test_file_delta_enum(self):
        fd = FileDelta(path="test.py", change_type="created")
        assert fd.change_type == "created"

        fd2 = FileDelta(path="old.py", change_type="deleted")
        assert fd2.change_type == "deleted"

    def test_block_with_workaround(self):
        b = Block(issue="Can't connect", workaround="Use localhost", severity="critical")
        assert b.workaround == "Use localhost"
        assert b.severity == "critical"


class TestCheckpointCompressor:
    def setup_method(self):
        self.compressor = CheckpointCompressor()

    def test_estimate_tokens_empty(self):
        assert self.compressor.estimate_tokens("") == 0

    def test_estimate_tokens_english(self):
        tokens = self.compressor.estimate_tokens("Hello world this is a test")
        assert tokens > 0
        assert tokens < 20  # ~7 tokens

    def test_estimate_tokens_korean(self):
        tokens = self.compressor.estimate_tokens("안녕하세요 세상입니다")
        assert tokens > 0

    def test_compress_full(self):
        cp = Checkpoint(
            id="cp_test",
            project_path="/test",
            performer="claude",
            purpose="Small checkpoint",
            completion_pct=100,
        )
        result = self.compressor.compress_checkpoint(cp, token_budget=2000)
        assert "Small checkpoint" in result

    def test_compress_l1(self):
        cp = Checkpoint(
            id="cp_test",
            project_path="/test",
            project_name="test",
            performer="claude",
            purpose="X" * 500,  # Large purpose
            completion_pct=50,
            next_steps=[
                NextStep(action=f"Step {i}", priority="low")
                for i in range(10)
            ],
        )
        result = self.compressor.compress_checkpoint(cp, token_budget=300)
        assert "X" in result  # Purpose truncated but present

    def test_compress_l3_ultra(self):
        cp = Checkpoint(
            id="cp_test",
            project_path="/test",
            project_name="test",
            performer="claude",
            purpose="Ultra test",
            completion_pct=10,
            next_steps=[
                NextStep(action="Critical step", priority="critical"),
            ],
        )
        result = self.compressor.compress_checkpoint(cp, token_budget=30)
        assert "Ultra test" in result

    def test_estimate_checkpoint_tokens(self):
        cp = Checkpoint(
            id="cp_test",
            project_path="/test",
            performer="claude",
            purpose="Token estimation test",
            current_state="Testing",
            next_steps=[NextStep(action="Step 1")],
            required_context=["Context A"],
            decisions_made=[Decision(decision="Decided X")],
            blocks=[Block(issue="Blocked by Y")],
        )
        result = self.compressor.estimate_checkpoint_tokens(cp)
        assert "full" in result
        assert "l1" in result
        assert "l2" in result
        assert "l3" in result
        assert "field_breakdown" in result
        # Each level should be <= full; L3 may slightly exceed L2 for small inputs
        assert result["l1"] <= result["full"]


class TestCheckpointService:
    @pytest.fixture
    def tmp_storage(self, tmp_path):
        return FileStorage(base_path=str(tmp_path / "hits_data"))

    @pytest.mark.asyncio
    async def test_auto_checkpoint(self, tmp_storage):
        from hits_core.service.checkpoint_service import CheckpointService
        service = CheckpointService(storage=tmp_storage)

        cp = await service.auto_checkpoint(
            project_path="/test/project",
            performer="claude",
            purpose="Test auto-checkpoint",
            current_state="Testing",
            completion_pct=50,
        )
        assert cp.id.startswith("cp_")
        assert cp.performer == "claude"
        assert cp.completion_pct == 50
        assert cp.project_path == "/test/project"

    @pytest.mark.asyncio
    async def test_get_latest_checkpoint(self, tmp_storage):
        from hits_core.service.checkpoint_service import CheckpointService
        service = CheckpointService(storage=tmp_storage)

        # Create two checkpoints
        cp1 = await service.auto_checkpoint(
            project_path="/test/proj",
            performer="claude",
            purpose="First",
            completion_pct=30,
        )
        cp2 = await service.auto_checkpoint(
            project_path="/test/proj",
            performer="opencode",
            purpose="Second",
            completion_pct=60,
        )

        latest = await service.get_latest_checkpoint("/test/proj")
        assert latest is not None
        assert latest.purpose == "Second"
        assert latest.completion_pct == 60

    @pytest.mark.asyncio
    async def test_list_checkpoints(self, tmp_storage):
        from hits_core.service.checkpoint_service import CheckpointService
        service = CheckpointService(storage=tmp_storage)

        await service.auto_checkpoint(
            project_path="/test/proj",
            performer="claude",
            purpose="CP1",
        )
        await service.auto_checkpoint(
            project_path="/test/proj",
            performer="claude",
            purpose="CP2",
        )

        cps = await service.list_checkpoints("/test/proj")
        assert len(cps) >= 2

    @pytest.mark.asyncio
    async def test_list_all_projects(self, tmp_storage):
        from hits_core.service.checkpoint_service import CheckpointService
        service = CheckpointService(storage=tmp_storage)

        await service.auto_checkpoint(
            project_path="/test/projA",
            performer="claude",
            purpose="Project A",
        )
        await service.auto_checkpoint(
            project_path="/test/projB",
            performer="opencode",
            purpose="Project B",
        )

        projects = await service.list_all_projects()
        assert len(projects) == 2
        paths = [p["project_path"] for p in projects]
        assert "/test/projA" in paths
        assert "/test/projB" in paths

    @pytest.mark.asyncio
    async def test_checkpoint_with_explicit_steps(self, tmp_storage):
        from hits_core.service.checkpoint_service import CheckpointService
        service = CheckpointService(storage=tmp_storage)

        cp = await service.auto_checkpoint(
            project_path="/test/proj",
            performer="claude",
            purpose="With steps",
            additional_steps=[
                NextStep(action="Step A", command="cmd_a", priority="high"),
                NextStep(action="Step B", file="b.py", priority="medium"),
            ],
            additional_context=["Must know this"],
            files_modified=["file1.py", "file2.py"],
        )
        assert len(cp.next_steps) >= 2
        assert cp.next_steps[0].action == "Step A"
        assert any(fd.path == "file1.py" for fd in cp.files_delta)
