"""DAG-based lossless context preservation.

Inspired by lossless-code/LCM: every piece of context is preserved as a node
in a directed acyclic graph. Summaries cascade upward through levels,
but the raw leaf nodes are NEVER deleted.

Architecture:
    ContextNode (leaf or summary)
    ├── NodeType.RAW      — original work log / checkpoint data
    ├── NodeType.SUMMARY  — compressed version of child nodes
    └── NodeType.MERGE    — merged summary of parallel branches

    ContextDAG
    ├── nodes: dict[str, ContextNode]
    ├── edges: parent → children relationships
    ├── root_id: the top-level summary node
    └── levels: L0 (raw) → L1 → L2 → L3 (project summary)

    ContextDAGService
    ├── add_raw_node()     — add work log/checkpoint as leaf
    ├── build_summary()    — compress children into summary node
    ├── merge_branches()   — merge parallel session outputs
    ├── get_context()      — query at specific compression level
    ├── search()           — find relevant context by keyword
    └── get_lineage()      — trace a node's ancestry for audit

Why DAG instead of linear chain?
    - Parallel sessions can MERGE (Claude + OpenCode working simultaneously)
    - Lossless: raw data never deleted, only compressed upward
    - Queryable at any granularity level
    - Audit trail: full lineage from summary → original data
"""

from enum import Enum
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class NodeType(str, Enum):
    RAW = "raw"          # Original work log / checkpoint
    SUMMARY = "summary"  # Compressed version of children
    MERGE = "merge"      # Merged output of parallel branches


class CompressionLevel(str, Enum):
    L0_RAW = "L0"        # Full original data
    L1_SUMMARY = "L1"    # Per-session summary
    L2_COMPACT = "L2"    # Per-day / multi-session compact
    L3_PROJECT = "L3"    # Project-level ultra-summary


# ---------------------------------------------------------------------------
# ContextNode
# ---------------------------------------------------------------------------

class ContextNode(BaseModel):
    """A single node in the context DAG.

    RAW nodes contain original data (work log or checkpoint JSON).
    SUMMARY/MERGE nodes contain compressed text + references to children.
    """
    model_config = ConfigDict(use_enum_values=True, extra="ignore")

    id: str = Field(..., description="Unique node ID")
    node_type: NodeType = Field(default=NodeType.RAW)
    level: CompressionLevel = Field(default=CompressionLevel.L0_RAW)

    # Content
    title: str = Field(default="", description="Short title / label")
    content: str = Field(default="", description="Full content (raw or summary text)")
    content_hash: Optional[str] = Field(default=None, description="SHA256 of raw content for integrity")

    # DAG relationships
    child_ids: list[str] = Field(default_factory=list, description="Child node IDs (this summarizes them)")
    parent_ids: list[str] = Field(default_factory=list, description="Parent node IDs (summaries containing this)")

    # Context
    project_path: str = Field(default="")
    performer: str = Field(default="")
    session_id: Optional[str] = Field(default=None, description="Originating session ID")
    tags: list[str] = Field(default_factory=list)

    # Metadata
    token_count: int = Field(default=0, description="Estimated token count")
    created_at: datetime = Field(default_factory=datetime.now)

    # Source reference
    source_type: Optional[str] = Field(default=None, description="work_log | checkpoint | manual")
    source_id: Optional[str] = Field(default=None, description="ID of source work_log or checkpoint")

    def is_leaf(self) -> bool:
        return len(self.child_ids) == 0

    def is_root(self) -> bool:
        return len(self.parent_ids) == 0


# ---------------------------------------------------------------------------
# ContextDAG
# ---------------------------------------------------------------------------

