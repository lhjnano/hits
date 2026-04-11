"""Git commit collector."""

import asyncio
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

from .base import BaseCollector, CollectorEvent
from ..models.work_log import WorkLogSource, WorkLogResultType


class GitCollector(BaseCollector):
    def __init__(
        self,
        project_path: str,
        callback: Optional[Callable[[CollectorEvent], None]] = None,
        poll_interval: int = 300,
    ):
        super().__init__(callback)
        self.project_path = Path(project_path)
        self.poll_interval = poll_interval
        self._last_commit_hash: Optional[str] = None
        self._task: Optional[asyncio.Task] = None
    
    @property
    def source(self) -> WorkLogSource:
        return WorkLogSource.GIT
    
    def _run_git(self, *args: str) -> Optional[str]:
        try:
            result = subprocess.run(
                ["git"] + list(args),
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None
    
    def _get_current_user(self) -> str:
        name = self._run_git("config", "user.name") or "unknown"
        email = self._run_git("config", "user.email") or ""
        if email:
            return f"{name} <{email}>"
        return name
    
    def _get_last_commit_hash(self) -> Optional[str]:
        return self._run_git("rev-parse", "HEAD")
    
    def _parse_commits(self, since_hash: Optional[str] = None) -> list[dict]:
        format_str = "%H|%an|%ae|%at|%s"
        cmd = ["log", f"--format={format_str}"]
        
        if since_hash:
            cmd.append(f"{since_hash}..HEAD")
        else:
            cmd.extend(["-n", "50"])
        
        output = self._run_git(*cmd)
        if not output:
            return []
        
        commits = []
        for line in output.split("\n"):
            if not line.strip():
                continue
            parts = line.split("|", 4)
            if len(parts) == 5:
                commits.append({
                    "hash": parts[0],
                    "author": parts[1],
                    "email": parts[2],
                    "timestamp": int(parts[3]),
                    "message": parts[4],
                })
        return commits
    
    def _get_changed_files(self, commit_hash: str) -> list[str]:
        output = self._run_git("diff-tree", "--no-commit-id", "--name-only", "-r", commit_hash)
        if output:
            return output.split("\n")
        return []
    
    async def collect(self) -> list[CollectorEvent]:
        events = []
        
        current_hash = self._get_last_commit_hash()
        if not current_hash:
            return events
        
        commits = self._parse_commits(self._last_commit_hash)
        
        for commit in commits:
            files = self._get_changed_files(commit["hash"])
            author = f"{commit['author']} <{commit['email']}>"
            
            event = CollectorEvent(
                source=self.source,
                performed_by=author,
                performed_at=datetime.fromtimestamp(commit["timestamp"]),
                request_text=commit["message"],
                result_type=WorkLogResultType.COMMIT,
                result_ref=commit["hash"][:8],
                result_data={
                    "full_hash": commit["hash"],
                    "files": files[:20],
                    "file_count": len(files),
                },
                tags=self._extract_tags(commit["message"], files),
                project_path=str(self.project_path),
            )
            events.append(event)
            self._emit(event)
        
        if commits:
            self._last_commit_hash = current_hash
        
        return events
    
    def _extract_tags(self, message: str, files: list[str]) -> list[str]:
        tags = []
        
        keywords = {
            "fix": "bug",
            "bug": "bug",
            "feat": "feature",
            "feature": "feature",
            "add": "feature",
            "refactor": "refactor",
            "test": "test",
            "doc": "docs",
            "docs": "docs",
            "style": "style",
            "chore": "chore",
            "perf": "performance",
            "ci": "ci",
        }
        
        msg_lower = message.lower()
        for keyword, tag in keywords.items():
            if keyword in msg_lower:
                tags.append(tag)
        
        for file in files[:5]:
            parts = file.split("/")
            if len(parts) > 1:
                tags.append(parts[0])
        
        return list(set(tags))[:5]
    
    async def start(self) -> None:
        self._running = True
        self._last_commit_hash = self._get_last_commit_hash()
        self._task = asyncio.create_task(self._poll_loop())
    
    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
    
    async def _poll_loop(self) -> None:
        while self._running:
            try:
                await self.collect()
            except Exception:
                pass
            await asyncio.sleep(self.poll_interval)
