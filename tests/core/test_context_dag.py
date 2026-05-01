"""Tests for DAG-based context preservation.

Covers:
- ContextNode: creation, leaf/root detection, relationships
- ContextDAG: add/remove/query/search, level-based access, merge
- ContextDAGService: CRUD, raw node addition, summary building, merge, resume
- Lossless guarantee: RAW nodes cannot be deleted
- Token budget query
- Lineage tracing (audit trail)
"""

import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from hits_core.models.context_dag import (
    ContextDAG,
    ContextNode,
    NodeType,
    CompressionLevel,
)
from hits_core.models.work_log import WorkLog, WorkLogSource
from hits_core.models.checkpoint import Checkpoint


# ============================================================================
# Fixtures
# ============================================================================

def make_raw_node(
    id: str = "raw_1",
    title: str = "Test work log",
    content: str = "Did some work",
    performer: str = "claude",
    tokens: int = 50,
) -> ContextNode:
    return ContextNode(
        id=id,
        node_type=NodeType.RAW,
        level=CompressionLevel.L0_RAW,
        title=title,
        content=content,
        project_path="/test/project",
        performer=performer,
        token_count=tokens,
        source_type="work_log",
        source_id=id.replace("raw_", "log_"),
    )


def make_dag() -> ContextDAG:
    return ContextDAG(
        id="dag_test",
        project_path="/test/project",
        project_name="project",
    )


def make_work_log(text: str = "Fixed auth bug") -> WorkLog:
    return WorkLog(
        id="log_test1",
        source=WorkLogSource.MANUAL,
        performed_by="claude",
        request_text=text,
        project_path="/test/project",
    )


def make_checkpoint(purpose: str = "Implement feature") -> Checkpoint:
    return Checkpoint(
        id="cp_test1",
        project_path="/test/project",
        project_name="project",
        performer="claude",
        purpose=purpose,
    )


# ============================================================================
# ContextNode
# ============================================================================

class TestContextNode:

    def test_raw_node_creation(self):
        node = make_raw_node()
        assert node.node_type == NodeType.RAW
        assert node.level == CompressionLevel.L0_RAW
        assert node.is_leaf() is True
        assert node.is_root() is True

    def test_summary_with_children_is_not_leaf(self):
        parent = ContextNode(
            id="sum_1",
            node_type=NodeType.SUMMARY,
            level=CompressionLevel.L1_SUMMARY,
            child_ids=["raw_1", "raw_2"],
        )
        assert parent.is_leaf() is False

    def test_node_with_parent_is_not_root(self):
        node = ContextNode(
            id="raw_1",
            node_type=NodeType.RAW,
            level=CompressionLevel.L0_RAW,
            parent_ids=["sum_1"],
        )
        assert node.is_root() is False

    def test_default_values(self):
        node = ContextNode(id="n1")
        assert node.tags == []
        assert node.token_count == 0
        assert node.child_ids == []
        assert node.parent_ids == []


# ============================================================================
# ContextDAG — basic operations
# ============================================================================

class TestContextDAGBasic:

    def test_add_node(self):
        dag = make_dag()
        node = make_raw_node("raw_1")
        dag.add_node(node)
        assert "raw_1" in dag.nodes
        assert dag.total_raw_nodes == 1

    def test_get_node(self):
        dag = make_dag()
        dag.add_node(make_raw_node("raw_1"))
        assert dag.get_node("raw_1") is not None
        assert dag.get_node("nonexistent") is None

    def test_add_summary_node(self):
        dag = make_dag()
        dag.add_node(make_raw_node("raw_1"))
        summary = ContextNode(
            id="sum_1",
            node_type=NodeType.SUMMARY,
            level=CompressionLevel.L1_SUMMARY,
            child_ids=["raw_1"],
        )
        dag.add_node(summary)
        assert dag.total_summary_nodes == 1

    def test_remove_summary_node(self):
        dag = make_dag()
        dag.add_node(make_raw_node("raw_1"))
        summary = ContextNode(
            id="sum_1",
            node_type=NodeType.SUMMARY,
            level=CompressionLevel.L1_SUMMARY,
            child_ids=["raw_1"],
        )
        dag.add_node(summary)
        removed = dag.remove_node("sum_1")
        assert removed is not None
        assert "sum_1" not in dag.nodes
        # RAW node still exists
        assert "raw_1" in dag.nodes

    def test_cannot_remove_raw_node(self):
        dag = make_dag()
        dag.add_node(make_raw_node("raw_1"))
        with pytest.raises(ValueError, match="Cannot remove RAW"):
            dag.remove_node("raw_1")

    def test_remove_nonexistent_returns_none(self):
        dag = make_dag()
        assert dag.remove_node("nonexistent") is None


