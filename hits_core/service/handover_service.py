"""Handover service - generates project-scoped session handover summaries.

Enables seamless context transfer between AI tools (Claude, OpenCode, etc.)
when token limits are reached or the user switches tools.

Key design:
- Project-scoped: only includes work logs for the specified project
- Data-driven: no LLM dependency for reliability
- Structured: machine-readable format that any AI can consume
- File-based fallback: works even when HITS server is down
"""

import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..storage.base import BaseStorage
from ..storage.file_store import FileStorage
from ..models.work_log import WorkLog


class HandoverSummary:
    """Structured handover summary for a specific project."""

    def __init__(
        self,
        project_path: str,
        project_name: str = "",
        recent_logs: Optional[list[WorkLog]] = None,
        files_modified: Optional[list[str]] = None,
        commands_run: Optional[list[str]] = None,
        key_decisions: Optional[list[str]] = None,
        pending_items: Optional[list[str]] = None,
        session_history: Optional[list[dict]] = None,
        git_branch: Optional[str] = None,
        git_status: Optional[str] = None,
        generated_at: Optional[datetime] = None,
    ):
        self.project_path = project_path
        self.project_name = project_name or Path(project_path).name
        self.recent_logs = recent_logs or []
        self.files_modified = files_modified or []
        self.commands_run = commands_run or []
        self.key_decisions = key_decisions or []
        self.pending_items = pending_items or []
        self.session_history = session_history or []
        self.git_branch = git_branch
        self.git_status = git_status
        self.generated_at = generated_at or datetime.now()

    def to_dict(self) -> dict:
        return {
            "project_path": self.project_path,
            "project_name": self.project_name,
            "generated_at": self.generated_at.isoformat(),
            "git_branch": self.git_branch,
            "git_status": self.git_status,
            "session_history": self.session_history,
            "key_decisions": self.key_decisions,
            "pending_items": self.pending_items,
            "files_modified": self.files_modified,
            "commands_run": self.commands_run,
            "recent_logs": [
                {
                    "id": log.id,
                    "performed_by": log.performed_by,
                    "performed_at": log.performed_at.isoformat(),
                    "request_text": log.request_text,
                    "context": log.context,
                    "source": log.source,
                    "tags": log.tags,
                    "result_type": log.result_type,
                }
                for log in self.recent_logs
            ],
        }

    def to_text(self) -> str:
        """Generate human-readable handover text.

        Format designed for:
        1. Direct copy-paste into AI chat as context
        2. Human reading as a project status report
        3. Pasting into documents/wiki
        """
        lines = []
        
        # Header
        lines.append(f"📋 인수인계: {self.project_name}")
        lines.append(f"{'=' * 40}")
        lines.append(f"경로: {self.project_path}")
        lines.append(f"시간: {self.generated_at.strftime('%Y-%m-%d %H:%M')}")
        
        if self.git_branch:
            lines.append(f"브랜치: {self.git_branch} ({self.git_status or '?'})")
        
        lines.append("")
        
        # Session history
        if self.session_history:
            lines.append("👥 작업 이력")
            lines.append("-" * 30)
            for session in self.session_history:
                tool = session.get("performed_by", "unknown")
                count = session.get("log_count", 0)
                last = session.get("last_activity", "")[:16]
                lines.append(f"  {tool}: {count}건 (마지막: {last})")
            lines.append("")

        # Key decisions
        if self.key_decisions:
            lines.append("★ 주요 결정 사항")
            lines.append("-" * 30)
            for decision in self.key_decisions:
                lines.append(f"  • {decision}")
            lines.append("")

        # Pending items
        if self.pending_items:
            lines.append("⚠ 미완료 / 후속 작업")
            lines.append("-" * 30)
            for item in self.pending_items:
                lines.append(f"  • {item}")
            lines.append("")

        # Files modified
        if self.files_modified:
            unique = sorted(set(self.files_modified))
            lines.append(f"📄 수정된 파일 ({len(unique)}개)")
            lines.append("-" * 30)
            for f in unique[:15]:
                lines.append(f"  {f}")
            if len(unique) > 15:
                lines.append(f"  ... 외 {len(unique) - 15}개")
            lines.append("")

        # Recent work
        if self.recent_logs:
            lines.append("📝 최근 작업")
            lines.append("-" * 30)
            for log in self.recent_logs[:10]:
                ts = log.performed_at.strftime("%m/%d %H:%M")
                tool = log.performed_by
                summary = log.request_text or log.context or "(내용 없음)"
                tags = f" [{', '.join(log.tags)}]" if log.tags else ""
                lines.append(f"  [{ts}] {tool}: {summary[:80]}{tags}")
        
        # Empty state
        if not self.session_history and not self.recent_logs:
            lines.append("기록된 작업이 없습니다.")
        
        return "\n".join(lines)


