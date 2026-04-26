"""Tests for Work Log functionality - recording and retrieving work history."""

import pytest
from datetime import datetime, timedelta

from hits_core.models.work_log import WorkLog, WorkLogSource
from hits_core.storage.file_store import FileStorage


class TestWorkLogModel:
    def test_work_log_creation(self):
        """Test creating a work log."""
        log = WorkLog(
            source=WorkLogSource.AI_SESSION,
            id="log1",
            project_path="/test/project",
            performed_by="claude",
            performed_at=datetime(2026, 4, 26, 10, 0),
            request_text="Implement auth feature",
            context="Using JWT tokens with HttpOnly cookies",
            files_modified=["auth.py", "main.py"],
            commands_run=["npm test", "pytest tests/"],
            tags=["auth", "security"],
        )

        assert log.id == "log1"
        assert log.project_path == "/test/project"
        assert log.performed_by == "claude"
        assert log.request_text == "Implement auth feature"
        assert len(log.files_modified) == 2
        assert len(log.commands_run) == 2
        assert "auth" in log.tags
        assert "security" in log.tags

    def test_work_log_defaults(self):
        """Test work log with default values."""
        log = WorkLog(
            source=WorkLogSource.AI_SESSION,
            id="log2",
            project_path="/test/project",
            performed_by="manual",
            request_text="Manual entry",
        )

        assert log.performed_at is not None  # Should default to now
        assert log.files_modified == []
        assert log.commands_run == []
        assert log.tags == []

    def test_work_log_to_dict(self):
        """Test converting work log to dict."""
        log = WorkLog(
            source=WorkLogSource.AI_SESSION,
            id="log1",
            project_path="/test/project",
            performed_by="claude",
            performed_at=datetime(2026, 4, 26, 10, 0),
            request_text="Test task",
            context="Test context",
        )

        data = log.model_dump()

        assert data["id"] == "log1"
        assert data["project_path"] == "/test/project"
        assert data["performed_by"] == "claude"
        assert data["request_text"] == "Test task"
        assert data["context"] == "Test context"
        assert "performed_at" in data


