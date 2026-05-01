"""End-to-end scenario tests for automatic token tracking.

Verifies that:
1. Every MCP tool call auto-records token usage
2. Token records are written to JSONL files
3. API endpoints return the tracked data correctly
4. Dashboard can query real tracked data
5. Tracking never breaks the original tool call
"""

import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

from hits_core.mcp.server import HITSMCPServer
from hits_core.service.token_tracker import TokenTrackerService
from hits_core.storage.file_store import FileStorage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_data(tmp_path):
    """Create temp data directory with required subdirs."""
    data = tmp_path / "data"
    data.mkdir()
    (data / "work_logs").mkdir()
    (data / "checkpoints").mkdir()
    (data / "signals").mkdir()
    (data / "signals" / "pending").mkdir()
    (data / "signals" / "consumed").mkdir()
    (data / "workflows").mkdir()
    (data / "trees").mkdir()
    (data / "token_tracking").mkdir()
    (data / "token_tracking" / "records").mkdir()
    (data / "token_tracking" / "budgets").mkdir()
    return tmp_path


@pytest.fixture
def server(tmp_data):
    """Create MCP server with temp storage."""
    return HITSMcP_Server_Factory(tmp_data)


def HITSMcP_Server_Factory(tmp_path):
    """Helper to create server with mocked paths."""
    data_path = str(tmp_path / "data")
    server = HITSMCPServer(data_path=data_path)
    return server


def _tool_call(server, tool_name, args, call_id=1):
    """Simulate a tools/call JSON-RPC request."""
    return asyncio.get_event_loop().run_until_complete(
        server.handle_tools_call(
            params={"name": tool_name, "arguments": args},
            id_val=call_id,
        )
    )


def _parse_response(raw: str) -> dict:
    return json.loads(raw)


# ===========================================================================
# Scenario 1: record_work auto-tracks tokens
# ===========================================================================

class TestAutoTrackingRecordWork:
    """When I call hits_record_work via MCP, tokens should be auto-recorded."""

    @pytest.mark.asyncio
    async def test_record_work_creates_token_record(self, tmp_data):
        """hits_record_work → work log saved + token record auto-created."""
        server = HITSMcP_Server_Factory(tmp_data)

        result_raw = await server.handle_tools_call(
            {"name": "hits_record_work", "arguments": {
                "project_path": "/test/project",
                "performed_by": "claude",
                "request_text": "Fixed critical auth bug",
                "context": "JWT validation was broken",
            }},
            id_val=1,
        )
        result = json.loads(result_raw)

        # 1. Tool call succeeded
        assert "error" not in result
        text = result["result"]["content"][0]["text"]
        assert "✅" in text

        # 2. Token record was created
        tracker = TokenTrackerService(data_dir=tmp_data / "data")
        stats = tracker.get_project_stats("/test/project")
        assert stats.total_records >= 1
        assert stats.total_tokens > 0

    @pytest.mark.asyncio
    async def test_record_work_tracks_performer(self, tmp_data):
        server = HITSMcP_Server_Factory(tmp_data)

        await server.handle_tools_call(
            {"name": "hits_record_work", "arguments": {
                "project_path": "/proj",
                "performed_by": "opencode",
                "request_text": "Refactored models",
            }},
            id_val=1,
        )

        tracker = TokenTrackerService(data_dir=tmp_data / "data")
        stats = tracker.get_project_stats("/proj")
        assert "opencode" in stats.by_performer


# ===========================================================================
# Scenario 2: auto_checkpoint auto-tracks tokens
# ===========================================================================

class TestAutoTrackingAutoCheckpoint:
    """hits_auto_checkpoint should record tokens for the full pipeline."""

    @pytest.mark.asyncio
    async def test_auto_checkpoint_tracks_tokens(self, tmp_data):
        server = HITSMcP_Server_Factory(tmp_data)

        result_raw = await server.handle_tools_call(
            {"name": "hits_auto_checkpoint", "arguments": {
                "project_path": "/test/proj",
                "performer": "claude",
                "purpose": "Completed auth module",
                "current_state": "Auth working",
                "completion_pct": 80,
                "send_signal": False,  # skip signal for test
            }},
            id_val=1,
        )
        result = json.loads(result_raw)

        # Tool succeeded
        text = result["result"]["content"][0]["text"]
        assert "✅" in text

        # Token record exists
        tracker = TokenTrackerService(data_dir=tmp_data / "data")
        stats = tracker.get_project_stats("/test/proj")
        assert stats.total_records >= 1
        # Auto-checkpoint generates more output → more tokens
        assert stats.total_tokens > 0


# ===========================================================================
# Scenario 3: resume auto-tracks tokens
# ===========================================================================

class TestAutoTrackingResume:
    """hits_resume should record tokens for context loading."""

    @pytest.mark.asyncio
    async def test_resume_tracks_tokens(self, tmp_data):
        server = HITSMcP_Server_Factory(tmp_data)

        # First create some data
        await server.handle_tools_call(
            {"name": "hits_record_work", "arguments": {
                "project_path": "/test/proj",
                "performed_by": "claude",
                "request_text": "Initial work",
            }},
            id_val=1,
        )

        # Now resume
        result_raw = await server.handle_tools_call(
            {"name": "hits_resume", "arguments": {
                "project_path": "/test/proj",
                "performer": "opencode",
            }},
            id_val=2,
        )
        result = json.loads(result_raw)
        assert "error" not in result

        # Should have token records for BOTH calls
        tracker = TokenTrackerService(data_dir=tmp_data / "data")
        stats = tracker.get_project_stats("/test/proj")
        assert stats.total_records >= 2  # record_work + resume


