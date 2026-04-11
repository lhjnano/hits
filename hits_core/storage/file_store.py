"""File-based storage backend for fallback and local development."""

import json
import os
from pathlib import Path
from typing import Optional
from datetime import datetime

from .base import BaseStorage
from ..models.tree import KnowledgeTree
from ..models.workflow import Workflow
from ..models.work_log import WorkLog


class FileStorage(BaseStorage):
    TREE_DIR = "trees"
    WORKFLOW_DIR = "workflows"
    WORK_LOG_DIR = "work_logs"
    INDEX_FILE = "index.json"

    # Centralized data home - all AI tools write to the same location
    DEFAULT_DATA_HOME = Path.home() / ".hits" / "data"

    def __init__(self, base_path: Optional[str] = None):
        if base_path:
            self.base_path = Path(base_path)
        else:
            # Priority: env var > ~/.hits/data/ (centralized)
            env_path = os.environ.get("HITS_DATA_PATH")
            if env_path:
                self.base_path = Path(env_path)
            else:
                self.base_path = self.DEFAULT_DATA_HOME

        self.tree_dir = self.base_path / self.TREE_DIR
        self.workflow_dir = self.base_path / self.WORKFLOW_DIR
        self.work_log_dir = self.base_path / self.WORK_LOG_DIR
        
        self.tree_dir.mkdir(parents=True, exist_ok=True)
        self.workflow_dir.mkdir(parents=True, exist_ok=True)
        self.work_log_dir.mkdir(parents=True, exist_ok=True)
    
    def _tree_path(self, tree_id: str) -> Path:
        return self.tree_dir / f"{tree_id}.json"
    
    def _workflow_path(self, workflow_id: str) -> Path:
        return self.workflow_dir / f"{workflow_id}.json"
    
    def _work_log_path(self, log_id: str) -> Path:
        return self.work_log_dir / f"{log_id}.json"
    
    def _index_path(self, dir_path: Path) -> Path:
        return dir_path / self.INDEX_FILE
    
    def _read_index(self, dir_path: Path) -> list[str]:
        index_file = self._index_path(dir_path)
        if index_file.exists():
            with open(index_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return []
    
    def _write_index(self, dir_path: Path, items: list[str]) -> None:
        index_file = self._index_path(dir_path)
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(items, f)
    
    async def save_tree(self, tree: KnowledgeTree) -> bool:
        try:
            path = self._tree_path(tree.id)
            with open(path, "w", encoding="utf-8") as f:
                f.write(tree.model_dump_json(indent=2))
            
            index = self._read_index(self.tree_dir)
            if tree.id not in index:
                index.append(tree.id)
                self._write_index(self.tree_dir, index)
            
            return True
        except Exception:
            return False
    
    async def load_tree(self, tree_id: str) -> Optional[KnowledgeTree]:
        try:
            path = self._tree_path(tree_id)
            if not path.exists():
                return None
            with open(path, "r", encoding="utf-8") as f:
                return KnowledgeTree.model_validate_json(f.read())
        except Exception:
            return None
    
    async def delete_tree(self, tree_id: str) -> bool:
        try:
            path = self._tree_path(tree_id)
            if path.exists():
                path.unlink()
            
            index = self._read_index(self.tree_dir)
            if tree_id in index:
                index.remove(tree_id)
                self._write_index(self.tree_dir, index)
            
            return True
        except Exception:
            return False
    
    async def list_trees(self) -> list[str]:
        return self._read_index(self.tree_dir)
    
    async def save_workflow(self, workflow: Workflow) -> bool:
        try:
            path = self._workflow_path(workflow.id)
            with open(path, "w", encoding="utf-8") as f:
                f.write(workflow.model_dump_json(indent=2))
            
            index = self._read_index(self.workflow_dir)
            if workflow.id not in index:
                index.append(workflow.id)
                self._write_index(self.workflow_dir, index)
            
            return True
        except Exception:
            return False
    
    async def load_workflow(self, workflow_id: str) -> Optional[Workflow]:
        try:
            path = self._workflow_path(workflow_id)
            if not path.exists():
                return None
            with open(path, "r", encoding="utf-8") as f:
                return Workflow.model_validate_json(f.read())
        except Exception:
            return None
    
    async def delete_workflow(self, workflow_id: str) -> bool:
        try:
            path = self._workflow_path(workflow_id)
            if path.exists():
                path.unlink()
            
            index = self._read_index(self.workflow_dir)
            if workflow_id in index:
                index.remove(workflow_id)
                self._write_index(self.workflow_dir, index)
            
            return True
        except Exception:
            return False
    
    async def list_workflows(self) -> list[str]:
        return self._read_index(self.workflow_dir)
    
    async def save_work_log(self, log: WorkLog) -> bool:
        try:
            path = self._work_log_path(log.id)
            with open(path, "w", encoding="utf-8") as f:
                f.write(log.model_dump_json(indent=2))
            
            index = self._read_index(self.work_log_dir)
            if log.id not in index:
                index.append(log.id)
                self._write_index(self.work_log_dir, index)
            
            return True
        except Exception:
            return False
    
    async def load_work_log(self, log_id: str) -> Optional[WorkLog]:
        try:
            path = self._work_log_path(log_id)
            if not path.exists():
                return None
            with open(path, "r", encoding="utf-8") as f:
                return WorkLog.model_validate_json(f.read())
        except Exception:
            return None
    
    async def delete_work_log(self, log_id: str) -> bool:
        try:
            path = self._work_log_path(log_id)
            if path.exists():
                path.unlink()
            
            index = self._read_index(self.work_log_dir)
            if log_id in index:
                index.remove(log_id)
                self._write_index(self.work_log_dir, index)
            
            return True
        except Exception:
            return False
    
    async def list_work_logs(
        self,
        performed_by: Optional[str] = None,
        source: Optional[str] = None,
        since: Optional[datetime] = None,
        project_path: Optional[str] = None,
        limit: int = 100,
    ) -> list[WorkLog]:
        logs = []
        index = self._read_index(self.work_log_dir)
        
        for log_id in index:
            log = await self.load_work_log(log_id)
            if log is None:
                continue
            
            if performed_by and log.performed_by != performed_by:
                continue
            if source and log.source != source:
                continue
            if since and log.performed_at < since:
                continue
            if project_path and log.project_path != project_path:
                continue
            
            logs.append(log)
        
        logs.sort(key=lambda x: x.performed_at, reverse=True)
        return logs[:limit]
    
    async def search_work_logs(
        self,
        query: str,
        project_path: Optional[str] = None,
        limit: int = 50,
    ) -> list[WorkLog]:
        query_lower = query.lower()
        logs = []
        index = self._read_index(self.work_log_dir)
        
        for log_id in index:
            log = await self.load_work_log(log_id)
            if log is None:
                continue
            
            # Project filter first (narrow down before text search)
            if project_path and log.project_path != project_path:
                continue
            
            searchable = " ".join([
                log.request_text or "",
                log.context or "",
                " ".join(log.tags),
                log.result_ref or "",
                log.performed_by,
                log.category or "",
                log.project_path or "",
            ]).lower()
            
            if query_lower in searchable:
                logs.append(log)
        
        logs.sort(key=lambda x: x.performed_at, reverse=True)
        return logs[:limit]
    
    async def list_project_paths(self) -> list[str]:
        """Return all unique project paths that have work logs."""
        paths: set[str] = set()
        index = self._read_index(self.work_log_dir)
        
        for log_id in index:
            log = await self.load_work_log(log_id)
            if log and log.project_path:
                paths.add(log.project_path)
        
        return sorted(paths)
    
    async def get_project_summary(self, project_path: str) -> dict:
        """Get aggregated statistics for a specific project."""
        index = self._read_index(self.work_log_dir)
        
        total_logs = 0
        ai_sessions = 0
        files_modified: set[str] = set()
        commands_run: list[str] = []
        tags: dict[str, int] = {}
        performers: dict[str, int] = {}
        last_activity: Optional[datetime] = None
        
        for log_id in index:
            log = await self.load_work_log(log_id)
            if log is None or log.project_path != project_path:
                continue
            
            total_logs += 1
            
            if log.source == "ai_session":
                ai_sessions += 1
            
            if log.result_data:
                for f in log.result_data.get("files_modified", []):
                    files_modified.add(f)
                commands_run.extend(log.result_data.get("commands_run", []))
            
            for tag in log.tags:
                tags[tag] = tags.get(tag, 0) + 1
            
            performers[log.performed_by] = performers.get(log.performed_by, 0) + 1
            
            if last_activity is None or log.performed_at > last_activity:
                last_activity = log.performed_at
        
        return {
            "project_path": project_path,
            "total_logs": total_logs,
            "ai_sessions": ai_sessions,
            "files_modified": sorted(files_modified),
            "commands_run": commands_run,
            "tags": dict(sorted(tags.items(), key=lambda x: x[1], reverse=True)),
            "performers": performers,
            "last_activity": last_activity.isoformat() if last_activity else None,
        }
