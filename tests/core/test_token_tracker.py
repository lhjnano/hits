"""Tests for Token Tracker — budget management and cost analytics.

Covers:
- estimate_cost: model-based cost calculation
- TokenTrackerService.record: JSONL recording
- Budget: set/get/remaining/alert
- Analytics: project stats, daily usage, top projects
- Edge cases: no budget, unlimited budget, empty records
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from hits_core.service.token_tracker import (
    TokenTrackerService,
    TokenRecord,
    TokenBudget,
    DailyUsage,
    ProjectTokenStats,
    estimate_cost,
    MODEL_COSTS_PER_1K,
)


# ============================================================================
# estimate_cost
# ============================================================================

class TestEstimateCost:

    def test_known_model_gpt4o(self):
        cost = estimate_cost("gpt-4o", tokens_in=1000, tokens_out=500)
        expected = (1000 / 1000 * 0.0025) + (500 / 1000 * 0.01)
        assert abs(cost - expected) < 0.0001

    def test_known_model_claude_sonnet(self):
        cost = estimate_cost("claude-3.5-sonnet", tokens_in=1000, tokens_out=500)
        expected = (1000 / 1000 * 0.003) + (500 / 1000 * 0.015)
        assert abs(cost - expected) < 0.0001

    def test_partial_model_match(self):
        """Model name with version suffix should still match."""
        cost = estimate_cost("gpt-4o-2024-08-06", tokens_in=1000, tokens_out=500)
        assert cost > 0  # should match "gpt-4o"

    def test_unknown_model_zero_cost(self):
        cost = estimate_cost("custom-model-v1", tokens_in=1000, tokens_out=500)
        assert cost == 0.0

    def test_none_model_zero_cost(self):
        cost = estimate_cost(None, tokens_in=1000, tokens_out=500)
        assert cost == 0.0

    def test_local_model_zero_cost(self):
        cost = estimate_cost("local", tokens_in=10000, tokens_out=5000)
        assert cost == 0.0

    def test_zero_tokens(self):
        cost = estimate_cost("gpt-4o", tokens_in=0, tokens_out=0)
        assert cost == 0.0


# ============================================================================
# TokenRecord
# ============================================================================

class TestTokenRecord:

    def test_default_values(self):
        rec = TokenRecord()
        assert rec.tokens_in == 0
        assert rec.tokens_out == 0
        assert rec.tokens_total == 0
        assert rec.estimated_cost_usd == 0.0

    def test_auto_id(self):
        rec = TokenRecord()
        assert rec.id.startswith("tr_")

    def test_fields(self):
        rec = TokenRecord(
            project_path="/test/project",
            performer="claude",
            tokens_in=500,
            tokens_out=200,
            tokens_total=700,
            model="gpt-4o",
            operation="chat",
        )
        assert rec.project_path == "/test/project"
        assert rec.model == "gpt-4o"


# ============================================================================
# TokenBudget
# ============================================================================

class TestTokenBudget:

    def test_default_budget(self):
        budget = TokenBudget(project_path="/test/project")
        assert budget.monthly_token_limit == 0  # unlimited
        assert budget.daily_token_limit == 0
        assert budget.alert_threshold_pct == 80.0


# ============================================================================
# TokenTrackerService — recording
# ============================================================================

class TestTokenTrackerRecording:

    @pytest.fixture
    def tracker(self, tmp_path):
        return TokenTrackerService(data_dir=tmp_path)

    def test_record_creates_file(self, tracker):
        rec = tracker.record(
            project_path="/test/project",
            performer="claude",
            tokens_in=500,
            tokens_out=200,
            model="gpt-4o",
        )
        assert rec.tokens_total == 700
        assert rec.estimated_cost_usd > 0

        # Check file exists
        date_str = datetime.now().strftime("%Y-%m-%d")
        record_file = tracker._records_dir / f"{date_str}.jsonl"
        assert record_file.exists()

    def test_record_appends_to_same_day(self, tracker):
        tracker.record(project_path="/test", performer="claude", tokens_in=100)
        tracker.record(project_path="/test", performer="opencode", tokens_in=200)

        records = tracker._load_records(project_path="/test")
        assert len(records) == 2

    def test_record_with_all_fields(self, tracker):
        rec = tracker.record(
            project_path="/test/project",
            performer="claude",
            tokens_in=1000,
            tokens_out=500,
            model="gpt-4o",
            operation="resume",
            session_id="sess_123",
            tags=["checkpoint", "handover"],
        )
        assert rec.operation == "resume"
        assert rec.session_id == "sess_123"
        assert "checkpoint" in rec.tags

    def test_record_without_optional_fields(self, tracker):
        rec = tracker.record(project_path="/test", performer="manual")
        assert rec.model is None
        assert rec.operation is None
        assert rec.tags == []


# ============================================================================
# TokenTrackerService — budget
# ============================================================================

class TestTokenTrackerBudget:

    @pytest.fixture
    def tracker(self, tmp_path):
        return TokenTrackerService(data_dir=tmp_path)

    def test_set_and_get_budget(self, tracker):
        tracker.set_budget(
            "/test/project",
            monthly_token_limit=100_000,
        )
        budget = tracker.get_budget("/test/project")
        assert budget is not None
        assert budget.monthly_token_limit == 100_000

    def test_get_budget_none_when_not_set(self, tracker):
        assert tracker.get_budget("/nonexistent") is None

    def test_remaining_budget_unlimited(self, tracker):
        # No budget = unlimited = None remaining
        remaining = tracker.get_remaining_budget("/test/project")
        assert remaining is None

    def test_remaining_budget_with_usage(self, tracker):
        tracker.set_budget("/test/project", monthly_token_limit=10_000)
        tracker.record(
            project_path="/test/project",
            performer="claude",
            tokens_in=3000,
            tokens_out=2000,
        )
        remaining = tracker.get_remaining_budget("/test/project")
        assert remaining == 5_000

    def test_remaining_budget_cant_go_negative(self, tracker):
        tracker.set_budget("/test/project", monthly_token_limit=1_000)
        tracker.record(
            project_path="/test/project",
            performer="claude",
            tokens_in=2000,
            tokens_out=1000,
        )
        remaining = tracker.get_remaining_budget("/test/project")
        assert remaining == 0

    def test_budget_alert_under_threshold(self, tracker):
        tracker.set_budget("/test/project", monthly_token_limit=10_000, alert_threshold_pct=80.0)
        tracker.record(project_path="/test/project", performer="claude", tokens_in=1000)
        alert = tracker.check_budget_alert("/test/project")
        assert alert is None  # only 10% used

    def test_budget_alert_over_threshold(self, tracker):
        tracker.set_budget("/test/project", monthly_token_limit=10_000, alert_threshold_pct=80.0)
        tracker.record(project_path="/test/project", performer="claude", tokens_in=8000)
        alert = tracker.check_budget_alert("/test/project")
        assert alert is not None
        assert "80.0%" in alert

    def test_budget_alert_no_budget(self, tracker):
        alert = tracker.check_budget_alert("/test/project")
        assert alert is None


# ============================================================================
# TokenTrackerService — analytics
# ============================================================================

class TestTokenTrackerAnalytics:

    @pytest.fixture
    def tracker(self, tmp_path):
        t = TokenTrackerService(data_dir=tmp_path)
        # Seed some data
        for i in range(5):
            t.record(
                project_path="/test/project",
                performer="claude" if i % 2 == 0 else "opencode",
                tokens_in=1000 + i * 100,
                tokens_out=500 + i * 50,
                model="gpt-4o" if i % 2 == 0 else "claude-3.5-sonnet",
                operation="chat" if i < 3 else "resume",
            )
        return t

    def test_project_stats(self, tracker):
        stats = tracker.get_project_stats("/test/project")
        assert stats.total_records == 5
        assert stats.total_tokens_in > 0
        assert stats.total_tokens_out > 0
        assert stats.total_tokens > 0
        assert stats.total_cost_usd > 0
        assert "claude" in stats.by_performer
        assert "opencode" in stats.by_performer
        assert "gpt-4o" in stats.by_model
        assert stats.active_days == 1
        assert stats.first_record is not None
        assert stats.last_record is not None

    def test_project_stats_empty(self, tracker):
        stats = tracker.get_project_stats("/nonexistent")
        assert stats.total_records == 0
        assert stats.total_tokens == 0

    def test_project_stats_with_budget(self, tracker):
        tracker.set_budget("/test/project", monthly_token_limit=100_000)
        stats = tracker.get_project_stats("/test/project")
        assert stats.budget_monthly == 100_000
        assert stats.budget_used_pct > 0

    def test_daily_usage(self, tracker):
        daily = tracker.get_daily_usage("/test/project", days=7)
        assert len(daily) == 7
        # Only today should have data
        days_with_data = [d for d in daily if d.record_count > 0]
        assert len(days_with_data) == 1
        assert days_with_data[0].record_count == 5

    def test_daily_usage_models_breakdown(self, tracker):
        daily = tracker.get_daily_usage("/test/project", days=1)
        today = daily[0]
        assert "gpt-4o" in today.models
        assert "claude-3.5-sonnet" in today.models

    def test_daily_usage_performers_breakdown(self, tracker):
        daily = tracker.get_daily_usage("/test/project", days=1)
        today = daily[0]
        assert "claude" in today.performers
        assert "opencode" in today.performers

    def test_daily_usage_no_data(self, tracker):
        daily = tracker.get_daily_usage("/empty/project", days=3)
        assert all(d.record_count == 0 for d in daily)

    def test_top_projects(self, tracker):
        tracker.record(project_path="/other/project", performer="claude", tokens_in=100)
        top = tracker.get_top_projects(limit=5)
        assert len(top) >= 2
        # The one with more tokens should be first
        assert top[0].total_tokens >= top[1].total_tokens

    def test_top_projects_empty(self, tmp_path):
        empty_tracker = TokenTrackerService(data_dir=tmp_path)
        top = empty_tracker.get_top_projects()
        assert top == []


# ============================================================================
# Integration: full workflow
# ============================================================================

class TestTokenTrackerIntegration:

    @pytest.fixture
    def tracker(self, tmp_path):
        return TokenTrackerService(data_dir=tmp_path)

    def test_full_workflow(self, tracker):
        """Set budget → record usage → check alert → get stats."""
        # 1. Set budget
        tracker.set_budget("/my/project", monthly_token_limit=50_000)

        # 2. Record multiple sessions
        tracker.record(
            project_path="/my/project", performer="claude",
            tokens_in=5000, tokens_out=3000, model="gpt-4o", operation="chat",
        )
        tracker.record(
            project_path="/my/project", performer="opencode",
            tokens_in=8000, tokens_out=4000, model="claude-3.5-sonnet", operation="resume",
        )
        tracker.record(
            project_path="/my/project", performer="claude",
            tokens_in=10000, tokens_out=5000, model="gpt-4o", operation="checkpoint",
        )

        # 3. Check remaining
        remaining = tracker.get_remaining_budget("/my/project")
        # total = (5+3) + (8+4) + (10+5) = 35K
        assert remaining == 15_000

        # 4. Get stats
        stats = tracker.get_project_stats("/my/project")
        assert stats.total_records == 3
        assert stats.total_tokens == 35_000
        assert stats.by_performer["claude"] == 23_000
        assert stats.by_performer["opencode"] == 12_000

        # 5. Daily usage
        daily = tracker.get_daily_usage("/my/project", days=1)
        assert daily[0].tokens_total == 35_000

    def test_multi_project_isolation(self, tracker):
        """Records from one project don't affect another."""
        tracker.record(project_path="/project/a", performer="claude", tokens_in=1000)
        tracker.record(project_path="/project/b", performer="opencode", tokens_in=5000)

        stats_a = tracker.get_project_stats("/project/a")
        stats_b = tracker.get_project_stats("/project/b")

        assert stats_a.total_tokens == 1000
        assert stats_b.total_tokens == 5000