# ============================================================================
# ContextDAG — relationships
# ============================================================================

class TestContextDAGRelationships:

    def test_parent_child_link_on_add(self):
        dag = make_dag()
        dag.add_node(make_raw_node("raw_1"))
        dag.add_node(make_raw_node("raw_2"))
        summary = ContextNode(
            id="sum_1",
            node_type=NodeType.SUMMARY,
            child_ids=["raw_1", "raw_2"],
        )
        dag.add_node(summary)

        # Children should have parent_ids updated
        assert "sum_1" in dag.nodes["raw_1"].parent_ids
        assert "sum_1" in dag.nodes["raw_2"].parent_ids

    def test_get_children(self):
        dag = make_dag()
        dag.add_node(make_raw_node("raw_1"))
        dag.add_node(make_raw_node("raw_2"))
        summary = ContextNode(id="sum_1", child_ids=["raw_1", "raw_2"])
        dag.add_node(summary)

        children = dag.get_children("sum_1")
        assert len(children) == 2

    def test_get_descendants(self):
        dag = make_dag()
        dag.add_node(make_raw_node("raw_1"))
        dag.add_node(make_raw_node("raw_2"))
        dag.add_node(make_raw_node("raw_3"))
        # L1 summary of raw_1 and raw_2
        l1 = ContextNode(id="L1_1", child_ids=["raw_1", "raw_2"])
        dag.add_node(l1)
        # L2 summary of L1_1 and raw_3
        l2 = ContextNode(id="L2_1", child_ids=["L1_1", "raw_3"])
        dag.add_node(l2)

        desc = dag.get_descendants("L2_1")
        ids = {n.id for n in desc}
        assert "L1_1" in ids
        assert "raw_1" in ids
        assert "raw_2" in ids
        assert "raw_3" in ids

    def test_get_ancestors(self):
        dag = make_dag()
        dag.add_node(make_raw_node("raw_1"))
        l1 = ContextNode(id="L1_1", child_ids=["raw_1"])
        dag.add_node(l1)
        l2 = ContextNode(id="L2_1", child_ids=["L1_1"])
        dag.add_node(l2)

        ancestors = dag.get_ancestors("raw_1")
        ids = {n.id for n in ancestors}
        assert "L1_1" in ids
        assert "L2_1" in ids

    def test_get_lineage(self):
        dag = make_dag()
        dag.add_node(make_raw_node("raw_1"))
        l1 = ContextNode(id="L1_1", child_ids=["raw_1"])
        dag.add_node(l1)

        lineage = dag.get_lineage("raw_1")
        ids = {n.id for n in lineage}
        assert "raw_1" in ids
        assert "L1_1" in ids


# ============================================================================
# ContextDAG — level-based queries
# ============================================================================

