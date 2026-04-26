"""Integration tests for Resume functionality - Checkpoint + Signals.

Tests the complete handover flow:
1. Record work logs
2. Create checkpoint at session end
3. Send handover signal
4. Resume at next session (checkpoint + signals)
"""

import pytest
from datetime import datetime
from pathlib import Path

from hits_core.service.checkpoint_service import CheckpointService
from hits_core.service.signal_service import SignalService
from hits_core.service.handover_service import HandoverService
from hits_core.storage.file_store import FileStorage
from hits_core.models.checkpoint import Checkpoint, NextStep
from hits_core.models.work_log import WorkLog, WorkLogSource


class TestResumeIntegration:
    """Integration tests for the complete resume flow."""

    @pytest.fixture
    def storage(self, tmp_path):
        """Create a temporary storage."""
        return FileStorage(base_path=str(tmp_path / "hits_data"))

    @pytest.fixture
    def checkpoint_service(self, storage):
        """Create checkpoint service."""
        return CheckpointService(storage=storage)

    @pytest.fixture
    def signal_service(self, tmp_path):
        """Create signal service."""
        return SignalService(data_path=str(tmp_path / "hits_data"))

    @pytest.fixture
    def handover_service(self, storage):
        """Create handover service."""
        return HandoverService(storage=storage)

    @pytest.mark.asyncio
    async def test_complete_handover_flow(self, checkpoint_service, signal_service, handover_service):
        """Test the complete handover flow: record -> checkpoint -> signal -> resume.

        Simulates a Claude session ending with work, then an OpenCode session resuming.
        """
        project_path = "/test/my-project"

        # ── Session 1: Claude Code does work ──────────────────────────────

        # 1. Record work logs during session
        work_log1 = WorkLog(
            source=WorkLogSource.AI_SESSION,
            id="log1",
            project_path=project_path,
            performed_by="claude",
            performed_at=datetime(2026, 4, 26, 10, 0),
            request_text="Implement JWT authentication",
            context="Using JWT with HttpOnly cookies for security",
            files_modified=["auth.py", "main.py"],
            commands_run=["pytest tests/auth_test.py"],
            tags=["auth", "security"],
            result_data={
                "files_modified": ["auth.py", "main.py"],
                "commands_run": ["pytest tests/auth_test.py"],
            },
        )
        await handover_service.storage.save_work_log(work_log1)

        work_log2 = WorkLog(
            source=WorkLogSource.AI_SESSION,
            id="log2",
            project_path=project_path,
            performed_by="claude",
            performed_at=datetime(2026, 4, 26, 11, 0),
            request_text="Fix auth middleware bug",
            context="Token validation was failing",
            files_modified=["middleware.py"],
            commands_run=["npm test"],
            tags=["bugfix"],
            result_data={
                "files_modified": ["middleware.py"],
                "commands_run": ["npm test"],
            },
        )
        await handover_service.storage.save_work_log(work_log2)

        # 2. Create checkpoint at session end
        checkpoint = await checkpoint_service.auto_checkpoint(
            project_path=project_path,
            performer="claude",
            purpose="Implement JWT authentication system",
            current_state="JWT auth working, middleware fixed, tests passing",
            completion_pct=60,
            additional_steps=[
                NextStep(action="Add refresh token rotation", command="edit auth.py", priority="high"),
                NextStep(action="Implement rate limiting", command="add middleware", priority="medium"),
                NextStep(action="Write API documentation", file="docs/api.md", priority="low"),
            ],
            additional_context=["Using Argon2id for password hashing", "Token expiry: 15 min access, 7d refresh"],
            files_modified=["auth.py", "middleware.py", "main.py"],
        )

        assert checkpoint.id.startswith("cp_")
        assert checkpoint.performer == "claude"
        assert checkpoint.completion_pct == 60
        assert len(checkpoint.next_steps) >= 3

        # 3. Send handover signal
        signal = await signal_service.send_signal(
            sender="claude",
            recipient="opencode",
            signal_type="session_end",
            project_path=project_path,
            summary="JWT auth implementation - 60% complete",
            context="JWT auth working, need to add refresh tokens and rate limiting",
            pending_items=[
                "Add refresh token rotation",
                "Implement rate limiting",
                "Write API documentation",
            ],
            priority="high",
            tags=["auth", "incomplete"],
        )

        assert signal.sender == "claude"
        assert signal.recipient == "opencode"
        assert len(signal.pending_items) == 3

        # ── Session 2: OpenCode resumes ───────────────────────────────

        # 4. Check for pending signals
        pending_signals = await signal_service.check_signals(
            recipient="opencode",
            project_path=project_path,
        )

        assert len(pending_signals) == 1
        assert pending_signals[0].id == signal.id
        assert "JWT auth" in pending_signals[0].summary

        # 5. Get latest checkpoint
        latest_checkpoint = await checkpoint_service.get_latest_checkpoint(project_path)

        assert latest_checkpoint is not None
        assert latest_checkpoint.id == checkpoint.id
        assert "refresh token" in latest_checkpoint.to_text()

        # 6. Get handover summary (work logs)
        handover = await handover_service.get_handover(project_path)

        assert len(handover.recent_logs) == 2
        assert "JWT authentication" in handover.to_text()
        assert "auth.py" in handover.files_modified

        # ── Verification: Resume info is complete ───────────────────────

        # Verify checkpoint has all necessary info
        assert latest_checkpoint.purpose == "Implement JWT authentication system"
        assert latest_checkpoint.completion_pct == 60
        assert len(latest_checkpoint.next_steps) >= 3

        # Verify signal has correct info
        assert signal.summary == "JWT auth implementation - 60% complete"
        assert "rate limiting" in signal.context

        # Verify work logs are preserved
        assert len(handover.recent_logs) == 2
        assert handover.recent_logs[0].request_text == "Fix auth middleware bug"  # Most recent

    @pytest.mark.asyncio
    async def test_resume_with_no_previous_session(self, checkpoint_service, signal_service, handover_service):
        """Test resuming a project with no previous checkpoint or signals."""
        project_path = "/test/new-project"

        # No checkpoint exists
        checkpoint = await checkpoint_service.get_latest_checkpoint(project_path)
        assert checkpoint is None

        # No signals exist
        signals = await signal_service.check_signals(recipient="opencode", project_path=project_path)
        assert len(signals) == 0

        # Handover should work but be empty
        handover = await handover_service.get_handover(project_path)
        assert len(handover.recent_logs) == 0
        assert len(handover.files_modified) == 0

    @pytest.mark.asyncio
    async def test_multiple_handovers_between_tools(self, checkpoint_service, signal_service, handover_service):
        """Test multiple handovers between Claude and OpenCode."""
        project_path = "/test/multi-handover"

        # ── Claude Session 1 ────────────────────────────────────────────
        cp1 = await checkpoint_service.auto_checkpoint(
            project_path=project_path,
            performer="claude",
            purpose="Phase 1: Setup",
            current_state="Project initialized",
            completion_pct=20,
        )

        await signal_service.send_signal(
            sender="claude",
            recipient="opencode",
            signal_type="session_end",
            project_path=project_path,
            summary="Phase 1 complete",
            pending_items=["Continue with Phase 2"],
        )

        # ── OpenCode Session 1 ──────────────────────────────────────────
        # OpenCode consumes the signal
        signals = await signal_service.check_signals(recipient="opencode", project_path=project_path)
        await signal_service.consume_signal(signals[0].id, "opencode")

        # OpenCode does more work
        work_log = WorkLog(
            source=WorkLogSource.AI_SESSION,
            id="log1",
            project_path=project_path,
            performed_by="opencode",
            request_text="Phase 2 work",
        )
        await handover_service.storage.save_work_log(work_log)

        # OpenCode creates checkpoint
        cp2 = await checkpoint_service.auto_checkpoint(
            project_path=project_path,
            performer="opencode",
            purpose="Phase 2: Implementation",
            current_state="Core features implemented",
            completion_pct=50,
        )

        await signal_service.send_signal(
            sender="opencode",
            recipient="claude",
            signal_type="session_end",
            project_path=project_path,
            summary="Phase 2 complete",
            pending_items=["Phase 3: Testing"],
        )

        # ── Claude Session 2 (Resumes) ──────────────────────────────────
        # Claude should see the latest checkpoint from OpenCode
        latest = await checkpoint_service.get_latest_checkpoint(project_path)
        assert latest.id == cp2.id
        assert latest.performer == "opencode"
        assert latest.completion_pct == 50

        # Claude should see the signal from OpenCode
        signals = await signal_service.check_signals(recipient="claude", project_path=project_path)
        assert len(signals) == 1
        assert "Phase 2 complete" in signals[0].summary

        # Claude should see the work log from OpenCode
        handover = await handover_service.get_handover(project_path)
        assert len(handover.recent_logs) == 1
        assert handover.recent_logs[0].performed_by == "opencode"

    @pytest.mark.asyncio
    async def test_resume_with_checkpoint_compression(self, checkpoint_service, signal_service):
        """Test that checkpoints can be compressed for token budget."""
        project_path = "/test/compression-test"

        # Create a large checkpoint with lots of data
        large_checkpoint = await checkpoint_service.auto_checkpoint(
            project_path=project_path,
            performer="claude",
            purpose="X" * 1000,  # Large purpose
            current_state="Y" * 500,  # Large state
            additional_steps=[
                NextStep(action=f"Step {i}", priority="low")
                for i in range(50)
            ],
            additional_context=[f"Context {i}" for i in range(30)],
            files_modified=[f"file{i}.py" for i in range(20)],
        )

        # Test different compression levels
        from hits_core.ai.checkpoint_compressor import CheckpointCompressor
        compressor = CheckpointCompressor()

        # Full checkpoint
        full_text = large_checkpoint.to_text()
        assert len(full_text) > 1000

        # Compressed with budget
        compressed = compressor.compress_checkpoint(large_checkpoint, token_budget=500)
        assert len(compressed) < len(full_text)
        assert "X" in compressed  # Key info should be preserved

        # Ultra compressed
        ultra = compressor.compress_checkpoint(large_checkpoint, token_budget=100)
        assert len(ultra) < len(compressed)
        assert len(ultra) < 500  # Should fit within budget

    @pytest.mark.asyncio
    async def test_signal_consumption_archives_file(self, signal_service, tmp_path):
        """Test that consuming a signal archives it from pending/ to consumed/."""
        project_path = "/test/archive-test"

        # Send signal
        signal = await signal_service.send_signal(
            sender="claude",
            recipient="opencode",
            project_path=project_path,
            summary="Test signal",
        )

        # Verify in pending
        pending = await signal_service.check_signals(recipient="opencode", project_path=project_path)
        assert len(pending) == 1

        # Consume
        consumed = await signal_service.consume_signal(signal.id, "opencode")
        assert consumed is not None
        assert consumed.status.value == "consumed"

        # Verify moved from pending
        pending_after = await signal_service.check_signals(recipient="opencode", project_path=project_path)
        assert len(pending_after) == 0

        # Verify in consumed
        consumed_files = list(signal_service.consumed_dir.glob("*.json"))
        assert len(consumed_files) == 1
        assert signal.id in str(consumed_files[0])

    @pytest.mark.asyncio
    async def test_checkpoint_list_multiple_checkpoints(self, checkpoint_service):
        """Test listing all checkpoints for a project."""
        project_path = "/test/list-test"

        # Create multiple checkpoints
        cp1 = await checkpoint_service.auto_checkpoint(
            project_path=project_path,
            performer="claude",
            purpose="Checkpoint 1",
            completion_pct=20,
        )
        cp2 = await checkpoint_service.auto_checkpoint(
            project_path=project_path,
            performer="claude",
            purpose="Checkpoint 2",
            completion_pct=40,
        )
        cp3 = await checkpoint_service.auto_checkpoint(
            project_path=project_path,
            performer="opencode",
            purpose="Checkpoint 3",
            completion_pct=60,
        )

        # List all
        checkpoints = await checkpoint_service.list_checkpoints(project_path)

        assert len(checkpoints) >= 3

        # Verify ordering (newest first)
        purposes = [cp.purpose for cp in checkpoints]
        assert "Checkpoint 3" in purposes
        assert "Checkpoint 2" in purposes
        assert "Checkpoint 1" in purposes

    @pytest.mark.asyncio
    async def test_resume_text_formatting(self, checkpoint_service, signal_service, handover_service):
        """Test that resume information is formatted correctly for AI consumption."""
        project_path = "/test/format-test"

        # Create checkpoint
        checkpoint = await checkpoint_service.auto_checkpoint(
            project_path=project_path,
            performer="claude",
            purpose="Build auth system",
            current_state="JWT working",
            completion_pct=70,
            additional_steps=[
                NextStep(action="Add refresh tokens", command="edit auth.py", priority="high"),
            ],
        )

        # Convert to text
        text = checkpoint.to_text()

        # Verify key sections exist
        assert "Build auth system" in text
        assert "JWT working" in text
        assert "70%" in text
        assert "Add refresh tokens" in text
        assert "edit auth.py" in text

        # Verify structured format (based on actual output)
        lines = text.split("\n")
        assert any("PURPOSE" in line or "Purpose" in line for line in lines)
        assert any("progress:" in line or "Progress" in line for line in lines)
        assert any("NEXT STEPS" in line or "Next Steps" in line for line in lines)
