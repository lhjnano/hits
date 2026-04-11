"""Base collector interface and common utilities."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Callable, Any
import uuid

from ..models.work_log import WorkLog, WorkLogSource


@dataclass
class CollectorEvent:
    source: WorkLogSource
    performed_by: str
    performed_at: datetime
    request_text: Optional[str] = None
    result_type: str = "none"
    result_ref: Optional[str] = None
    result_data: Optional[dict] = None
    context: Optional[str] = None
    tags: Optional[list[str]] = None
    project_path: Optional[str] = None
    node_id: Optional[str] = None
    category: Optional[str] = None
    
    def to_work_log(self) -> WorkLog:
        return WorkLog(
            id=str(uuid.uuid4()),
            source=self.source,
            request_text=self.request_text,
            request_by=None,
            performed_by=self.performed_by,
            performed_at=self.performed_at,
            result_type=self.result_type,
            result_ref=self.result_ref,
            result_data=self.result_data,
            context=self.context,
            tags=self.tags or [],
            project_path=self.project_path,
            node_id=self.node_id,
            category=self.category,
        )


class BaseCollector(ABC):
    def __init__(self, callback: Optional[Callable[[CollectorEvent], None]] = None):
        self.callback = callback
        self._running = False
    
    @property
    @abstractmethod
    def source(self) -> WorkLogSource:
        pass
    
    @abstractmethod
    async def collect(self) -> list[CollectorEvent]:
        pass
    
    @abstractmethod
    async def start(self) -> None:
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        pass
    
    def _emit(self, event: CollectorEvent) -> None:
        if self.callback:
            self.callback(event)
    
    def is_running(self) -> bool:
        return self._running