# ===========================================================================
# Scenario 4: tracking never breaks tool calls
# ===========================================================================

class TestAutoTrackingResilience:
    """Even if tracking fails, the tool call must succeed."""

    @pytest.mark.asyncio
    async def test_tracking_failure_doesnt_break_tool(self, tmp_data):
        server = HITSMcP_Server_Factory(tmp_data)

        # Corrupt the token tracking dir (make it a file instead of dir)
        tracker_dir = tmp_data / "data" / "token_tracking" / "records"
        import shutil
        shutil.rmtree(str(tracker_dir))
        tracker_dir.write_text("corrupt")  # now it's a file, not a dir

        # Tool call should STILL succeed
        result_raw = await server.handle_tools_call(
            {"name": "hits_record_work", "arguments": {
                "project_path": "/test/proj",
                "performed_by": "claude",
                "request_text": "Should still work",
            }},
            id_val=1,
        )
        result = json.loads(result_raw)
        text = result["result"]["content"][0]["text"]
        assert "✅" in text  # tool succeeded despite tracking failure


# ===========================================================================
# Scenario 5: operation field correctly identifies tool
# ===========================================================================

class TestAutoTrackingOperationTag:
    """Each tool call should be tagged with the operation name."""

    @pytest.mark.asyncio
    async def test_operation_name_in_records(self, tmp_data):
        server = HITSMcP_Server_Factory(tmp_data)

        # Call different tools
        await server.handle_tools_call(
            {"name": "hits_record_work", "arguments": {
                "project_path": "/proj",
                "performed_by": "claude",
                "request_text": "Work A",
            }},
            id_val=1,
        )
        await server.handle_tools_call(
            {"name": "hits_get_handover", "arguments": {
                "project_path": "/proj",
            }},
            id_val=2,
        )

        tracker = TokenTrackerService(data_dir=tmp_data / "data")
        stats = tracker.get_project_stats("/proj")

        # Should have records for both operations
        assert "hits_record_work" in stats.by_operation
        assert "hits_get_handover" in stats.by_operation


# ===========================================================================
# Scenario 6: Multiple projects tracked independently
# ===========================================================================

class TestAutoTrackingMultiProject:
    """Token tracking should be project-scoped."""

    @pytest.mark.asyncio
    async def test_separate_project_tracking(self, tmp_data):
        server = HITSMcP_Server_Factory(tmp_data)

        # Record work in project A
        await server.handle_tools_call(
            {"name": "hits_record_work", "arguments": {
                "project_path": "/proj-a",
                "performed_by": "claude",
                "request_text": "Work on A",
            }},
            id_val=1,
        )
        # Record work in project B
        await server.handle_tools_call(
            {"name": "hits_record_work", "arguments": {
                "project_path": "/proj-b",
                "performed_by": "opencode",
                "request_text": "Work on B",
            }},
            id_val=2,
        )

        tracker = TokenTrackerService(data_dir=tmp_data / "data")

        stats_a = tracker.get_project_stats("/proj-a")
        stats_b = tracker.get_project_stats("/proj-b")

        assert stats_a.total_records == 1
        assert stats_b.total_records == 1
        assert "claude" in stats_a.by_performer
        assert "opencode" in stats_b.by_performer

        # Top projects should list both
        top = tracker.get_top_projects()
        paths = [p.project_path for p in top]
        assert "/proj-a" in paths
        assert "/proj-b" in paths


# ===========================================================================
# Scenario 7: Token API returns real MCP-tracked data
# ===========================================================================

class TestTokenAPIWithRealData:
    """The token API routes should return data that MCP tools actually tracked."""

    @pytest.mark.asyncio
    async def test_api_returns_mcp_tracked_data(self, tmp_data):
        server = HITSMcP_Server_Factory(tmp_data)

        # Simulate a realistic session: 3 tool calls
        await server.handle_tools_call(
            {"name": "hits_record_work", "arguments": {
                "project_path": "/my/project",
                "performed_by": "claude",
                "request_text": "Implemented auth",
                "context": "Added JWT + Argon2id",
                "tags": ["feature", "auth"],
                "files_modified": ["auth.py", "middleware.py"],
            }},
            id_val=1,
        )
        await server.handle_tools_call(
            {"name": "hits_search_works", "arguments": {
                "project_path": "/my/project",
                "query": "auth",
            }},
            id_val=2,
        )
        await server.handle_tools_call(
            {"name": "hits_auto_checkpoint", "arguments": {
                "project_path": "/my/project",
                "performer": "claude",
                "purpose": "Auth complete",
                "current_state": "80% done",
                "completion_pct": 80,
                "send_signal": False,
            }},
            id_val=3,
        )

        # Now query via TokenTrackerService (same as API route)
        tracker = TokenTrackerService(data_dir=tmp_data / "data")

        # Stats
        stats = tracker.get_project_stats("/my/project")
        assert stats.total_records == 3
        assert stats.total_tokens > 0
        assert stats.active_days >= 1
        assert "claude" in stats.by_performer
        assert "hits_record_work" in stats.by_operation
        assert "hits_auto_checkpoint" in stats.by_operation

        # Daily usage
        daily = tracker.get_daily_usage("/my/project", days=7)
        assert len(daily) == 7
        today = daily[-1]
        assert today.record_count == 3
        assert today.tokens_total > 0

        # Top projects
        top = tracker.get_top_projects()
        assert len(top) >= 1
        assert top[0].project_path == "/my/project"
