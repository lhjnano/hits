"""Tests for Handover service - generates project-scoped session handover summaries."""

import pytest
from datetime import datetime
from pathlib import Path

from hits_core.service.handover_service import HandoverService, HandoverSummary
from hits_core.models.work_log import WorkLog, WorkLogSource, WorkLogResultType


class TestHandoverSummary:
    def test_handover_summary_creation(self):
        """Test creating a handover summary."""
        summary = HandoverSummary(
            project_path="/test/project",
            project_name="test-project",
            key_decisions=["Use JWT for auth"],
            pending_items=["Add rate limiting"],
            files_modified=["auth.py", "main.py"],
            commands_run=["npm test", "pytest"],
        )

        assert summary.project_path == "/test/project"
        assert summary.project_name == "test-project"
        assert len(summary.key_decisions) == 1
        assert len(summary.pending_items) == 1
        assert len(summary.files_modified) == 2
        assert len(summary.commands_run) == 2

    def test_handover_summary_to_dict(self):
        """Test converting summary to dict."""
        summary = HandoverSummary(
            project_path="/test/project",
            project_name="test",
            key_decisions=["Decision 1"],
            pending_items=["Task 1"],
        )

        data = summary.to_dict()

        assert data["project_path"] == "/test/project"
        assert data["project_name"] == "test"
        assert len(data["key_decisions"]) == 1
        assert len(data["pending_items"]) == 1
        assert "generated_at" in data
        assert "recent_logs" in data

    def test_handover_summary_to_text(self):
        """Test converting summary to human-readable text."""
        summary = HandoverSummary(
            project_path="/test/project",
            project_name="my-project",
            key_decisions=["Use PostgreSQL"],
            pending_items=["Add caching"],
            files_modified=["db.py"],
            git_branch="main",
            git_status="clean",
        )

        text = summary.to_text()

        assert "my-project" in text
        assert "/test/project" in text
        assert "Use PostgreSQL" in text
        assert "Add caching" in text
        assert "db.py" in text
        assert "main" in text

    def test_handover_summary_with_recent_logs(self):
        """Test summary with recent work logs."""
        log1 = WorkLog(
            id="log1",
            source=WorkLogSource.AI_SESSION,
            performed_by="claude",
            performed_at=datetime(2026, 1, 1, 10, 0),
            request_text="Implement auth",
            context="Using JWT",
            tags=["auth"],
        )
        log2 = WorkLog(
            id="log2",
            source=WorkLogSource.AI_SESSION,
            performed_by="opencode",
            performed_at=datetime(2026, 1, 1, 11, 0),
            request_text="Fix bug",
            context="Fixed null pointer",
            tags=["bugfix"],
        )

        summary = HandoverSummary(
            project_path="/test/project",
            recent_logs=[log1, log2],
        )

        text = summary.to_text()

        assert "Implement auth" in text
        assert "Fix bug" in text


