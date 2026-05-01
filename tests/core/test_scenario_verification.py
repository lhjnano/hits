"""Scenario-based verification tests — production failure edge cases.

These tests verify that the code handles real-world failure scenarios
that could occur in production, not just happy-path functionality.

Categories:
1. LLM Client: API failures, malformed responses, fallback integrity
2. Token Tracker: corrupt files, budget boundaries, concurrent writes
3. Context DAG: orphan nodes, budget=0, circular references, deep chains
4. Workflow Checkpoint: state transition violations, corrupt persistence
5. WebSocket EventBus: concurrent publish, rapid connect/disconnect
"""

import asyncio
import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

# ===========================================================================
# 1. LLM Client — Production Failure Scenarios
# ===========================================================================

from hits_core.ai.llm_client import (
    LLMClient,
    LLMProvider,
    MockLLMProvider,
    OpenAIProvider,
    AnthropicProvider,
    create_provider,
    LLMUsage,
)


class TestLLMClientAPIFailures:
    """What happens when the LLM API fails in various ways?"""

    @pytest.mark.asyncio
    async def test_api_returns_malformed_json(self):
        """Scenario: API returns 200 but body is not valid JSON."""
        provider = OpenAIProvider(api_key="sk-test")
        client = LLMClient(provider=provider)

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b"not json at all"
            mock_urlopen.return_value = mock_resp

            # Should fallback to mock, not crash
            result = await client.analyze_node("test data")
            assert "[Mock Response]" in result
            assert client.usage.total_errors == 1

    @pytest.mark.asyncio
    async def test_api_returns_empty_choices(self):
        """Scenario: API returns valid JSON but missing 'choices' key."""
        provider = OpenAIProvider(api_key="sk-test")
        client = LLMClient(provider=provider)

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({"id": "chatcmpl-1"}).encode()
            mock_urlopen.return_value = mock_resp

            result = await client.analyze_node("test data")
            assert "[Mock Response]" in result
            assert client.usage.total_errors == 1

    @pytest.mark.asyncio
    async def test_api_returns_http_401(self):
        """Scenario: API key expired / invalid → 401."""
        import urllib.error

        provider = OpenAIProvider(api_key="sk-expired")
        client = LLMClient(provider=provider)

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.HTTPError(
                url="https://api.openai.com/v1/chat/completions",
                code=401,
                msg="Unauthorized",
                hdrs={},
                fp=None,
            )

            result = await client.analyze_node("test")
            assert "[Mock Response]" in result
            assert client.usage.total_errors == 1

    @pytest.mark.asyncio
    async def test_api_returns_http_429_rate_limit(self):
        """Scenario: Rate limited by API provider → 429."""
        import urllib.error

        provider = AnthropicProvider(api_key="sk-ant-test")
        client = LLMClient(provider=provider)

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.HTTPError(
                url="https://api.anthropic.com/v1/messages",
                code=429,
                msg="Too Many Requests",
                hdrs={},
                fp=None,
            )

            result = await client.analyze_node("test")
            assert "[Mock Response]" in result

    @pytest.mark.asyncio
    async def test_network_timeout(self):
        """Scenario: Network timeout during API call."""
        import urllib.error

        provider = OpenAIProvider(api_key="sk-test")
        client = LLMClient(provider=provider)

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError("Connection timed out")

            result = await client.smart_compress("long text " * 100)
            assert "[Mock Response]" in result

    @pytest.mark.asyncio
    async def test_suggest_children_with_empty_response(self):
        """Scenario: LLM returns empty string for suggest_children."""
        failing_provider = AsyncMock(spec=LLMProvider)
        failing_provider.generate = AsyncMock(return_value="")
        failing_provider.is_available = MagicMock(return_value=True)

        client = LLMClient(provider=failing_provider)
        suggestions = await client.suggest_children("test node")

        # Should handle gracefully — empty list, not crash
        assert isinstance(suggestions, list)

    @pytest.mark.asyncio
    async def test_extract_insights_with_non_json_response(self):
        """Scenario: LLM returns prose instead of JSON for extract_insights."""
        prose_provider = AsyncMock(spec=LLMProvider)
        prose_provider.generate = AsyncMock(
            return_value="The project made good progress. Key issue was auth."
        )
        prose_provider.is_available = MagicMock(return_value=True)

        client = LLMClient(provider=prose_provider)
        result = await client.extract_insights(["log1", "log2"])

        # Should fallback to progress_summary field
        assert "progress_summary" in result
        assert result["key_decisions"] == []
        assert result["warnings"] == []

    @pytest.mark.asyncio
    async def test_extract_insights_with_partial_json(self):
        """Scenario: LLM returns JSON embedded in markdown."""
        md_provider = AsyncMock(spec=LLMProvider)
        md_provider.generate = AsyncMock(
            return_value='Here are the insights:\n```json\n{"key_decisions": ["Use Redis"], "patterns": [], "warnings": ["Cost rising"], "progress_summary": "70% done"}\n```'
        )
        md_provider.is_available = MagicMock(return_value=True)

        client = LLMClient(provider=md_provider)
        result = await client.extract_insights(["log1"])

        assert "Use Redis" in result["key_decisions"]
        assert "Cost rising" in result["warnings"]

    @pytest.mark.asyncio
    async def test_error_counter_accumulates_correctly(self):
        """Scenario: Multiple consecutive API failures."""
        import urllib.error

        provider = OpenAIProvider(api_key="sk-test")
        client = LLMClient(provider=provider)

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError("fail")

            for _ in range(5):
                await client.analyze_node("test")

            assert client.usage.total_errors == 5
            assert client.usage.total_requests == 5

    @pytest.mark.asyncio
    async def test_provider_without_key_raises_on_direct_call(self):
        """Scenario: OpenAI provider with no key → RuntimeError on generate()."""
        provider = OpenAIProvider(api_key=None)
        with patch.dict("os.environ", {}, clear=False):
            # Remove any env keys
            with patch("os.environ.get", return_value=None):
                # Provider should not be available
                assert not provider.is_available()
                # Direct generate should raise
                with pytest.raises(RuntimeError, match="API key not configured"):
                    await provider.generate("test")

    def test_create_provider_with_empty_string_key(self):
        """Scenario: API key set to empty string."""
        provider = create_provider(provider_name="openai", api_key="")
        # Empty string is falsy, should fallback to mock
        assert isinstance(provider, MockLLMProvider)