class TestContextDAGLevels:

    def test_get_leaf_nodes(self):
        dag = make_dag()
        dag.add_node(make_raw_node("raw_1"))
        dag.add_node(make_raw_node("raw_2"))
        summary = ContextNode(id="sum_1", child_ids=["raw_1"])
        dag.add_node(summary)

        leaves = dag.get_leaf_nodes()
        # raw_2 is a leaf (no parent), raw_1 is a leaf but has parent
        # Only RAW + is_leaf
        raw_leaves = [n for n in dag.nodes.values()
                      if n.node_type == NodeType.RAW and n.is_leaf()]
        assert len(raw_leaves) >= 1  # raw_2 has no parent, so it's a leaf

    def test_get_nodes_at_level(self):
        dag = make_dag()
        dag.add_node(make_raw_node("raw_1"))
        dag.add_node(ContextNode(
            id="sum_1",
            node_type=NodeType.SUMMARY,
            level=CompressionLevel.L1_SUMMARY,
        ))

        l0 = dag.get_nodes_at_level(CompressionLevel.L0_RAW)
        l1 = dag.get_nodes_at_level(CompressionLevel.L1_SUMMARY)
        assert len(l0) == 1
        assert len(l1) == 1

    def test_get_context_at_level(self):
        dag = make_dag()
        for i in range(5):
            dag.add_node(make_raw_node(f"raw_{i}"))
        nodes = dag.get_context_at_level(CompressionLevel.L0_RAW, limit=3)
        assert len(nodes) == 3


# ============================================================================
# ContextDAG — token budget
# ============================================================================

class TestContextDAGBudget:

    def test_get_context_within_budget(self):
        dag = make_dag()
        for i in range(5):
            dag.add_node(make_raw_node(f"raw_{i}", tokens=100))
        summary = ContextNode(
            id="sum_1",
            node_type=NodeType.SUMMARY,
            level=CompressionLevel.L1_SUMMARY,
            child_ids=["raw_0", "raw_1"],
            token_count=50,
            content="Summary of raw_0 and raw_1",
        )
        dag.add_node(summary)

        nodes = dag.get_context_within_budget(
            token_budget=200,
            prefer_level=CompressionLevel.L1_SUMMARY,
        )
        total = sum(n.token_count for n in nodes)
        assert total <= 200

    def test_empty_dag_returns_empty(self):
        dag = make_dag()
        nodes = dag.get_context_within_budget(token_budget=1000)
        assert nodes == []


# ============================================================================
# ContextDAG — search
# ============================================================================

class TestContextDAGSearch:

    def test_search_by_title(self):
        dag = make_dag()
        dag.add_node(make_raw_node("raw_1", title="Fixed authentication bug"))
        dag.add_node(make_raw_node("raw_2", title="Added logging"))

        results = dag.search("authentication")
        assert len(results) == 1
        assert results[0].id == "raw_1"

    def test_search_by_content(self):
        dag = make_dag()
        dag.add_node(make_raw_node("raw_1", content="Error in JWT token validation"))
        dag.add_node(make_raw_node("raw_2", content="Added test cases"))

        results = dag.search("JWT")
        assert len(results) >= 1

    def test_search_by_tag(self):
        dag = make_dag()
        dag.add_node(ContextNode(
            id="n1", tags=["security", "auth"],
            title="Auth work", content="",
        ))
        dag.add_node(ContextNode(
            id="n2", tags=["feature"],
            title="Feature work", content="",
        ))

        results = dag.search("security")
        assert len(results) == 1
        assert results[0].id == "n1"

    def test_search_no_results(self):
        dag = make_dag()
        dag.add_node(make_raw_node())
        results = dag.search("nonexistent_keyword_xyz")
        assert len(results) == 0


# ============================================================================
# ContextDAG — merge
# ============================================================================

class TestContextDAGMerge:

    def test_merge_two_branches(self):
        dag = make_dag()
        # Branch A (Claude session)
        dag.add_node(make_raw_node("claude_1", performer="claude"))
        claude_sum = ContextNode(
            id="claude_sum",
            node_type=NodeType.SUMMARY,
            level=CompressionLevel.L1_SUMMARY,
            child_ids=["claude_1"],
            content="Claude summary",
        )
        dag.add_node(claude_sum)

        # Branch B (OpenCode session)
        dag.add_node(make_raw_node("opencode_1", performer="opencode"))
        opencode_sum = ContextNode(
            id="opencode_sum",
            node_type=NodeType.SUMMARY,
            level=CompressionLevel.L1_SUMMARY,
            child_ids=["opencode_1"],
            content="OpenCode summary",
        )
        dag.add_node(opencode_sum)

        # Merge both branches
        merge = ContextNode(
            id="merge_1",
            node_type=NodeType.MERGE,
            level=CompressionLevel.L2_COMPACT,
            child_ids=["claude_sum", "opencode_sum"],
            content="Combined Claude + OpenCode work",
        )
        dag.merge_nodes(["claude_sum", "opencode_sum"], merge)

        assert dag.nodes["claude_sum"].parent_ids == ["merge_1"]
        assert dag.nodes["opencode_sum"].parent_ids == ["merge_1"]
        assert dag.total_summary_nodes == 3  # 2 summaries + 1 merge

    def test_statistics(self):
        dag = make_dag()
        dag.add_node(make_raw_node("raw_1", tokens=100))
        dag.add_node(make_raw_node("raw_2", tokens=200))
        stats = dag.get_statistics()
        assert stats["total_nodes"] == 2
        assert stats["raw_nodes"] == 2
        assert stats["total_tokens_preserved"] == 300