class TestHandoverService:
    @pytest.fixture
    def handover_service(self, tmp_path):
        """Create a handover service with temporary storage."""
        from hits_core.storage.file_store import FileStorage
        storage = FileStorage(base_path=str(tmp_path / "hits_data"))
        return HandoverService(storage=storage)

    @pytest.mark.asyncio
    async def test_generate_handover_empty_project(self, handover_service):
        """Test generating handover for a project with no work logs."""
        summary = await handover_service.get_handover(project_path="/empty/project")

        assert summary.project_path == "/empty/project"
        assert summary.project_name == "project"
        assert len(summary.recent_logs) == 0
        assert len(summary.files_modified) == 0

    @pytest.mark.asyncio
    async def test_generate_handover_with_work_logs(self, handover_service):
        """Test generating handover with existing work logs."""
        # Create some work logs
        log1 = WorkLog(
            id="log1",
            source=WorkLogSource.AI_SESSION,
            project_path="/test/project",
            performed_by="claude",
            performed_at=datetime(2026, 4, 26, 10, 0),
            request_text="Feature A implementation",
            context="Using FastAPI",
            files_modified=["app.py"],
            commands_run=["pytest"],
            tags=["feature"],
            result_data={
                "files_modified": ["app.py"],
                "commands_run": ["pytest"],
            },
        )
        log2 = WorkLog(
            id="log2",
            source=WorkLogSource.AI_SESSION,
            project_path="/test/project",
            performed_by="opencode",
            performed_at=datetime(2026, 4, 26, 11, 0),
            request_text="Bug fix",
            context="Fixed auth issue",
            files_modified=["auth.py"],
            commands_run=["npm test"],
            tags=["bugfix"],
            result_data={
                "files_modified": ["auth.py"],
                "commands_run": ["npm test"],
            },
        )

        await handover_service.storage.save_work_log(log1)
        await handover_service.storage.save_work_log(log2)

        # Generate handover
        summary = await handover_service.get_handover(project_path="/test/project")

        assert len(summary.recent_logs) == 2
        assert "app.py" in summary.files_modified
        assert "auth.py" in summary.files_modified
        assert "pytest" in summary.commands_run
        assert "npm test" in summary.commands_run

    @pytest.mark.asyncio
    async def test_generate_handover_limit_logs(self, handover_service):
        """Test that handover limits number of recent logs."""
        # Create 10 work logs
        for i in range(10):
            log = WorkLog(
                id=f"log{i}",
                source=WorkLogSource.AI_SESSION,
                project_path="/test/project",
                performed_by="claude",
                performed_at=datetime(2026, 4, 26, i, 0),
                request_text=f"Task {i}",
            )
            await handover_service.storage.save_work_log(log)

        # Generate handover with default limit
        summary = await handover_service.get_handover(project_path="/test/project")

        # Should limit to reasonable number (e.g., 5-10)
        assert len(summary.recent_logs) <= 10

    @pytest.mark.asyncio
    async def test_generate_handover_git_info(self, handover_service, tmp_path):
        """Test that handover includes git information."""
        # Create a git repo in temp directory
        test_project = tmp_path / "test_project"
        test_project.mkdir()

        import subprocess
        subprocess.run(["git", "init"], cwd=test_project, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=test_project, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=test_project, capture_output=True)

        # Create a commit so HEAD exists
        (test_project / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "README.md"], cwd=test_project, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=test_project, capture_output=True)

        # Create feature branch
        subprocess.run(["git", "checkout", "-b", "feature-branch"], cwd=test_project, capture_output=True)

        # Generate handover
        summary = await handover_service.get_handover(project_path=str(test_project))

        assert summary.git_branch == "feature-branch"

    @pytest.mark.asyncio
    async def test_generate_handover_multiple_projects(self, handover_service):
        """Test that handover only includes logs for the specified project."""
        # Create logs for different projects
        log_a = WorkLog(
            id="log_a",
            source=WorkLogSource.AI_SESSION,
            project_path="/project/a",
            performed_by="claude",
            performed_at=datetime(2026, 4, 26, 10, 0),
            request_text="Project A task",
        )
        log_b = WorkLog(
            id="log_b",
            source=WorkLogSource.AI_SESSION,
            project_path="/project/b",
            performed_by="claude",
            performed_at=datetime(2026, 4, 26, 10, 0),
            request_text="Project B task",
        )

        await handover_service.storage.save_work_log(log_a)
        await handover_service.storage.save_work_log(log_b)

        # Generate handover for project A
        summary_a = await handover_service.get_handover(project_path="/project/a")
        assert len(summary_a.recent_logs) == 1
        assert summary_a.recent_logs[0].request_text == "Project A task"

        # Generate handover for project B
        summary_b = await handover_service.get_handover(project_path="/project/b")
        assert len(summary_b.recent_logs) == 1
        assert summary_b.recent_logs[0].request_text == "Project B task"

    @pytest.mark.asyncio
    async def test_list_projects(self, handover_service):
        """Test listing all projects with work logs."""
        # Create logs for multiple projects
        await handover_service.storage.save_work_log(WorkLog(
            id="log1",
            source=WorkLogSource.AI_SESSION,
            project_path="/project/a",
            performed_by="claude",
            performed_at=datetime.now(),
            request_text="Task A",
        ))
        await handover_service.storage.save_work_log(WorkLog(
            id="log2",
            source=WorkLogSource.AI_SESSION,
            project_path="/project/b",
            performed_by="claude",
            performed_at=datetime.now(),
            request_text="Task B",
        ))

        projects = await handover_service.list_projects()

        assert len(projects) == 2
        project_paths = [p["project_path"] for p in projects]
        assert "/project/a" in project_paths
        assert "/project/b" in project_paths