# ===========================================================================
# 2. Token Tracker — Corrupt Data & Boundary Scenarios
# ===========================================================================

from hits_core.service.token_tracker import (
    TokenTrackerService,
    TokenRecord,
    TokenBudget,
    estimate_cost,
    MODEL_COSTS_PER_1K,
)


class TestTokenTrackerCorruptData:
    """What happens when data files are corrupted?"""

    def _make_service(self, tmp_path: Path) -> TokenTrackerService:
        return TokenTrackerService(data_dir=tmp_path)

    def test_corrupt_jsonl_line_in_middle(self, tmp_path):
        """Scenario: Crash during write leaves a partial line in JSONL."""
        svc = self._make_service(tmp_path)

        # Write 3 valid records
        svc.record(project_path="/proj", tokens_in=100, tokens_out=50)
        svc.record(project_path="/proj", tokens_in=200, tokens_out=100)

        # Manually append a corrupt line
        date_str = datetime.now().strftime("%Y-%m-%d")
        record_file = svc._records_dir / f"{date_str}.jsonl"
        with open(record_file, "a") as f:
            f.write("{corrupt json without closing\n")

        # Write another valid record after
        svc.record(project_path="/proj", tokens_in=300, tokens_out=150)

        # Should still load 3 valid records, skip the corrupt one
        records = svc._load_records(project_path="/proj")
        assert len(records) == 3

    def test_empty_jsonl_file(self, tmp_path):
        """Scenario: JSONL file exists but is empty."""
        svc = self._make_service(tmp_path)
        date_str = datetime.now().strftime("%Y-%m-%d")
        record_file = svc._records_dir / f"{date_str}.jsonl"
        record_file.write_text("")

        records = svc._load_records()
        assert records == []

    def test_jsonl_with_only_whitespace(self, tmp_path):
        """Scenario: JSONL file has blank lines."""
        svc = self._make_service(tmp_path)
        date_str = datetime.now().strftime("%Y-%m-%d")
        record_file = svc._records_dir / f"{date_str}.jsonl"
        record_file.write_text("\n\n   \n\n")

        records = svc._load_records()
        assert records == []

    def test_corrupt_budget_file(self, tmp_path):
        """Scenario: Budget file is corrupt JSON."""
        svc = self._make_service(tmp_path)
        svc.set_budget("/proj", monthly_token_limit=1000)

        # Corrupt the budget file
        budget_file = svc._budgets_dir / f"{svc._project_key('/proj')}.json"
        budget_file.write_text("{corrupt")

        # Should return None gracefully
        assert svc.get_budget("/proj") is None

    def test_corrupt_budget_file_with_empty_content(self, tmp_path):
        """Scenario: Budget file is empty."""
        svc = self._make_service(tmp_path)
        svc.set_budget("/proj", monthly_token_limit=1000)

        budget_file = svc._budgets_dir / f"{svc._project_key('/proj')}.json"
        budget_file.write_text("")

        assert svc.get_budget("/proj") is None


