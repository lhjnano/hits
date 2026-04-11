"""HITS internal action collector - records actions taken within HITS UI."""

from datetime import datetime
from typing import Optional, Callable, Any
import getpass

from .base import BaseCollector, CollectorEvent
from ..models.work_log import WorkLogSource, WorkLogResultType


class HitsActionCollector(BaseCollector):
    def __init__(
        self,
        callback: Optional[Callable[[CollectorEvent], None]] = None,
        username: Optional[str] = None,
    ):
        super().__init__(callback)
        self._username = username or getpass.getuser()
    
    @property
    def source(self) -> WorkLogSource:
        return WorkLogSource.LINK_CLICK
    
    async def collect(self) -> list[CollectorEvent]:
        return []
    
    async def start(self) -> None:
        self._running = True
    
    async def stop(self) -> None:
        self._running = False
    
    def record_link_click(
        self,
        url: str,
        title: Optional[str] = None,
        category: Optional[str] = None,
        node_id: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> CollectorEvent:
        event = CollectorEvent(
            source=WorkLogSource.LINK_CLICK,
            performed_by=self._username,
            performed_at=datetime.now(),
            request_text=title,
            result_type=WorkLogResultType.URL,
            result_ref=url[:100],
            result_data={"url": url, "title": title},
            tags=tags or [],
            category=category,
            node_id=node_id,
        )
        self._emit(event)
        return event
    
    def record_shell_exec(
        self,
        command: str,
        category: Optional[str] = None,
        node_id: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> CollectorEvent:
        event = CollectorEvent(
            source=WorkLogSource.SHELL_EXEC,
            performed_by=self._username,
            performed_at=datetime.now(),
            request_text=command[:200],
            result_type=WorkLogResultType.COMMAND,
            result_ref=command[:50],
            result_data={"command": command},
            tags=tags or [],
            category=category,
            node_id=node_id,
        )
        self._emit(event)
        return event
    
    def record_manual_entry(
        self,
        text: str,
        context: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> CollectorEvent:
        event = CollectorEvent(
            source=WorkLogSource.MANUAL,
            performed_by=self._username,
            performed_at=datetime.now(),
            request_text=text,
            context=context,
            tags=tags or [],
        )
        self._emit(event)
        return event
    
    def record_navigation(
        self,
        from_view: str,
        to_view: str,
        query: Optional[str] = None,
    ) -> CollectorEvent:
        event = CollectorEvent(
            source=WorkLogSource.MANUAL,
            performed_by=self._username,
            performed_at=datetime.now(),
            request_text=f"Navigate: {from_view} → {to_view}",
            result_data={"from": from_view, "to": to_view, "query": query},
            tags=["navigation"],
        )
        self._emit(event)
        return event