class TestWorkLogStorage:
    @pytest.fixture
    def storage(self, tmp_path):
        """Create a file storage with temporary directory."""
        return FileStorage(base_path=str(tmp_path / "hits_data"))

    @pytest.mark.asyncio
    async def test_save_and_load_work_log(self, storage):
        """Test saving and retrieving a work log."""
        log = WorkLog(
            source=WorkLogSource.AI_SESSION,
            id="log1",
            project_path="/test/project",
            performed_by="claude",
            performed_at=datetime(2026, 4, 26, 10, 0),
            request_text="Test task",
            context="Test context",
        )

        # Save
        await storage.save_work_log(log)

        # Get
        retrieved = await storage.load_work_log("log1")

        assert retrieved is not None
        assert retrieved.id == "log1"
        assert retrieved.request_text == "Test task"
        assert retrieved.context == "Test context"

    @pytest.mark.asyncio
    async def test_list_work_logs_by_project(self, storage):
        """Test listing work logs for a specific project."""
        # Create logs for different projects
        log1 = WorkLog(
            source=WorkLogSource.AI_SESSION,
            id="log1",
            project_path="/project/a",
            performed_by="claude",
            performed_at=datetime(2026, 4, 26, 10, 0),
            request_text="Task A1",
        )
        log2 = WorkLog(
            source=WorkLogSource.AI_SESSION,
            id="log2",
            project_path="/project/a",
            performed_by="opencode",
            performed_at=datetime(2026, 4, 26, 11, 0),
            request_text="Task A2",
        )
        log3 = WorkLog(
            source=WorkLogSource.AI_SESSION,
            id="log3",
            project_path="/project/b",
            performed_by="claude",
            performed_at=datetime(2026, 4, 26, 12, 0),
            request_text="Task B",
        )

        await storage.save_work_log(log1)
        await storage.save_work_log(log2)
        await storage.save_work_log(log3)

        # List for project A
        project_a_logs = await storage.list_work_logs(project_path="/project/a")
        assert len(project_a_logs) == 2
        assert all(log.project_path == "/project/a" for log in project_a_logs)

        # List for project B
        project_b_logs = await storage.list_work_logs(project_path="/project/b")
        assert len(project_b_logs) == 1
        assert project_b_logs[0].id == "log3"

    @pytest.mark.asyncio
    async def test_list_work_logs_with_limit(self, storage):
        """Test limiting number of work logs returned."""
        # Create 10 logs
        for i in range(10):
            log = WorkLog(
            source=WorkLogSource.AI_SESSION,
                id=f"log{i}",
                project_path="/test/project",
                performed_by="claude",
                performed_at=datetime(2026, 4, 26, i, 0),
                request_text=f"Task {i}",
            )
            await storage.save_work_log(log)

        # List with limit
        logs = await storage.list_work_logs(
            project_path="/test/project",
            limit=5,
        )
        assert len(logs) == 5

    @pytest.mark.asyncio
    async def test_list_work_logs_ordering(self, storage):
        """Test that work logs are returned in descending order."""
        base_time = datetime(2026, 4, 26, 10, 0)

        # Create logs with different times
        log1 = WorkLog(
            source=WorkLogSource.AI_SESSION,
            id="log1",
            project_path="/test/project",
            performed_by="claude",
            performed_at=base_time,
            request_text="Task 1",
        )
        log2 = WorkLog(
            source=WorkLogSource.AI_SESSION,
            id="log2",
            project_path="/test/project",
            performed_by="claude",
            performed_at=base_time + timedelta(hours=1),
            request_text="Task 2",
        )
        log3 = WorkLog(
            source=WorkLogSource.AI_SESSION,
            id="log3",
            project_path="/test/project",
            performed_by="claude",
            performed_at=base_time + timedelta(hours=2),
            request_text="Task 3",
        )

        await storage.save_work_log(log1)
        await storage.save_work_log(log2)
        await storage.save_work_log(log3)

        # List should return in descending order (newest first)
        logs = await storage.list_work_logs(project_path="/test/project")

        assert logs[0].id == "log3"  # Newest
        assert logs[1].id == "log2"
        assert logs[2].id == "log1"  # Oldest

    @pytest.mark.asyncio
    async def test_search_work_logs(self, storage):
        """Test searching work logs by keyword."""
        # Create logs with different content
        log1 = WorkLog(
            source=WorkLogSource.AI_SESSION,
            id="log1",
            project_path="/test/project",
            performed_by="claude",
            performed_at=datetime.now(),
            request_text="Implement authentication",
            context="Using JWT tokens",
        )
        log2 = WorkLog(
            source=WorkLogSource.AI_SESSION,
            id="log2",
            project_path="/test/project",
            performed_by="claude",
            performed_at=datetime.now(),
            request_text="Fix database bug",
            context="SQL query error",
        )
        log3 = WorkLog(
            source=WorkLogSource.AI_SESSION,
            id="log3",
            project_path="/test/project",
            performed_by="claude",
            performed_at=datetime.now(),
            request_text="Add user authentication",
            context="OAuth integration",
        )

        await storage.save_work_log(log1)
        await storage.save_work_log(log2)
        await storage.save_work_log(log3)

        # Search for "authentication"
        results = await storage.search_work_logs(
            query="authentication",
            project_path="/test/project",
        )

        assert len(results) == 2
        assert all("authentication" in log.request_text.lower() or "authentication" in log.context.lower()
                   for log in results)

    @pytest.mark.asyncio
    async def test_update_work_log(self, storage):
        """Test updating an existing work log."""
        # Create a log
        log = WorkLog(
            source=WorkLogSource.AI_SESSION,
            id="log1",
            project_path="/test/project",
            performed_by="claude",
            request_text="Original task",
        )
        await storage.save_work_log(log)

        # Update it
        updated_log = WorkLog(
            source=WorkLogSource.AI_SESSION,
            id="log1",
            project_path="/test/project",
            performed_by="claude",
            request_text="Updated task",
            context="Added context",
            tags=["updated"],
        )
        await storage.save_work_log(updated_log)

        # Verify update
        retrieved = await storage.load_work_log("log1")
        assert retrieved.request_text == "Updated task"
        assert retrieved.context == "Added context"
        assert "updated" in retrieved.tags

    @pytest.mark.asyncio
    async def test_delete_work_log(self, storage):
        """Test deleting a work log."""
        # Create a log
        log = WorkLog(
            source=WorkLogSource.AI_SESSION,
            id="log1",
            project_path="/test/project",
            performed_by="claude",
            request_text="Task to delete",
        )
        await storage.save_work_log(log)

        # Verify it exists
        retrieved = await storage.load_work_log("log1")
        assert retrieved is not None

        # Delete it
        await storage.delete_work_log("log1")

        # Verify it's gone
        retrieved = await storage.load_work_log("log1")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_get_recent_work_logs(self, storage):
        """Test getting recent work logs across all projects."""
        now = datetime.now()

        # Create logs for different projects at different times
        log1 = WorkLog(
            source=WorkLogSource.AI_SESSION,
            id="log1",
            project_path="/project/a",
            performed_by="claude",
            performed_at=now - timedelta(hours=2),
            request_text="Old task",
        )
        log2 = WorkLog(
            source=WorkLogSource.AI_SESSION,
            id="log2",
            project_path="/project/b",
            performed_by="opencode",
            performed_at=now - timedelta(hours=1),
            request_text="Recent task",
        )
        log3 = WorkLog(
            source=WorkLogSource.AI_SESSION,
            id="log3",
            project_path="/project/a",
            performed_by="claude",
            performed_at=now,
            request_text="Latest task",
        )

        await storage.save_work_log(log1)
        await storage.save_work_log(log2)
        await storage.save_work_log(log3)

        # Get recent logs (use list_work_logs without project filter)
        recent = await storage.list_work_logs(limit=2)

        assert len(recent) == 2
        assert recent[0].id == "log3"  # Most recent
        assert recent[1].id == "log2"

    @pytest.mark.asyncio
    async def test_list_work_logs_by_performer(self, storage):
        """Test filtering recent work logs by performer."""
        now = datetime.now()

        # Create logs by different performers
        log1 = WorkLog(
            source=WorkLogSource.AI_SESSION,
            id="log1",
            project_path="/test/project",
            performed_by="claude",
            performed_at=now,
            request_text="Claude task",
        )
        log2 = WorkLog(
            source=WorkLogSource.AI_SESSION,
            id="log2",
            project_path="/test/project",
            performed_by="opencode",
            performed_at=now,
            request_text="OpenCode task",
        )
        log3 = WorkLog(
            source=WorkLogSource.AI_SESSION,
            id="log3",
            project_path="/test/project",
            performed_by="claude",
            performed_at=now,
            request_text="Another Claude task",
        )

        await storage.save_work_log(log1)
        await storage.save_work_log(log2)
        await storage.save_work_log(log3)

        # Get recent logs by claude (use list_work_logs with performed_by filter)
        claude_logs = await storage.list_work_logs(
            limit=10,
            performed_by="claude",
        )

        assert len(claude_logs) == 2
        assert all(log.performed_by == "claude" for log in claude_logs)