class TestTokenTrackerBudgetBoundaries:
    """Budget edge cases."""

    def _make_service(self, tmp_path: Path) -> TokenTrackerService:
        return TokenTrackerService(data_dir=tmp_path)

    def test_budget_exactly_at_threshold(self, tmp_path):
        """Scenario: Usage is exactly at alert threshold (80%)."""
        svc = self._make_service(tmp_path)
        svc.set_budget("/proj", monthly_token_limit=1000, alert_threshold_pct=80.0)

        # Use exactly 800 tokens (80%)
        svc.record(project_path="/proj", tokens_in=800, tokens_out=0)

        alert = svc.check_budget_alert("/proj")
        assert alert is not None
        assert "80.0%" in alert

    def test_budget_just_under_threshold(self, tmp_path):
        """Scenario: Usage is 79.9% — should NOT alert."""
        svc = self._make_service(tmp_path)
        svc.set_budget("/proj", monthly_token_limit=1000, alert_threshold_pct=80.0)

        svc.record(project_path="/proj", tokens_in=799, tokens_out=0)

        alert = svc.check_budget_alert("/proj")
        assert alert is None

    def test_budget_exceeded_100_pct(self, tmp_path):
        """Scenario: Usage exceeds 100% of budget."""
        svc = self._make_service(tmp_path)
        svc.set_budget("/proj", monthly_token_limit=1000)

        svc.record(project_path="/proj", tokens_in=1200, tokens_out=0)

        remaining = svc.get_remaining_budget("/proj")
        assert remaining == 0  # Clamped to 0, not negative

    def test_no_budget_set_returns_none(self, tmp_path):
        """Scenario: No budget configured → None."""
        svc = self._make_service(tmp_path)
        assert svc.get_budget("/no-proj") is None
        assert svc.get_remaining_budget("/no-proj") is None
        assert svc.check_budget_alert("/no-proj") is None

    def test_budget_with_zero_limit_means_unlimited(self, tmp_path):
        """Scenario: Budget exists but limit is 0 (unlimited)."""
        svc = self._make_service(tmp_path)
        svc.set_budget("/proj", monthly_token_limit=0)

        assert svc.get_remaining_budget("/proj") is None  # unlimited


