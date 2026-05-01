"""ContextDAG Service — builds and manages lossless context graphs.

Responsibilities:
- Add raw work logs / checkpoints as leaf nodes
- Periodically build summary nodes from accumulated raw nodes
- Support merging parallel session branches
- Query context at any compression level within token budgets
- Persist DAG to disk (~/.hits/data/context_dags/)
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from ..models.context_dag import (
    ContextDAG,
    ContextNode,
    NodeType,
    CompressionLevel,
)
from ..models.work_log import WorkLog
from ..models.checkpoint import Checkpoint
from ..storage.base import BaseStorage
from ..storage.file_store import FileStorage


class ContextDAGService:
    """Manage per-project context DAGs for lossless preservation.

    Storage:
        ~/.hits/data/context_dags/
        ├── {project_hash}.json      ← DAG structure
        └── {project_hash}/
            ├── {node_id}.json       ← individual node data (for large content)
            └── summaries/
                ├── L1_{id}.json
                ├── L2_{id}.json
                └── L3_{id}.json
    """

    DAG_DIR = "context_dags"

    def __init__(self, storage: Optional[BaseStorage] = None):
        self.storage = storage or FileStorage()
        if isinstance(self.storage, FileStorage):
            self._base_path = self.storage.base_path
        else:
            self._base_path = Path.home() / ".hits" / "data"
        self._dag_dir = self._base_path / self.DAG_DIR
        self._dag_dir.mkdir(parents=True, exist_ok=True)

    def _project_key(self, project_path: str) -> str:
        return project_path.replace("/", "_").strip("_")

    # -----------------------------------------------------------------------
    # DAG CRUD
    # -----------------------------------------------------------------------

    async def get_or_create_dag(self, project_path: str) -> ContextDAG:
        """Get existing DAG or create a new one for the project."""
        key = self._project_key(project_path)
        dag = await self._load_dag(key)
        if dag is None:
            dag = ContextDAG(
                id=f"dag_{uuid4().hex[:8]}",
                project_path=project_path,
                project_name=Path(project_path).name,
            )
            await self._save_dag(dag)
        return dag

    async def _load_dag(self, key: str) -> Optional[ContextDAG]:
        path = self._dag_dir / f"{key}.json"
        if not path.exists():
            return None
        try:
            return ContextDAG.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    async def _save_dag(self, dag: ContextDAG) -> None:
        key = self._project_key(dag.project_path)
        path = self._dag_dir / f"{key}.json"
        path.write_text(dag.model_dump_json(indent=2), encoding="utf-8")

    # -----------------------------------------------------------------------
    # Add raw nodes
    # -----------------------------------------------------------------------

    async def add_work_log_node(self, dag: ContextDAG, log: WorkLog) -> ContextNode:
        """Add a work log as a RAW leaf node in the DAG."""
        token_estimate = len(log.request_text) // 3 + len(log.context or "") // 3

        node = ContextNode(
            id=f"raw_{log.id}",
            node_type=NodeType.RAW,
            level=CompressionLevel.L0_RAW,
            title=log.request_text[:100],
            content=log.model_dump_json(),  # Pydantic handles datetime serialization
            project_path=log.project_path or dag.project_path,
            performer=log.performed_by,
            session_id=None,
            tags=log.tags,
            token_count=token_estimate,
            source_type="work_log",
            source_id=log.id,
        )

        dag.add_node(node)
        await self._save_dag(dag)
        return node

    async def add_checkpoint_node(self, dag: ContextDAG, checkpoint: Checkpoint) -> ContextNode:
        """Add a checkpoint as a RAW leaf node."""
        content = checkpoint.to_text()
        token_estimate = len(content) // 3

        node = ContextNode(
            id=f"raw_cp_{checkpoint.id}",
            node_type=NodeType.RAW,
            level=CompressionLevel.L0_RAW,
            title=f"Checkpoint: {checkpoint.purpose[:80]}",
            content=content,
            project_path=checkpoint.project_path,
            performer=checkpoint.performer,
            tags=["checkpoint"],
            token_count=token_estimate,
            source_type="checkpoint",
            source_id=checkpoint.id,
        )

        dag.add_node(node)
        await self._save_dag(dag)
        return node

    # -----------------------------------------------------------------------
    # Build summaries
    # -----------------------------------------------------------------------

    async def build_summary(
        self,
        dag: ContextDAG,
        child_ids: list[str],
        title: str = "",
        content: str = "",
        level: CompressionLevel = CompressionLevel.L1_SUMMARY,
        performer: str = "system",
    ) -> ContextNode:
        """Create a summary node from a set of child nodes.

        The summary node references its children, creating the DAG edge.
        """
        # Calculate total tokens from children
        total_tokens = 0
        for cid in child_ids:
            child = dag.get_node(cid)
            if child:
                total_tokens += child.token_count

        summary = ContextNode(
            id=f"sum_{uuid4().hex[:8]}",
            node_type=NodeType.SUMMARY,
            level=level,
            title=title or f"Summary ({len(child_ids)} items)",
            content=content,
            child_ids=child_ids,
            project_path=dag.project_path,
            performer=performer,
            token_count=content and len(content) // 3 or total_tokens // 4,
            tags=["auto-summary"],
        )

        dag.add_node(summary)

        # Update root if this is the highest level
        if level in (CompressionLevel.L2_COMPACT, CompressionLevel.L3_PROJECT):
            dag.root_id = summary.id

        await self._save_dag(dag)
        return summary

    async def build_auto_summary(
        self,
        dag: ContextDAG,
        level: CompressionLevel = CompressionLevel.L1_SUMMARY,
        max_children: int = 10,
    ) -> Optional[ContextNode]:
        """Automatically build a summary from unparented nodes at the level below.

        L1: summarizes L0 (raw) nodes that have no L1 parent
        L2: summarizes L1 nodes that have no L2 parent
        L3: summarizes L2 nodes
        """
        target_level_map = {
            CompressionLevel.L1_SUMMARY: CompressionLevel.L0_RAW,
            CompressionLevel.L2_COMPACT: CompressionLevel.L1_SUMMARY,
            CompressionLevel.L3_PROJECT: CompressionLevel.L2_COMPACT,
        }
        source_level = target_level_map.get(level)
        if source_level is None:
            return None

        # Find nodes at source level that don't have a parent at target level
        unparented = []
        for node in dag.get_nodes_at_level(source_level):
            has_target_parent = any(
                dag.nodes.get(pid) and dag.nodes.get(pid).level == level
                for pid in node.parent_ids
            )
            if not has_target_parent:
                unparented.append(node)

        if len(unparented) == 0:
            return None

        # Take the most recent ones
        unparented.sort(key=lambda n: n.created_at, reverse=True)
        children = unparented[:max_children]
        child_ids = [c.id for c in children]

        # Build summary content from children
        summary_parts = []
        for child in children:
            text = child.content[:200] if child.content else child.title
            summary_parts.append(f"- {text}")

        content = "\n".join(summary_parts)
        title = f"{level.value} Summary of {len(children)} {source_level.value} nodes"

        return await self.build_summary(
            dag=dag,
            child_ids=child_ids,
            title=title,
            content=content,
            level=level,
        )

    # -----------------------------------------------------------------------
    # Merge parallel branches
    # -----------------------------------------------------------------------

    async def merge_branches(
        self,
        dag: ContextDAG,
        node_ids: list[str],
        title: str = "",
        content: str = "",
        performer: str = "coordinator",
    ) -> ContextNode:
        """Merge parallel session outputs into a single summary node."""
        merge = ContextNode(
            id=f"merge_{uuid4().hex[:8]}",
            node_type=NodeType.MERGE,
            level=CompressionLevel.L1_SUMMARY,
            title=title or f"Merged {len(node_ids)} branches",
            content=content,
            child_ids=node_ids,
            project_path=dag.project_path,
            performer=performer,
            tags=["merge"],
        )

        dag.merge_nodes(node_ids, merge)
        await self._save_dag(dag)
        return merge

    # -----------------------------------------------------------------------
    # Query
    # -----------------------------------------------------------------------

    async def get_context_for_resume(
        self,
        project_path: str,
        token_budget: int = 2000,
    ) -> str:
        """Get the best available context for resuming a project.

        Strategy: try L1 summaries first, fill remaining budget with L0 raw nodes.
        """
        dag = await self.get_or_create_dag(project_path)

        nodes = dag.get_context_within_budget(
            token_budget=token_budget,
            prefer_level=CompressionLevel.L1_SUMMARY,
        )

        if not nodes:
            # No summaries yet, use raw nodes
            nodes = dag.get_context_within_budget(
                token_budget=token_budget,
                prefer_level=CompressionLevel.L0_RAW,
            )

        if not nodes:
            return ""

        lines = [f"## Context DAG: {dag.project_name}"]
        for node in nodes:
            icon = {"L0": "📄", "L1": "📋", "L2": "📊", "L3": "🎯"}.get(node.level, "·")
            lines.append(f"\n{icon} [{node.level}] {node.title}")
            if node.content:
                # Truncate individual node content
                max_chars = (token_budget * 3) // max(len(nodes), 1)
                lines.append(node.content[:max_chars])

        return "\n".join(lines)

    async def search_context(
        self,
        project_path: str,
        query: str,
        limit: int = 10,
    ) -> list[ContextNode]:
        """Search for context across all levels."""
        key = self._project_key(project_path)
        dag = await self._load_dag(key)
        if dag is None:
            return []
        return dag.search(query, limit=limit)

    async def get_lineage(self, project_path: str, node_id: str) -> list[ContextNode]:
        """Get full lineage of a node (for audit/debugging)."""
        key = self._project_key(project_path)
        dag = await self._load_dag(key)
        if dag is None:
            return []
        return dag.get_lineage(node_id)

    async def get_statistics(self, project_path: str) -> dict:
        """Get DAG statistics for a project."""
        key = self._project_key(project_path)
        dag = await self._load_dag(key)
        if dag is None:
            return {"total_nodes": 0, "raw_nodes": 0, "summary_nodes": 0, "total_tokens_preserved": 0}
        return dag.get_statistics()
