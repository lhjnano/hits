"""Tests for Signal service - cross-tool handover via file-based signals."""

import pytest
from datetime import datetime
from pathlib import Path

from hits_core.service.signal_service import SignalService
from hits_core.models.signal import HandoverSignal, SignalStatus, SignalType


class TestSignalService:
    @pytest.fixture
    def signal_service(self, tmp_path):
        """Create a signal service with temporary directory."""
        return SignalService(data_path=str(tmp_path))

    @pytest.mark.asyncio
    async def test_send_signal(self, signal_service):
        """Test creating a new signal."""
        signal = await signal_service.send_signal(
            sender="claude",
            recipient="opencode",
            signal_type="session_end",
            project_path="/test/project",
            summary="JWT auth implementation complete",
            pending_items=["rate limiting", "refresh tokens"],
            priority="high",
        )

        assert signal.id.startswith("sig_")
        assert signal.sender == "claude"
        assert signal.recipient == "opencode"
        assert signal.signal_type == "session_end"
        assert signal.project_path == "/test/project"
        assert signal.summary == "JWT auth implementation complete"
        assert len(signal.pending_items) == 2
        assert signal.priority == "high"

        # Check file was created
        pending_files = list(signal_service.pending_dir.glob("*.json"))
        assert len(pending_files) == 1

    @pytest.mark.asyncio
    async def test_send_signal_with_tags(self, signal_service):
        """Test sending signal with tags."""
        signal = await signal_service.send_signal(
            sender="opencode",
            recipient="claude",
            signal_type="task_ready",
            project_path="/test/project",
            summary="Bug fix completed",
            tags=["bugfix", "auth"],
            priority="normal",
        )

        assert "bugfix" in signal.tags
        assert "auth" in signal.tags

    @pytest.mark.asyncio
    async def test_check_signals_no_signals(self, signal_service):
        """Test checking when no signals exist."""
        signals = await signal_service.check_signals(recipient="opencode")
        assert len(signals) == 0

    @pytest.mark.asyncio
    async def test_check_signals_with_signals(self, signal_service):
        """Test checking for pending signals."""
        # Send multiple signals
        await signal_service.send_signal(
            sender="claude",
            recipient="opencode",
            signal_type="session_end",
            summary="Signal 1",
        )
        await signal_service.send_signal(
            sender="cursor",
            recipient="opencode",
            signal_type="task_ready",
            summary="Signal 2",
        )
        await signal_service.send_signal(
            sender="claude",
            recipient="any",
            signal_type="session_end",
            summary="Signal 3",
        )

        # Check for opencode recipient (includes "any" signals)
        opencode_signals = await signal_service.check_signals(recipient="opencode")
        assert len(opencode_signals) == 3  # 2 for opencode + 1 for any

        # Check for claude recipient (includes "any" signals)
        claude_signals = await signal_service.check_signals(recipient="claude")
        assert len(claude_signals) == 1  # Only the "any" signal

    @pytest.mark.asyncio
    async def test_check_signals_by_project(self, signal_service):
        """Test filtering signals by project path."""
        await signal_service.send_signal(
            sender="claude",
            recipient="opencode",
            signal_type="session_end",
            project_path="/project/a",
            summary="Project A",
        )
        await signal_service.send_signal(
            sender="claude",
            recipient="opencode",
            signal_type="session_end",
            project_path="/project/b",
            summary="Project B",
        )

        # Check for specific project
        project_a_signals = await signal_service.check_signals(
            recipient="opencode",
            project_path="/project/a",
        )
        assert len(project_a_signals) == 1
        assert project_a_signals[0].summary == "Project A"

    @pytest.mark.asyncio
    async def test_check_signals_with_limit(self, signal_service):
        """Test limiting number of signals returned."""
        # Send 5 signals
        for i in range(5):
            await signal_service.send_signal(
                sender="claude",
                recipient="opencode",
                signal_type="session_end",
                summary=f"Signal {i}",
            )

        # Check with limit
        signals = await signal_service.check_signals(
            recipient="opencode",
            limit=3,
        )
        assert len(signals) == 3

    @pytest.mark.asyncio
    async def test_consume_signal(self, signal_service):
        """Test consuming a signal."""
        # Send a signal
        signal = await signal_service.send_signal(
            sender="claude",
            recipient="opencode",
            signal_type="session_end",
            summary="Test signal",
        )

        # Verify it's in pending
        pending_signals = await signal_service.check_signals(recipient="opencode")
        assert len(pending_signals) == 1

        # Consume it
        consumed_signal = await signal_service.consume_signal(
            signal_id=signal.id,
            consumed_by="opencode",
        )

        assert consumed_signal.id == signal.id
        assert consumed_signal.status == SignalStatus.CONSUMED
        assert consumed_signal.consumed_by == "opencode"

        # Verify it's no longer in pending
        pending_signals = await signal_service.check_signals(recipient="opencode")
        assert len(pending_signals) == 0

    @pytest.mark.asyncio
    async def test_consume_signal_moves_file(self, signal_service):
        """Test that consuming moves file from pending/ to consumed/."""
        signal = await signal_service.send_signal(
            sender="claude",
            recipient="opencode",
            signal_type="session_end",
            summary="Test signal",
        )

        # Get pending file path
        pending_files = list(signal_service.pending_dir.glob(f"*{signal.id}*.json"))
        assert len(pending_files) == 1
        pending_file = pending_files[0]

        # Consume signal
        await signal_service.consume_signal(signal_id=signal.id, consumed_by="opencode")

        # Check file was moved
        assert not pending_file.exists()

        consumed_files = list(signal_service.consumed_dir.glob(f"*{signal.id}*.json"))
        assert len(consumed_files) == 1

    @pytest.mark.asyncio
    async def test_consume_nonexistent_signal(self, signal_service):
        """Test consuming a signal that doesn't exist."""
        result = await signal_service.consume_signal(
            signal_id="sig_nonexistent",
            consumed_by="opencode",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_auto_cleanup_consumed(self, signal_service):
        """Test automatic cleanup of old consumed signals."""
        import time

        # Send and consume a signal
        signal = await signal_service.send_signal(
            sender="claude",
            recipient="opencode",
            summary="Old signal",
        )
        await signal_service.consume_signal(signal.id, "opencode")

        # Manually modify file timestamp to make it old
        consumed_file = list(signal_service.consumed_dir.glob(f"*{signal.id}*.json"))[0]
        old_time = time.time() - (72 * 3600 + 100)  # 72 hours + 100 seconds
        import os
        os.utime(consumed_file, (old_time, old_time))

        # Cleanup should remove old files
        await signal_service.cleanup_consumed(max_age_hours=72)

        # Verify file was removed
        remaining = list(signal_service.consumed_dir.glob("*.json"))
        assert len(remaining) == 0

    @pytest.mark.asyncio
    async def test_invalid_sender_recipient_normalization(self, signal_service):
        """Test that invalid sender/recipient are normalized."""
        signal = await signal_service.send_signal(
            sender="INVALID_TOOL",
            recipient="ALSO_INVALID",
            summary="Test normalization",
        )

        # Should be normalized to "unknown" and "any"
        assert signal.sender == "unknown"
        assert signal.recipient == "any"