class ContextDAG(BaseModel):
    """Directed Acyclic Graph for lossless context preservation.

    All raw data is stored as leaf nodes (L0). Summaries cascade upward
    through levels L1 → L2 → L3. The graph supports:
    - Linear chains (single session)
    - Merges (parallel sessions → combined summary)
    - Branching (session splits into sub-tasks)
    """
    model_config = ConfigDict(use_enum_values=True)

    id: str = Field(..., description="DAG ID (usually project-scoped)")
    project_path: str = Field(default="")
    project_name: str = Field(default="")

    nodes: dict[str, ContextNode] = Field(default_factory=dict, description="All nodes by ID")
    root_id: Optional[str] = Field(default=None, description="Top-level summary node ID")

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Statistics
    total_raw_nodes: int = Field(default=0)
    total_summary_nodes: int = Field(default=0)
    total_tokens_preserved: int = Field(default=0)

    # --- Node operations ---

    def add_node(self, node: ContextNode) -> None:
        """Add a node to the DAG."""
        self.nodes[node.id] = node

        if node.node_type == NodeType.RAW:
            self.total_raw_nodes += 1
        else:
            self.total_summary_nodes += 1
        self.total_tokens_preserved += node.token_count

        # Link parent ↔ child relationships
        for child_id in node.child_ids:
            child = self.nodes.get(child_id)
            if child and node.id not in child.parent_ids:
                child.parent_ids.append(node.id)

        self.updated_at = datetime.now()

    def get_node(self, node_id: str) -> Optional[ContextNode]:
        return self.nodes.get(node_id)

    def remove_node(self, node_id: str) -> Optional[ContextNode]:
        """Remove a summary node (never remove RAW nodes)."""
        node = self.nodes.get(node_id)
        if node is None:
            return None
        if node.node_type == NodeType.RAW:
            raise ValueError("Cannot remove RAW nodes — lossless preservation")

        # Unlink from parents and children
        for parent_id in node.parent_ids:
            parent = self.nodes.get(parent_id)
            if parent and node_id in parent.child_ids:
                parent.child_ids.remove(node_id)

        for child_id in node.child_ids:
            child = self.nodes.get(child_id)
            if child and node_id in child.parent_ids:
                child.parent_ids.remove(node_id)

        if self.root_id == node_id:
            self.root_id = None

        del self.nodes[node_id]
        self.total_summary_nodes -= 1
        self.updated_at = datetime.now()
        return node

    # --- Query operations ---

    def get_leaf_nodes(self) -> list[ContextNode]:
        """Get all RAW leaf nodes (original data)."""
        return [n for n in self.nodes.values() if n.is_leaf() and n.node_type == NodeType.RAW]

    def get_nodes_at_level(self, level: CompressionLevel) -> list[ContextNode]:
        """Get all nodes at a specific compression level."""
        return [n for n in self.nodes.values() if n.level == level]

    def get_children(self, node_id: str) -> list[ContextNode]:
        """Get immediate children of a node."""
        node = self.nodes.get(node_id)
        if not node:
            return []
        return [self.nodes[cid] for cid in node.child_ids if cid in self.nodes]

    def get_descendants(self, node_id: str) -> list[ContextNode]:
        """Get ALL descendants of a node (recursive)."""
        result = []
        visited = set()

        def _walk(nid: str):
            if nid in visited:
                return
            visited.add(nid)
            node = self.nodes.get(nid)
            if not node:
                return
            for cid in node.child_ids:
                child = self.nodes.get(cid)
                if child:
                    result.append(child)
                    _walk(cid)

        _walk(node_id)
        return result

    def get_ancestors(self, node_id: str) -> list[ContextNode]:
        """Get ALL ancestors of a node (trace upward to root)."""
        result = []
        visited = set()

        def _walk(nid: str):
            if nid in visited:
                return
            visited.add(nid)
            node = self.nodes.get(nid)
            if not node:
                return
            for pid in node.parent_ids:
                parent = self.nodes.get(pid)
                if parent:
                    result.append(parent)
                    _walk(pid)

        _walk(node_id)
        return result

    def get_lineage(self, node_id: str) -> list[ContextNode]:
        """Get full lineage: all descendants + node + all ancestors."""
        node = self.nodes.get(node_id)
        if not node:
            return []

        descendants = self.get_descendants(node_id)
        ancestors = self.get_ancestors(node_id)
        return descendants + [node] + ancestors

    def get_context_at_level(
        self,
        level: CompressionLevel,
        limit: int = 10,
    ) -> list[ContextNode]:
        """Get context at a specific compression level, most recent first."""
        nodes = self.get_nodes_at_level(level)
        nodes.sort(key=lambda n: n.created_at, reverse=True)
        return nodes[:limit]

    def get_context_within_budget(
        self,
        token_budget: int = 2000,
        prefer_level: CompressionLevel = CompressionLevel.L1_SUMMARY,
    ) -> list[ContextNode]:
        """Get the most relevant context within a token budget.

        Strategy:
        1. Start with preferred level summaries
        2. If under budget, add more detailed (lower level) nodes
        3. Stop when budget is exhausted
        """
        result = []
        used_tokens = 0

        # Level order: prefer_level first, then increasingly detailed
        level_order = [prefer_level]
        for lvl in [CompressionLevel.L1_SUMMARY, CompressionLevel.L0_RAW,
                     CompressionLevel.L2_COMPACT, CompressionLevel.L3_PROJECT]:
            if lvl not in level_order:
                level_order.append(lvl)

        for level in level_order:
            nodes = self.get_context_at_level(level, limit=20)
            for node in nodes:
                if used_tokens + node.token_count <= token_budget:
                    result.append(node)
                    used_tokens += node.token_count
                else:
                    return result
            if used_tokens >= token_budget:
                break

        return result

    def search(self, query: str, limit: int = 10) -> list[ContextNode]:
        """Search nodes by keyword in title, content, or tags."""
        query_lower = query.lower()
        if not query_lower:
            return []
        results = []

        for node in self.nodes.values():
            score = 0
            if query_lower in node.title.lower():
                score += 3
            if query_lower in node.content.lower():
                score += 2
            if any(query_lower in tag.lower() for tag in node.tags):
                score += 1

            if score > 0:
                results.append((score, node))

        results.sort(key=lambda x: x[0], reverse=True)
        return [node for _, node in results[:limit]]

    def get_statistics(self) -> dict:
        """Return DAG statistics."""
        return {
            "total_nodes": len(self.nodes),
            "raw_nodes": self.total_raw_nodes,
            "summary_nodes": self.total_summary_nodes,
            "total_tokens_preserved": self.total_tokens_preserved,
            "levels": {
                level.value: len(self.get_nodes_at_level(level))
                for level in CompressionLevel
            },
            "has_root": self.root_id is not None,
            "project_path": self.project_path,
        }

    # --- Merge operations ---

    def merge_nodes(
        self,
        node_ids: list[str],
        summary_node: "ContextNode",
    ) -> ContextNode:
        """Create a merge node that combines multiple branches."""
        for nid in node_ids:
            node = self.nodes.get(nid)
            if node and summary_node.id not in node.parent_ids:
                node.parent_ids.append(summary_node.id)
            if nid not in summary_node.child_ids:
                summary_node.child_ids.append(nid)

        self.add_node(summary_node)
        return summary_node