class TestTokenTrackerCostEstimation:
    """Cost estimation edge cases."""

    def test_unknown_model_returns_zero(self):
        """Scenario: Model not in cost table."""
        cost = estimate_cost("future-model-2027", 1000, 1000)
        assert cost == 0.0  # Unknown models default to zero

    def test_partial_model_match(self):
        """Scenario: Model variant not exact match (gpt-4o-2024-05-13)."""
        cost = estimate_cost("gpt-4o-2024-05-13", 1000, 1000)
        assert cost > 0  # Should match "gpt-4o" prefix

    def test_none_model_returns_zero(self):
        cost = estimate_cost(None, 1000, 1000)
        assert cost == 0.0

    def test_zero_tokens(self):
        cost = estimate_cost("gpt-4o", 0, 0)
        assert cost == 0.0

    def test_negative_tokens_handled(self):
        """Scenario: Negative token count (data corruption)."""
        # estimate_cost doesn't validate — just calculate
        cost = estimate_cost("gpt-4o", -100, 0)
        assert cost < 0  # Mathematically correct but indicates upstream bug


class TestTokenTrackerSpecialPaths:
    """Project path edge cases."""

    def _make_service(self, tmp_path: Path) -> TokenTrackerService:
        return TokenTrackerService(data_dir=tmp_path)

    def test_project_path_with_unicode(self, tmp_path):
        """Scenario: Project path contains Korean characters."""
        svc = self._make_service(tmp_path)
        svc.record(project_path="/home/user/프로젝트", tokens_in=100)
        stats = svc.get_project_stats("/home/user/프로젝트")
        assert stats.total_records == 1

    def test_project_path_with_spaces(self, tmp_path):
        """Scenario: Path has spaces."""
        svc = self._make_service(tmp_path)
        svc.record(project_path="/home/user/my project", tokens_in=100)
        stats = svc.get_project_stats("/home/user/my project")
        assert stats.total_records == 1

    def test_empty_project_path(self, tmp_path):
        """Scenario: Empty string project path."""
        svc = self._make_service(tmp_path)
        svc.record(project_path="", tokens_in=100)
        stats = svc.get_project_stats("")
        assert stats.total_records >= 1


# ===========================================================================
# 3. Context DAG — Structural Failure Scenarios
# ===========================================================================

from hits_core.models.context_dag import (
    ContextDAG,
    ContextNode,
    NodeType,
    CompressionLevel,
)
from hits_core.service.context_dag_service import ContextDAGService
from hits_core.storage.file_store import FileStorage


