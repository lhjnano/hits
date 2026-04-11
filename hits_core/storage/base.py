"""Storage abstraction layer."""

from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime
from ..models.tree import KnowledgeTree
from ..models.workflow import Workflow
from ..models.work_log import WorkLog


class BaseStorage(ABC):
    @abstractmethod
    async def save_tree(self, tree: KnowledgeTree) -> bool:
        pass
    
    @abstractmethod
    async def load_tree(self, tree_id: str) -> Optional[KnowledgeTree]:
        pass
    
    @abstractmethod
    async def delete_tree(self, tree_id: str) -> bool:
        pass
    
    @abstractmethod
    async def list_trees(self) -> list[str]:
        pass
    
    @abstractmethod
    async def save_workflow(self, workflow: Workflow) -> bool:
        pass
    
    @abstractmethod
    async def load_workflow(self, workflow_id: str) -> Optional[Workflow]:
        pass
    
    @abstractmethod
    async def delete_workflow(self, workflow_id: str) -> bool:
        pass
    
    @abstractmethod
    async def list_workflows(self) -> list[str]:
        pass
    
    @abstractmethod
    async def save_work_log(self, log: WorkLog) -> bool:
        pass
    
    @abstractmethod
    async def load_work_log(self, log_id: str) -> Optional[WorkLog]:
        pass
    
    @abstractmethod
    async def delete_work_log(self, log_id: str) -> bool:
        pass
    
    @abstractmethod
    async def list_work_logs(
        self,
        performed_by: Optional[str] = None,
        source: Optional[str] = None,
        since: Optional[datetime] = None,
        project_path: Optional[str] = None,
        limit: int = 100,
    ) -> list[WorkLog]:
        pass
    
    @abstractmethod
    async def search_work_logs(
        self,
        query: str,
        project_path: Optional[str] = None,
        limit: int = 50,
    ) -> list[WorkLog]:
        pass
    
    @abstractmethod
    async def list_project_paths(self) -> list[str]:
        """Return all unique project paths that have work logs."""
        pass
    
    @abstractmethod
    async def get_project_summary(self, project_path: str) -> dict:
        """Get aggregated statistics for a specific project."""
        pass
