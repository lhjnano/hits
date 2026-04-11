"""Shell history collector."""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable
import getpass

from .base import BaseCollector, CollectorEvent
from ..models.work_log import WorkLogSource, WorkLogResultType


class ShellCollector(BaseCollector):
    HISTORY_FILES = {
        "bash": ".bash_history",
        "zsh": ".zhistfile",
        "fish": ".local/share/fish/fish_history",
    }
    
    DEFAULT_IGNORE_PATTERNS = [
        "ls", "cd", "pwd", "echo", "cat", "clear",
        "exit", "history", "which", "type",
    ]
    
    def __init__(
        self,
        callback: Optional[Callable[[CollectorEvent], None]] = None,
        poll_interval: int = 60,
        shell: str = "bash",
        ignore_patterns: Optional[list[str]] = None,
    ):
        super().__init__(callback)
        self.poll_interval = poll_interval
        self.shell = shell
        self.ignore_patterns = ignore_patterns or self.DEFAULT_IGNORE_PATTERNS
        self._last_position: int = 0
        self._task: Optional[asyncio.Task] = None
        self._username = getpass.getuser()
    
    @property
    def source(self) -> WorkLogSource:
        return WorkLogSource.SHELL
    
    def _get_history_path(self) -> Optional[Path]:
        home = Path.home()
        
        if self.shell == "bash":
            histfile = os.environ.get("HISTFILE", str(home / ".bash_history"))
        elif self.shell == "zsh":
            histfile = os.environ.get("HISTFILE", str(home / ".zsh_history"))
        elif self.shell == "fish":
            histfile = str(home / ".local/share/fish/fish_history")
        else:
            return None
        
        path = Path(histfile)
        return path if path.exists() else None
    
    def _should_ignore(self, command: str) -> bool:
        cmd_first = command.strip().split()[0] if command.strip() else ""
        return cmd_first in self.ignore_patterns
    
    def _parse_command(self, line: str) -> Optional[dict]:
        line = line.strip()
        if not line or line.startswith("#"):
            return None
        
        if self.shell == "zsh" and line.startswith(":"):
            parts = line.split(";", 1)
            if len(parts) == 2:
                return {"command": parts[1].strip(), "raw": line}
        
        return {"command": line, "raw": line}
    
    async def collect(self) -> list[CollectorEvent]:
        events = []
        
        history_path = self._get_history_path()
        if not history_path:
            return events
        
        try:
            with open(history_path, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(self._last_position)
                new_lines = f.readlines()
                self._last_position = f.tell()
        except Exception:
            return events
        
        now = datetime.now()
        
        for line in new_lines:
            parsed = self._parse_command(line)
            if not parsed:
                continue
            
            command = parsed["command"]
            if self._should_ignore(command):
                continue
            
            event = CollectorEvent(
                source=self.source,
                performed_by=self._username,
                performed_at=now,
                request_text=command[:200],
                result_type=WorkLogResultType.COMMAND,
                result_ref=command[:50],
                result_data={"raw": parsed["raw"]},
                tags=self._extract_tags(command),
            )
            events.append(event)
            self._emit(event)
        
        return events
    
    def _extract_tags(self, command: str) -> list[str]:
        tags = []
        
        tool_tags = {
            "git": "git",
            "docker": "docker",
            "kubectl": "kubernetes",
            "npm": "npm",
            "yarn": "npm",
            "pip": "python",
            "python": "python",
            "pytest": "test",
            "mvn": "java",
            "gradle": "java",
            "cargo": "rust",
            "go": "go",
            "make": "build",
            "ssh": "ssh",
            "scp": "ssh",
            "rsync": "sync",
            "curl": "http",
            "wget": "http",
        }
        
        cmd_lower = command.lower()
        for tool, tag in tool_tags.items():
            if cmd_lower.startswith(tool + " ") or cmd_lower.startswith(tool + "\t"):
                tags.append(tag)
                break
        
        return tags
    
    async def start(self) -> None:
        self._running = True
        history_path = self._get_history_path()
        if history_path:
            try:
                with open(history_path, "r") as f:
                    f.seek(0, 2)
                    self._last_position = f.tell()
            except Exception:
                pass
        
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
