"""Checkpoint service - generates structured, actionable session snapshots.

This is the evolution of HandoverService. While HandoverService produces
informational summaries, CheckpointService produces executable checkpoints
that contain everything needed to immediately resume work.

Key improvements over HandoverService:
1. Actionable: generates concrete next_steps with commands
2. Token-aware: compressed output within token budgets
3. Auto-generated: designed to be called automatically on session end
4. Chained: checkpoints link to parent checkpoints for history
"""

import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from ..storage.base import BaseStorage
from ..storage.file_store import FileStorage
from ..models.work_log import WorkLog
from ..models.checkpoint import (
    Checkpoint, NextStep, FileDelta, Block, Decision,
    StepPriority, ChangeType,
)


class CheckpointService:
    """Generate and manage structured checkpoints.

    Usage:
        service = CheckpointService()

        # Auto-checkpoint at session end
        checkpoint = await service.auto_checkpoint(
            project_path="/home/user/project",
            performer="claude",
            purpose="Implement authentication",
            current_state="JWT tokens working, refresh pending",
        )

        # The checkpoint contains actionable next_steps + required context
        print(checkpoint.to_text())

        # Or get compressed version for token budget
        print(checkpoint.to_compact(token_budget=1000))
    """

    CHECKPOINT_DIR = "checkpoints"

    def __init__(self, storage: Optional[BaseStorage] = None):
        self.storage = storage or FileStorage()
        self._checkpoint_dir = self._get_checkpoint_dir()

    def _get_checkpoint_dir(self) -> Path:
        """Get or create checkpoint storage directory."""
        if isinstance(self.storage, FileStorage):
            base = self.storage.base_path
        else:
            base = Path(os.environ.get("HITS_DATA_PATH", Path.home() / ".hits" / "data"))
        cp_dir = base / self.CHECKPOINT_DIR
        cp_dir.mkdir(parents=True, exist_ok=True)
        return cp_dir

    def _detect_git_info(self, project_path: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """Detect git branch, status, and last commit."""
        branch = status = last_commit = None
        git_dir = Path(project_path) / ".git"
        if not git_dir.exists():
            return branch, status, last_commit

        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, timeout=5, cwd=project_path,
            )
            if result.returncode == 0:
                branch = result.stdout.strip()
        except Exception:
            pass

        try:
            result = subprocess.run(
                ["git", "status", "--short"],
                capture_output=True, text=True, timeout=5, cwd=project_path,
            )
            if result.returncode == 0:
                lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
                status = f"{len(lines)} changes" if lines else "clean"
        except Exception:
            pass

        try:
            result = subprocess.run(
                ["git", "log", "-1", "--oneline"],
                capture_output=True, text=True, timeout=5, cwd=project_path,
            )
            if result.returncode == 0:
                last_commit = result.stdout.strip()
        except Exception:
            pass

        return branch, status, last_commit

    def _extract_next_steps(self, logs: list[WorkLog]) -> list[NextStep]:
        """Extract actionable next steps from work logs.

        Heuristics:
        - Logs with 'todo', 'pending', 'fixme', '미완' → next steps
        - Logs tagged 'wip', 'todo', 'incomplete' → next steps
        - Recent context-heavy logs → potential next steps
        """
        pending_keywords = [
            "todo", "pending", "fixme", "미완", "필요", "남음", "wip",
            "다음", "추가", "구현 필요", "해야", "해야 함", "작업 필요",
        ]
        steps = []

        for log in reversed(logs):  # Most recent first
            text = f"{log.request_text or ''} {log.context or ''}".lower()
            tags_lower = {t.lower() for t in log.tags}

            # Check if this log indicates pending work
            is_pending = bool(tags_lower & {"todo", "wip", "incomplete", "pending"})
            if not is_pending:
                for kw in pending_keywords:
                    if kw in text:
                        is_pending = True
                        break

            if is_pending:
                # Extract the action
                action = log.request_text or log.context or "Continue pending work"
                action = action[:200]

                # Try to extract file reference
                file_ref = None
                if log.result_data:
                    files = log.result_data.get("files_modified", [])
                    if files:
                        file_ref = files[0]

                # Try to extract command
                command = None
                if log.result_data:
                    cmds = log.result_data.get("commands_run", [])
                    if cmds:
                        command = cmds[-1]

                # Determine priority from context
                priority = StepPriority.MEDIUM
                if any(kw in text for kw in ["critical", "urgent", "긴급", "필수"]):
                    priority = StepPriority.CRITICAL
                elif any(kw in text for kw in ["important", "중요", "높음"]):
                    priority = StepPriority.HIGH
                elif any(kw in text for kw in ["low", "낮음", "나중"]):
                    priority = StepPriority.LOW

                step = NextStep(
                    action=action,
                    command=command,
                    file=file_ref,
                    priority=priority,
                    context=log.context[:200] if log.context and len(log.context) > len(action) else None,
                )
                # Avoid duplicates
                if not any(s.action == step.action for s in steps):
                    steps.append(step)

        return steps[:8]  # Cap at 8 steps

    def _extract_files_delta(self, logs: list[WorkLog]) -> list[FileDelta]:
        """Extract file change deltas from work logs."""
        seen_paths: set[str] = set()
        deltas = []

        for log in reversed(logs):
            if not log.result_data:
                continue
            for f in log.result_data.get("files_modified", []):
                if f not in seen_paths:
                    seen_paths.add(f)
                    deltas.append(FileDelta(
                        path=f,
                        change_type=ChangeType.MODIFIED,
                        description=None,
                    ))

        return deltas[:20]

    def _extract_decisions(self, logs: list[WorkLog]) -> list[Decision]:
        """Extract architectural/important decisions from work logs."""
        decision_keywords = [
            "결정", "선택", "채택", "decide", "choose", "adopt",
            "아키텍처", "설계", "design", "architecture",
            "breaking", "중요", "필수", "important",
        ]
        decisions = []

        for log in reversed(logs):
            text = f"{log.context or ''} {log.request_text or ''} {' '.join(log.tags)}".lower()
            for kw in decision_keywords:
                if kw in text:
                    decision_text = log.request_text or log.context or ""
                    if decision_text and not any(d.decision == decision_text[:120] for d in decisions):
                        decisions.append(Decision(
                            decision=decision_text[:120],
                            rationale=None,
                        ))
                    break

        return decisions[:5]

    def _extract_required_context(self, logs: list[WorkLog]) -> list[str]:
        """Extract must-know context for the next session.

        Heuristics: facts that appear in context fields with
        '주의', '중요', '필수', 'important', 'note', 'caution' markers.
        """
        context_keywords = [
            "주의", "중요", "필수", "important", "note", "caution",
            "반드시", "절대", "never", "always", "must",
            "caution", "warning", "경고", "참고", "note:",
        ]
        contexts = []

        for log in reversed(logs):
            if not log.context:
                continue
            # Split context into sentences and find important ones
            sentences = log.context.replace(". ", ".\n").replace("。", "。\n").split("\n")
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence or len(sentence) < 10:
                    continue
                lower = sentence.lower()
                for kw in context_keywords:
                    if kw in lower and sentence not in contexts:
                        contexts.append(sentence[:200])
                        break

        return contexts[:6]

    def _extract_blocks(self, logs: list[WorkLog]) -> list[Block]:
        """Extract blockers from work logs."""
        block_keywords = ["blocked", "에러", "오류", "실패", "fail", "error", "안 됨", "불가"]
        blocks = []

        for log in reversed(logs):
            text = f"{log.context or ''} {log.request_text or ''}".lower()
            for kw in block_keywords:
                if kw in text:
                    issue = log.request_text or log.context or "Unknown block"
                    if not any(b.issue == issue[:150] for b in blocks):
                        blocks.append(Block(
                            issue=issue[:150],
                            severity="medium",
                        ))
                    break

        return blocks[:3]

    async def auto_checkpoint(
        self,
        project_path: str,
        performer: str,
        purpose: str = "",
        current_state: str = "",
        completion_pct: int = 0,
        additional_context: Optional[list[str]] = None,
        additional_steps: Optional[list[NextStep]] = None,
        files_modified: Optional[list[str]] = None,
        commands_run: Optional[list[str]] = None,
        parent_checkpoint_id: Optional[str] = None,
    ) -> Checkpoint:
        """Generate and save a checkpoint automatically.

        This is the primary entry point. Call it:
        - When a session ends
        - When a major milestone is reached
        - When switching AI tools

        Args:
            project_path: Absolute path to project.
            performer: AI tool name (claude/opencode/etc).
            purpose: What this session was trying to accomplish.
            current_state: What was actually achieved.
            completion_pct: 0-100 estimated completion.
            additional_context: Extra must-know facts.
            additional_steps: Extra next steps to add.
            files_modified: Files that were modified.
            commands_run: Commands that were run.
            parent_checkpoint_id: Link to previous checkpoint.
        """
        project_path = str(Path(project_path).resolve())

        # Get recent logs for context extraction
        logs = await self.storage.list_work_logs(
            project_path=project_path,
            limit=30,
        )

        # If no purpose provided, try to infer from logs
        if not purpose and logs:
            purpose = logs[0].request_text or "Continue previous session"

        if not current_state and logs:
            # Summarize recent activity
            activities = [f"{l.request_text or 'work'}" for l in logs[:5]]
            current_state = "; ".join(activities)[:300]

        # Extract structured data
        next_steps = self._extract_next_steps(logs)
        files_delta = self._extract_files_delta(logs)
        decisions = self._extract_decisions(logs)
        required_context = self._extract_required_context(logs)
        blocks = self._extract_blocks(logs)

        # Add additional items
        if additional_steps:
            next_steps = additional_steps + next_steps
        if additional_context:
            required_context = additional_context + required_context
        if files_modified:
            existing_paths = {fd.path for fd in files_delta}
            for f in files_modified:
                if f not in existing_paths:
                    files_delta.append(FileDelta(path=f))

        # Detect git info
        git_branch, git_status, git_last_commit = self._detect_git_info(project_path)

        # Create checkpoint
        checkpoint = Checkpoint(
            id=f"cp_{uuid4().hex[:8]}",
            project_path=project_path,
            project_name=Path(project_path).name,
            performer=performer,
            git_branch=git_branch,
            git_status=git_status,
            git_last_commit=git_last_commit,
            purpose=purpose,
            current_state=current_state,
            completion_pct=completion_pct,
            next_steps=next_steps,
            required_context=required_context,
            files_delta=files_delta,
            decisions_made=decisions,
            blocks=blocks,
            commands_run=commands_run or [],
            resume_command=f"npx @purpleraven/hits resume --project {project_path}",
            source_log_ids=[log.id for log in logs[:10]],
            parent_checkpoint_id=parent_checkpoint_id,
        )

        # Save checkpoint
        await self._save_checkpoint(checkpoint)

        return checkpoint

    async def _save_checkpoint(self, checkpoint: Checkpoint) -> bool:
        """Save checkpoint to disk."""
        try:
            # Save as project-specific checkpoint
            project_dir = self._checkpoint_dir / checkpoint.project_path.replace("/", "_")
            project_dir.mkdir(parents=True, exist_ok=True)

            path = project_dir / f"{checkpoint.id}.json"
            with open(path, "w", encoding="utf-8") as f:
                f.write(checkpoint.model_dump_json(indent=2))

            # Also save as 'latest' for quick resume
            latest_path = project_dir / "latest.json"
            with open(latest_path, "w", encoding="utf-8") as f:
                f.write(checkpoint.model_dump_json(indent=2))

            return True
        except Exception:
            return False

    async def get_checkpoint(self, checkpoint_id: str, project_path: Optional[str] = None) -> Optional[Checkpoint]:
        """Load a specific checkpoint."""
        if project_path:
            project_dir = self._checkpoint_dir / project_path.replace("/", "_")
        else:
            # Search all project dirs
            for project_dir in self._checkpoint_dir.iterdir():
                if not project_dir.is_dir():
                    continue
                candidate = project_dir / f"{checkpoint_id}.json"
                if candidate.exists():
                    break
            else:
                return None

        path = project_dir / f"{checkpoint_id}.json"
        if not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                return Checkpoint.model_validate_json(f.read())
        except Exception:
            return None

    async def get_latest_checkpoint(self, project_path: str) -> Optional[Checkpoint]:
        """Get the most recent checkpoint for a project."""
        project_dir = self._checkpoint_dir / project_path.replace("/", "_")
        latest_path = project_dir / "latest.json"

        if not latest_path.exists():
            return None

        try:
            with open(latest_path, "r", encoding="utf-8") as f:
                return Checkpoint.model_validate_json(f.read())
        except Exception:
            return None

    async def list_checkpoints(self, project_path: str, limit: int = 10) -> list[Checkpoint]:
        """List checkpoints for a project, most recent first."""
        project_dir = self._checkpoint_dir / project_path.replace("/", "_")
        if not project_dir.exists():
            return []

        checkpoints = []
        for path in sorted(project_dir.glob("cp_*.json"), reverse=True):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    cp = Checkpoint.model_validate_json(f.read())
                checkpoints.append(cp)
            except Exception:
                continue

        return checkpoints[:limit]

    async def list_all_projects(self) -> list[dict]:
        """List all projects with checkpoint history."""
        projects = []
        if not self._checkpoint_dir.exists():
            return projects

        for project_dir in sorted(self._checkpoint_dir.iterdir()):
            if not project_dir.is_dir():
                continue

            # Read latest checkpoint for project info
            latest_path = project_dir / "latest.json"
            if not latest_path.exists():
                continue

            try:
                with open(latest_path, "r", encoding="utf-8") as f:
                    cp = Checkpoint.model_validate_json(f.read())

                # Count checkpoints
                cp_count = sum(1 for p in project_dir.glob("cp_*.json"))

                projects.append({
                    "project_path": cp.project_path,
                    "project_name": cp.project_name,
                    "checkpoint_count": cp_count,
                    "last_performer": cp.performer,
                    "last_activity": cp.created_at.isoformat(),
                    "completion_pct": cp.completion_pct,
                    "git_branch": cp.git_branch,
                    "purpose": cp.purpose[:100],
                })
            except Exception:
                continue

        return sorted(projects, key=lambda x: x.get("last_activity") or "", reverse=True)