class HandoverService:
    """Generate project-scoped handover summaries.

    Usage:
        service = HandoverService()

        # New AI session starts → get handover
        summary = await service.get_handover("/home/user/source/my-project")

        # Print structured text for AI context
        print(summary.to_text())

        # Or get machine-readable dict
        data = summary.to_dict()
    """

    def __init__(self, storage: Optional[BaseStorage] = None):
        self.storage = storage or FileStorage()  # defaults to ~/.hits/data/

    def _detect_git_info(self, project_path: str) -> tuple[Optional[str], Optional[str]]:
        """Detect git branch and status for a project."""
        branch = None
        status = None

        git_dir = Path(project_path) / ".git"
        if not git_dir.exists():
            return branch, status

        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, timeout=5,
                cwd=project_path,
            )
            if result.returncode == 0:
                branch = result.stdout.strip()
        except Exception:
            pass

        try:
            result = subprocess.run(
                ["git", "status", "--short"],
                capture_output=True, text=True, timeout=5,
                cwd=project_path,
            )
            if result.returncode == 0:
                status_lines = result.stdout.strip().split("\n")
                status_lines = [l for l in status_lines if l.strip()]
                if status_lines:
                    status = f"{len(status_lines)} changes"
                else:
                    status = "clean"
        except Exception:
            pass

        return branch, status

    def _extract_key_decisions(self, logs: list[WorkLog]) -> list[str]:
        """Extract key decisions from work log contexts.

        Heuristic: logs with 'decide', 'determine', 'change', 'important'
        in their context or tags are treated as key decisions.
        """
        decision_keywords = [
            "결정", "변경", "선택", "채택", "important", "decide",
            "아키텍처", "설계", "design", "architecture", "breaking",
            "중요", "필수",
        ]
        decisions = []

        for log in logs:
            text = f"{log.context or ''} {log.request_text or ''} {' '.join(log.tags)}".lower()
            for kw in decision_keywords:
                if kw.lower() in text:
                    decision = log.request_text or log.context or ""
                    if decision and decision not in decisions:
                        decisions.append(decision[:120])
                    break

        return decisions[:5]

    def _extract_pending_items(self, logs: list[WorkLog]) -> list[str]:
        """Extract pending/incomplete items from recent logs.

        Heuristic: logs with 'todo', 'pending', 'fixme', '미완', '필요'
        or tags like 'wip', 'todo', 'incomplete'.
        """
        pending_keywords = ["todo", "pending", "fixme", "미완", "필요", "남음", "wip"]
        pending_tags = {"todo", "wip", "incomplete", "pending"}
        items = []

        for log in logs:
            tags_lower = {t.lower() for t in log.tags}
            if pending_tags & tags_lower:
                text = log.request_text or log.context or ""
                if text and text not in items:
                    items.append(text[:120])
                continue

            text = f"{log.context or ''} {log.request_text or ''}".lower()
            for kw in pending_keywords:
                if kw in text:
                    original = log.request_text or log.context or ""
                    if original and original not in items:
                        items.append(original[:120])
                    break

        return items[:5]

    def _build_session_history(self, logs: list[WorkLog]) -> list[dict]:
        """Build per-AI-tool session breakdown."""
        sessions: dict[str, dict] = {}

        for log in logs:
            performer = log.performed_by
            if performer not in sessions:
                sessions[performer] = {
                    "performed_by": performer,
                    "log_count": 0,
                    "first_activity": log.performed_at.isoformat(),
                    "last_activity": log.performed_at.isoformat(),
                }
            sessions[performer]["log_count"] += 1
            sessions[performer]["last_activity"] = log.performed_at.isoformat()

        return sorted(sessions.values(), key=lambda x: x["last_activity"], reverse=True)

    async def get_handover(
        self,
        project_path: str,
        recent_count: int = 20,
    ) -> HandoverSummary:
        """Generate a handover summary for a specific project.

        Args:
            project_path: Absolute path identifying the project.
            recent_count: Number of recent work logs to include.

        Returns:
            HandoverSummary with all context needed for the next AI session.
        """
        # Normalize path
        project_path = str(Path(project_path).resolve())

        # Get project-scoped work logs
        logs = await self.storage.list_work_logs(
            project_path=project_path,
            limit=recent_count,
        )

        # If no logs found with exact path, try matching by project name
        if not logs:
            all_logs = await self.storage.list_work_logs(limit=50)
            project_name = Path(project_path).name
            logs = [
                log for log in all_logs
                if log.project_path and (
                    Path(log.project_path).name == project_name
                    or project_name in (log.project_path or "")
                )
            ][:recent_count]

        # Collect aggregated data
        files_modified: list[str] = []
        commands_run: list[str] = []

        for log in logs:
            if log.result_data:
                files_modified.extend(log.result_data.get("files_modified", []))
                commands_run.extend(log.result_data.get("commands_run", []))

        # Detect git info
        git_branch, git_status = self._detect_git_info(project_path)

        return HandoverSummary(
            project_path=project_path,
            recent_logs=logs,
            files_modified=files_modified,
            commands_run=commands_run,
            key_decisions=self._extract_key_decisions(logs),
            pending_items=self._extract_pending_items(logs),
            session_history=self._build_session_history(logs),
            git_branch=git_branch,
            git_status=git_status,
        )

    async def list_projects(self) -> list[dict]:
        """List all projects that have work logs.

        Returns:
            List of dicts with project_path and summary stats.
        """
        paths = await self.storage.list_project_paths()
        projects = []

        for path in paths:
            summary = await self.storage.get_project_summary(path)
            projects.append(summary)

        return sorted(projects, key=lambda x: x.get("last_activity") or "", reverse=True)

    async def get_all_handovers(self) -> HandoverSummary:
        """Get a combined handover summary across all projects.

        Returns a merged view showing all recent activity regardless of project.
        """
        all_logs = await self.storage.list_work_logs(limit=50)

        files_modified: list[str] = []
        commands_run: list[str] = []

        for log in all_logs:
            if log.result_data:
                files_modified.extend(log.result_data.get("files_modified", []))
                commands_run.extend(log.result_data.get("commands_run", []))

        return HandoverSummary(
            project_path="all",
            project_name="전체 프로젝트",
            recent_logs=all_logs,
            files_modified=files_modified,
            commands_run=commands_run,
            key_decisions=self._extract_key_decisions(all_logs),
            pending_items=self._extract_pending_items(all_logs),
            session_history=self._build_session_history(all_logs),
        )