class TestContextDAGStructuralEdgeCases:
    """What happens with unusual DAG structures?"""

    def _make_dag(self) -> ContextDAG:
        return ContextDAG(id="dag_test", project_path="/test")

    def test_remove_node_that_is_also_root(self):
        """Scenario: Removing the root summary node."""
        dag = self._make_dag()

        raw = ContextNode(id="raw_1", node_type=NodeType.RAW, level=CompressionLevel.L0_RAW)
        summary = ContextNode(
            id="sum_1", node_type=NodeType.SUMMARY,
            level=CompressionLevel.L1_SUMMARY, child_ids=["raw_1"],
        )
        dag.add_node(raw)
        dag.add_node(summary)
        dag.root_id = summary.id

        removed = dag.remove_node(summary.id)
        assert removed is not None
        assert dag.root_id is None
        # Raw node should still exist
        assert dag.get_node("raw_1") is not None

    def test_add_node_with_nonexistent_child_ids(self):
        """Scenario: Summary references child that doesn't exist yet."""
        dag = self._make_dag()

        summary = ContextNode(
            id="sum_1", node_type=NodeType.SUMMARY,
            level=CompressionLevel.L1_SUMMARY,
            child_ids=["raw_ghost"],  # doesn't exist
        )
        # Should not crash
        dag.add_node(summary)
        assert dag.get_node("sum_1") is not None

    def test_get_context_with_zero_budget(self):
        """Scenario: Token budget is 0."""
        dag = self._make_dag()
        raw = ContextNode(id="raw_1", token_count=100)
        dag.add_node(raw)

        result = dag.get_context_within_budget(token_budget=0)
        assert result == []

    def test_get_context_with_budget_smaller_than_any_node(self):
        """Scenario: All nodes exceed the budget."""
        dag = self._make_dag()
        raw = ContextNode(id="raw_1", token_count=5000)
        dag.add_node(raw)

        result = dag.get_context_within_budget(token_budget=100)
        assert result == []

    def test_search_with_empty_query(self):
        """Scenario: Empty search query returns nothing."""
        dag = self._make_dag()
        raw = ContextNode(id="raw_1", title="Important", content="Data")
        dag.add_node(raw)

        result = dag.search("")
        assert result == []

    def test_search_with_special_regex_chars(self):
        """Scenario: Query contains regex-like characters (should not crash)."""
        dag = self._make_dag()
        raw = ContextNode(id="raw_1", title="test.*+?{}[]() thing")
        dag.add_node(raw)

        # Should not raise regex error
        result = dag.search(".*+?{}[]()")
        assert len(result) == 1

    def test_get_lineage_for_nonexistent_node(self):
        """Scenario: Query lineage for a node that doesn't exist."""
        dag = self._make_dag()
        result = dag.get_lineage("ghost_node")
        assert result == []

    def test_get_descendants_and_ancestors_empty(self):
        """Scenario: Node with no connections."""
        dag = self._make_dag()
        raw = ContextNode(id="raw_1")
        dag.add_node(raw)

        assert dag.get_descendants("raw_1") == []
        assert dag.get_ancestors("raw_1") == []

    def test_deep_chain_does_not_overflow(self):
        """Scenario: 50-level deep summary chain."""
        dag = self._make_dag()

        prev_id = None
        for i in range(50):
            node = ContextNode(
                id=f"node_{i}",
                node_type=NodeType.RAW if i == 0 else NodeType.SUMMARY,
                level=CompressionLevel.L0_RAW if i == 0 else CompressionLevel.L1_SUMMARY,
                child_ids=[prev_id] if prev_id else [],
                token_count=10,
            )
            dag.add_node(node)
            prev_id = node.id

        # Descendants of root should be 49
        descendants = dag.get_descendants("node_49")
        assert len(descendants) == 49

    def test_merge_overlapping_branches(self):
        """Scenario: Merge with some duplicate node_ids."""
        dag = self._make_dag()

        raw1 = ContextNode(id="raw_1", node_type=NodeType.RAW, token_count=10)
        raw2 = ContextNode(id="raw_2", node_type=NodeType.RAW, token_count=10)
        dag.add_node(raw1)
        dag.add_node(raw2)

        # Merge with duplicate node_ids in list
        merge = ContextNode(
            id="merge_1", node_type=NodeType.MERGE,
            child_ids=["raw_1", "raw_2", "raw_1"],  # duplicate!
        )
        dag.merge_nodes(["raw_1", "raw_2", "raw_1"], merge)

        # Should handle duplicates gracefully
        assert dag.get_node("merge_1") is not None


