"""Collector daemon - manages all collectors and stores events."""

import asyncio
from typing import Optional, Callable, Any
from pathlib import Path

from .base import BaseCollector, CollectorEvent
from .git_collector import GitCollector
from .shell_collector import ShellCollector
from .hits_action_collector import HitsActionCollector
from .ai_session_collector import AISessionCollector
from ..storage.base import BaseStorage
from ..storage.file_store import FileStorage


class CollectorDaemon:
    def __init__(
        self,
        storage: Optional[BaseStorage] = None,
        project_paths: Optional[list[str]] = None,
        on_event: Optional[Callable[[CollectorEvent], None]] = None,
    ):
        self.storage = storage or FileStorage()
        self.project_paths = project_paths or []
        self.on_event = on_event
        
        self._collectors: list[BaseCollector] = []
        self._hits_collector: Optional[HitsActionCollector] = None
        self._running = False
    
    def _handle_event(self, event: CollectorEvent) -> None:
        asyncio.create_task(self._save_event(event))
        
        if self.on_event:
            self.on_event(event)
    
    async def _save_event(self, event: CollectorEvent) -> None:
        try:
            work_log = event.to_work_log()
            await self.storage.save_work_log(work_log)
        except Exception:
            pass
    
    def setup(self) -> None:
        for path in self.project_paths:
            if Path(path).exists():
                git_collector = GitCollector(
                    project_path=path,
                    callback=self._handle_event,
                )
                self._collectors.append(git_collector)
        
        shell_collector = ShellCollector(callback=self._handle_event)
        self._collectors.append(shell_collector)
        
        ai_collector = AISessionCollector(callback=self._handle_event)
        self._collectors.append(ai_collector)
        
        self._hits_collector = HitsActionCollector(callback=self._handle_event)
        self._collectors.append(self._hits_collector)
    
    async def start(self) -> None:
        if self._running:
            return
        
        self._running = True
        
        for collector in self._collectors:
            try:
                await collector.start()
            except Exception:
                pass
    
    async def stop(self) -> None:
        self._running = False
        
        for collector in self._collectors:
            try:
                await collector.stop()
            except Exception:
                pass
    
    def get_hits_collector(self) -> Optional[HitsActionCollector]:
        return self._hits_collector
    
    def is_running(self) -> bool:
        return self._running
    
    def get_collector_stats(self) -> dict:
        return {
            "total_collectors": len(self._collectors),
            "running_collectors": sum(1 for c in self._collectors if c.is_running()),
            "collector_types": [c.__class__.__name__ for c in self._collectors],
        }
