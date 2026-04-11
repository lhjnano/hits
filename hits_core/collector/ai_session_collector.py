"""AI session collector - monitors AI interaction sessions."""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable
import getpass

from .base import BaseCollector, CollectorEvent
from ..models.work_log import WorkLogSource, WorkLogResultType


class AISessionCollector(BaseCollector):
    SESSION_DIR = Path.home() / ".hits" / "sessions"
    
    def __init__(
        self,
        callback: Optional[Callable[[CollectorEvent], None]] = None,
        poll_interval: int = 30,
    ):
        super().__init__(callback)
        self.poll_interval = poll_interval
        self._task: Optional[asyncio.Task] = None
        self._username = getpass.getuser()
        self._processed_files: set[str] = set()
    
    @property
    def source(self) -> WorkLogSource:
        return WorkLogSource.AI_SESSION
    
    @classmethod
    def get_session_file(cls, session_id: str) -> Path:
        cls.SESSION_DIR.mkdir(parents=True, exist_ok=True)
        return cls.SESSION_DIR / f"{session_id}.json"
    
    @classmethod
    def write_session_summary(
        cls,
        session_id: str,
        ai_type: str,
        prompt: str,
        summary: str,
        files_modified: Optional[list[str]] = None,
        commands_run: Optional[list[str]] = None,
    ) -> None:
        data = {
            "session_id": session_id,
            "ai_type": ai_type,
            "prompt": prompt,
            "summary": summary,
            "files_modified": files_modified or [],
            "commands_run": commands_run or [],
            "timestamp": datetime.now().isoformat(),
        }
        
        path = cls.get_session_file(session_id)
        cls.SESSION_DIR.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    async def collect(self) -> list[CollectorEvent]:
        events = []
        
        if not self.SESSION_DIR.exists():
            return events
        
        for session_file in self.SESSION_DIR.glob("*.json"):
            if str(session_file) in self._processed_files:
                continue
            
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                event = CollectorEvent(
                    source=self.source,
                    performed_by=f"{data.get('ai_type', 'unknown')} ({self._username})",
                    performed_at=datetime.fromisoformat(data["timestamp"]),
                    request_text=data.get("prompt", "")[:200],
                    context=data.get("summary", "")[:500],
                    result_type=WorkLogResultType.AI_RESPONSE,
                    result_ref=data.get("session_id", "")[:20],
                    result_data={
                        "files_modified": data.get("files_modified", []),
                        "commands_run": data.get("commands_run", []),
                    },
                    tags=[data.get("ai_type", "ai")],
                )
                events.append(event)
                self._emit(event)
                self._processed_files.add(str(session_file))
            except Exception:
                pass
        
        return events
    
    async def start(self) -> None:
        self._running = True
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