class TestContextDAGServiceCorruptPersistence:
    """What happens when DAG files on disk are corrupted?"""

    @pytest.mark.asyncio
    async def test_corrupt_dag_file_returns_new_dag(self, tmp_path):
        """Scenario: DAG file exists but contains invalid JSON."""
        storage = FileStorage(base_path=tmp_path)
        svc = ContextDAGService(storage=storage)

        # Write corrupt DAG file
        dag_dir = tmp_path / "context_dags"
        dag_dir.mkdir(parents=True, exist_ok=True)
        dag_file = dag_dir / "test_project.json"
        dag_file.write_text("{corrupt json")

        dag = await svc.get_or_create_dag("/test/project")
        # Should create a fresh DAG, not crash
        assert dag is not None
        assert dag.project_path == "/test/project"

    @pytest.mark.asyncio
    async def test_get_statistics_for_nonexistent_project(self, tmp_path):
        """Scenario: Query stats for project that never had a DAG."""
        storage = FileStorage(base_path=tmp_path)
        svc = ContextDAGService(storage=storage)

        stats = await svc.get_statistics("/nonexistent")
        assert stats["total_nodes"] == 0

    @pytest.mark.asyncio
    async def test_search_empty_project(self, tmp_path):
        """Scenario: Search on a project with no DAG."""
        storage = FileStorage(base_path=tmp_path)
        svc = ContextDAGService(storage=storage)

        results = await svc.search_context("/new/project", "test")
        assert results == []

    @pytest.mark.asyncio
    async def test_resume_context_empty_dag(self, tmp_path):
        """Scenario: Resume context when DAG has no nodes."""
        storage = FileStorage(base_path=tmp_path)
        svc = ContextDAGService(storage=storage)

        context = await svc.get_context_for_resume("/test/proj", token_budget=2000)
        assert context == ""


# ===========================================================================
# 4. Workflow Checkpoint — State Transition Violations
# ===========================================================================

from hits_core.models.workflow_checkpoint import (
    WorkflowCheckpoint,
    StageDefinition,
    StageCheckpoint,
    StageStatus,
    WorkflowStatus,
)
from hits_core.service.workflow_checkpoint_service import WorkflowCheckpointService


class TestWorkflowStateTransitionViolations:
    """What happens when stages are operated on in wrong order?"""

    def _make_simple_workflow(self) -> WorkflowCheckpoint:
        return WorkflowCheckpoint(
            workflow_id="wf_test",
            project_path="/test",
            name="Test Workflow",
            stages=[
                StageDefinition(id="s1", name="Stage 1", agent="agent-1"),
                StageDefinition(id="s2", name="Stage 2", agent="agent-2",
                              dependencies=["s1"]),
                StageDefinition(id="s3", name="Stage 3", agent="agent-3",
                              dependencies=["s2"]),
            ],
        )

    def test_complete_stage_before_start(self):
        """Scenario: Complete a stage that was never started should raise."""
        wf = self._make_simple_workflow()

        # s1 is still "pending" — complete without start should raise
        with pytest.raises(ValueError, match="has not been started"):
            wf.complete_stage("s1")

    def test_fail_already_completed_stage(self):
        """Scenario: Fail a stage that already completed — auto-start then fail."""
        wf = self._make_simple_workflow()
        wf.start_stage("s1")
        wf.complete_stage("s1")

        # fail_stage on completed stage: auto-starts then fails
        wf.fail_stage("s1", "Something went wrong later")
        assert wf.get_stage_status("s1") == StageStatus.FAILED

    def test_start_already_running_stage(self):
        """Scenario: Start a stage that's already running — replaces it."""
        wf = self._make_simple_workflow()
        wf.start_stage("s1")
        wf.start_stage("s1")  # double start — replaces existing

        # Should still be RUNNING
        assert wf.get_stage_status("s1") == StageStatus.RUNNING

    def test_get_next_pending_with_all_completed(self):
        """Scenario: All stages done → no next pending."""
        wf = self._make_simple_workflow()
        wf.start_stage("s1")
        wf.complete_stage("s1")
        wf.start_stage("s2")
        wf.complete_stage("s2")
        wf.start_stage("s3")
        wf.complete_stage("s3")

        next_stage = wf.get_next_pending_stage()
        assert next_stage is None
        assert wf.status == WorkflowStatus.COMPLETED

    def test_get_next_pending_skips_failed_stage_with_unmet_deps(self):
        """Scenario: s1 fails → s2 has dep on s1 → s2 is blocked."""
        wf = self._make_simple_workflow()
        wf.start_stage("s1")
        wf.fail_stage("s1", "error")

        # s2 depends on s1 which failed → should be skipped
        next = wf.get_next_pending_stage()
        # s2 has unmet dependency, s3 depends on s2 → all blocked
        assert next is None or next.id != "s2"

    def test_workflow_with_empty_stages(self):
        """Scenario: Create workflow with no stages."""
        wf = WorkflowCheckpoint(
            workflow_id="wf_empty",
            project_path="/test",
            name="Empty",
            stages=[],
        )

        next_stage = wf.get_next_pending_stage()
        assert next_stage is None

    def test_workflow_resume_context_with_no_completed_stages(self):
        """Scenario: Resume context when nothing is done yet."""
        wf = self._make_simple_workflow()
        context = wf.get_resume_context()
        assert context is not None  # Should return something, not crash