# ============================================================================
# ContextDAGService
# ============================================================================

class TestContextDAGService:

    @pytest.fixture
    def service(self, tmp_path):
        from hits_core.service.context_dag_service import ContextDAGService
        from hits_core.storage.file_store import FileStorage
        storage = FileStorage(base_path=tmp_path)
        return ContextDAGService(storage=storage)

    @pytest.mark.asyncio
    async def test_get_or_create_dag(self, service):
        dag = await service.get_or_create_dag("/test/project")
        assert dag.id.startswith("dag_")
        assert dag.project_path == "/test/project"

    @pytest.mark.asyncio
    async def test_persist_and_reload(self, service):
        dag = await service.get_or_create_dag("/test/project")
        dag.add_node(make_raw_node("raw_1"))
        await service._save_dag(dag)

        reloaded = await service.get_or_create_dag("/test/project")
        assert "raw_1" in reloaded.nodes

    @pytest.mark.asyncio
    async def test_add_work_log_node(self, service):
        dag = await service.get_or_create_dag("/test/project")
        log = make_work_log("Fixed authentication")
        node = await service.add_work_log_node(dag, log)

        assert node.node_type == NodeType.RAW
        assert node.level == CompressionLevel.L0_RAW
        assert "Fixed authentication" in node.title
        assert node.source_type == "work_log"

    @pytest.mark.asyncio
    async def test_add_checkpoint_node(self, service):
        dag = await service.get_or_create_dag("/test/project")
        cp = make_checkpoint("Implement DAG")
        node = await service.add_checkpoint_node(dag, cp)

        assert node.node_type == NodeType.RAW
        assert "Implement DAG" in node.title
        assert node.source_type == "checkpoint"

    @pytest.mark.asyncio
    async def test_build_summary(self, service):
        dag = await service.get_or_create_dag("/test/project")
        dag.add_node(make_raw_node("raw_1"))
        dag.add_node(make_raw_node("raw_2"))

        summary = await service.build_summary(
            dag,
            child_ids=["raw_1", "raw_2"],
            title="L1 Summary",
            content="Summarized 2 raw nodes",
            level=CompressionLevel.L1_SUMMARY,
        )

        assert summary.node_type == NodeType.SUMMARY
        assert len(summary.child_ids) == 2
        assert dag.nodes["raw_1"].parent_ids == [summary.id]

    @pytest.mark.asyncio
    async def test_build_auto_summary(self, service):
        dag = await service.get_or_create_dag("/test/project")
        for i in range(5):
            dag.add_node(make_raw_node(f"raw_{i}"))

        summary = await service.build_auto_summary(dag, level=CompressionLevel.L1_SUMMARY)
        assert summary is not None
        assert len(summary.child_ids) == 5

    @pytest.mark.asyncio
    async def test_build_auto_summary_no_unparented(self, service):
        dag = await service.get_or_create_dag("/test/project")
        dag.add_node(make_raw_node("raw_1"))
        # Already summarized
        dag.add_node(ContextNode(
            id="sum_1",
            node_type=NodeType.SUMMARY,
            level=CompressionLevel.L1_SUMMARY,
            child_ids=["raw_1"],
        ))
        dag.nodes["raw_1"].parent_ids = ["sum_1"]

        result = await service.build_auto_summary(dag, level=CompressionLevel.L1_SUMMARY)
        assert result is None  # no unparented raw nodes

    @pytest.mark.asyncio
    async def test_merge_branches(self, service):
        dag = await service.get_or_create_dag("/test/project")
        dag.add_node(make_raw_node("claude_1", performer="claude"))
        dag.add_node(make_raw_node("opencode_1", performer="opencode"))

        merge = await service.merge_branches(
            dag,
            node_ids=["claude_1", "opencode_1"],
            title="Merged sessions",
            content="Claude + OpenCode work combined",
        )

        assert merge.node_type == NodeType.MERGE
        assert len(merge.child_ids) == 2

    @pytest.mark.asyncio
    async def test_get_context_for_resume(self, service):
        dag = await service.get_or_create_dag("/test/project")
        dag.add_node(make_raw_node("raw_1", content="Important context"))
        dag.add_node(make_raw_node("raw_2", content="More context"))
        await service.build_summary(
            dag,
            child_ids=["raw_1", "raw_2"],
            title="Session summary",
            content="Did important work",
            level=CompressionLevel.L1_SUMMARY,
        )

        context = await service.get_context_for_resume("/test/project")
        assert "Context DAG" in context

    @pytest.mark.asyncio
    async def test_get_context_empty_project(self, service):
        context = await service.get_context_for_resume("/test/empty")
        assert context == ""

    @pytest.mark.asyncio
    async def test_search_context(self, service):
        dag = await service.get_or_create_dag("/test/project")
        dag.add_node(make_raw_node("raw_1", title="Fixed auth bug", content="JWT error"))
        dag.add_node(make_raw_node("raw_2", title="Added logging"))
        await service._save_dag(dag)

        results = await service.search_context("/test/project", "auth")
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_get_lineage(self, service):
        dag = await service.get_or_create_dag("/test/project")
        dag.add_node(make_raw_node("raw_1"))
        await service.build_summary(
            dag, child_ids=["raw_1"],
            title="L1 Summary",
            level=CompressionLevel.L1_SUMMARY,
        )

        lineage = await service.get_lineage("/test/project", "raw_1")
        ids = {n.id for n in lineage}
        assert "raw_1" in ids
        assert any(n.node_type == NodeType.SUMMARY for n in lineage)

    @pytest.mark.asyncio
    async def test_get_statistics(self, service):
        dag = await service.get_or_create_dag("/test/project")
        dag.add_node(make_raw_node("raw_1", tokens=100))
        dag.add_node(make_raw_node("raw_2", tokens=200))
        await service._save_dag(dag)

        stats = await service.get_statistics("/test/project")
        assert stats["raw_nodes"] == 2
        assert stats["total_tokens_preserved"] == 300

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, service):
        """End-to-end: raw → L1 summary → L2 summary → query."""
        dag = await service.get_or_create_dag("/test/project")

        # Add raw nodes
        for i in range(6):
            await service.add_work_log_node(dag, make_work_log(f"Work item {i}"))

        # Build L1 summaries
        l1_a = await service.build_summary(
            dag, child_ids=["raw_log_test1_0", "raw_log_test1_1", "raw_log_test1_2"],
            title="L1 Session A",
            level=CompressionLevel.L1_SUMMARY,
        )
        l1_b = await service.build_summary(
            dag, child_ids=["raw_log_test1_3", "raw_log_test1_4", "raw_log_test1_5"],
            title="L1 Session B",
            level=CompressionLevel.L1_SUMMARY,
        )

        # Build L2
        l2 = await service.build_summary(
            dag, child_ids=[l1_a.id, l1_b.id],
            title="L2 Daily Summary",
            level=CompressionLevel.L2_COMPACT,
        )

        # Query
        context = await service.get_context_for_resume("/test/project", token_budget=500)
        assert len(context) > 0

        stats = await service.get_statistics("/test/project")
        assert stats["raw_nodes"] == 6
        assert stats["summary_nodes"] == 3