class TestWorkflowServicePersistenceFailures:
    """What happens when persistence operations fail?"""

    @pytest.mark.asyncio
    async def test_get_nonexistent_workflow(self, tmp_path):
        """Scenario: Query a workflow that doesn't exist."""
        storage = FileStorage(base_path=tmp_path)
        svc = WorkflowCheckpointService(storage=storage)

        result = await svc.get_workflow("wf_ghost")
        assert result is None

    @pytest.mark.asyncio
    async def test_start_stage_on_nonexistent_workflow(self, tmp_path):
        """Scenario: Start a stage on a workflow that doesn't exist."""
        storage = FileStorage(base_path=tmp_path)
        svc = WorkflowCheckpointService(storage=storage)

        with pytest.raises(ValueError, match="not found"):
            await svc.start_stage("wf_ghost", "s1")

    @pytest.mark.asyncio
    async def test_complete_stage_on_nonexistent_workflow(self, tmp_path):
        """Scenario: Complete stage on missing workflow."""
        storage = FileStorage(base_path=tmp_path)
        svc = WorkflowCheckpointService(storage=storage)

        with pytest.raises(ValueError, match="not found"):
            await svc.complete_stage("wf_ghost", "s1")

    @pytest.mark.asyncio
    async def test_fail_stage_on_nonexistent_workflow(self, tmp_path):
        """Scenario: Fail stage on missing workflow."""
        storage = FileStorage(base_path=tmp_path)
        svc = WorkflowCheckpointService(storage=storage)

        with pytest.raises(ValueError, match="not found"):
            await svc.fail_stage("wf_ghost", "s1", "error")

    @pytest.mark.asyncio
    async def test_resume_nonexistent_workflow(self, tmp_path):
        """Scenario: Resume a workflow that doesn't exist."""
        storage = FileStorage(base_path=tmp_path)
        svc = WorkflowCheckpointService(storage=storage)

        result = await svc.resume_workflow("wf_ghost")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_workflows_with_corrupt_file(self, tmp_path):
        """Scenario: A corrupt workflow file in the directory."""
        storage = FileStorage(base_path=tmp_path)
        svc = WorkflowCheckpointService(storage=storage)

        # Create one valid workflow
        await svc.create_workflow("/test", "Valid", [
            StageDefinition(id="s1", name="S1", agent="a1"),
        ])

        # Write a corrupt file
        wf_dir = tmp_path / "workflows"
        (wf_dir / "wf_corrupt.json").write_text("{invalid}")

        # Should return only the valid one
        workflows = await svc.list_workflows()
        assert len(workflows) == 1
        assert workflows[0].name == "Valid"


# ===========================================================================
# 5. WebSocket EventBus — Concurrency & Edge Cases
# ===========================================================================

from hits_core.api.routes.ws import EventBus, LiveEvent


class TestWebSocketConcurrencyAndEdgeCases:
    """What happens under concurrent/high-load scenarios?"""

    @pytest.mark.asyncio
    async def test_concurrent_publishes(self):
        """Scenario: Multiple concurrent publishes to same bus."""
        bus = EventBus()
        ws = AsyncMock()
        ws.send_text = AsyncMock()
        await bus.subscribe(ws)

        # 10 concurrent publishes
        tasks = [
            bus.publish(f"event_{i}", data={"i": i})
            for i in range(10)
        ]
        results = await asyncio.gather(*tasks)

        # All should deliver to the single subscriber
        assert all(r == 1 for r in results)
        assert len(bus.get_history()) == 10

    @pytest.mark.asyncio
    async def test_rapid_subscribe_unsubscribe(self):
        """Scenario: Rapid subscribe/unsubscribe cycles."""
        bus = EventBus()
        ws = AsyncMock()

        for _ in range(100):
            await bus.subscribe(ws)
            await bus.unsubscribe(ws)

        assert bus.subscriber_count == 0

    @pytest.mark.asyncio
    async def test_publish_with_very_large_data(self):
        """Scenario: Event with large payload."""
        bus = EventBus()
        ws = AsyncMock()
        ws.send_text = AsyncMock()
        await bus.subscribe(ws)

        large_content = "x" * 100_000
        delivered = await bus.publish("large", data={"content": large_content})
        assert delivered == 1

        # Verify the large content was actually sent
        sent = ws.send_text.call_args[0][0]
        assert len(sent) > 100_000

    @pytest.mark.asyncio
    async def test_history_since_future_timestamp(self):
        """Scenario: Query history with a future timestamp."""
        bus = EventBus()
        await bus.publish("past_event")

        future = (datetime.now() + timedelta(days=365)).isoformat()
        result = bus.get_history_since(future)
        assert result == []

    @pytest.mark.asyncio
    async def test_history_since_empty(self):
        """Scenario: No events at all."""
        bus = EventBus()
        result = bus.get_history_since("2020-01-01T00:00:00")
        assert result == []

    @pytest.mark.asyncio
    async def test_dead_client_removed_during_concurrent_publish(self):
        """Scenario: Client dies during concurrent publishes."""
        bus = EventBus()
        alive = AsyncMock()
        alive.send_text = AsyncMock()
        dead = AsyncMock()
        dead.send_text = AsyncMock(side_effect=ConnectionResetError)

        await bus.subscribe(alive)
        await bus.subscribe(dead)

        # Concurrent publishes — dead client should be cleaned up
        await asyncio.gather(
            bus.publish("evt1"),
            bus.publish("evt2"),
            bus.publish("evt3"),
        )

        assert bus.subscriber_count == 1

    @pytest.mark.asyncio
    async def test_publish_after_all_clients_disconnect(self):
        """Scenario: Publish when no clients remain."""
        bus = EventBus()
        ws = AsyncMock()
        ws.send_text = AsyncMock(side_effect=Exception("gone"))

        await bus.subscribe(ws)
        await bus.publish("first")  # removes dead ws
        delivered = await bus.publish("second")  # no subscribers
        assert delivered == 0
        assert bus.subscriber_count == 0

    @pytest.mark.asyncio
    async def test_live_event_with_unicode_data(self):
        """Scenario: Event with Korean/emoji content."""
        bus = EventBus()
        ws = AsyncMock()
        ws.send_text = AsyncMock()
        await bus.subscribe(ws)

        await bus.publish("korean", data={"text": "안녕하세요 🔥🎉"})
        sent = ws.send_text.call_args[0][0]
        parsed = json.loads(sent)
        assert "안녕하세요" in parsed["data"]["text"]

    @pytest.mark.asyncio
    async def test_many_subscribers_reliability(self):
        """Scenario: 100 concurrent subscribers."""
        bus = EventBus()
        clients = []
        for _ in range(100):
            ws = AsyncMock()
            ws.send_text = AsyncMock()
            await bus.subscribe(ws)
            clients.append(ws)

        delivered = await bus.publish("broadcast_test", data={"hello": "world"})
        assert delivered == 100
