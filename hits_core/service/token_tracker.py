"""Token budget tracking and cost analytics.

Tracks token usage across sessions, tools, and models.
Supports per-project budgets, cost estimation, and usage analytics.

Usage:
    tracker = TokenTrackerService()

    # Record usage
    tracker.record(project_path="/project", performer="claude",
                   model="gpt-4o", tokens_in=500, tokens_out=200)

    # Set budget
    tracker.set_budget(project_path="/project", monthly_tokens=1_000_000)

    # Check budget
    remaining = tracker.get_remaining_budget("/project")

    # Analytics
    stats = tracker.get_project_stats("/project")
    daily = tracker.get_daily_usage("/project", days=7)
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field, ConfigDict


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class TokenRecord(BaseModel):
    """A single token usage record."""
    model_config = ConfigDict(use_enum_values=True, extra="ignore")

    id: str = Field(default_factory=lambda: f"tr_{uuid4().hex[:8]}")
    project_path: str = Field(default="")
    performer: str = Field(default="", description="claude/opencode/cursor/etc")
    session_id: Optional[str] = Field(default=None)

    # Token counts
    tokens_in: int = Field(default=0, description="Prompt/input tokens")
    tokens_out: int = Field(default=0, description="Completion/output tokens")
    tokens_total: int = Field(default=0, description="Total tokens (in + out)")

    # Model info
    model: Optional[str] = Field(default=None, description="gpt-4o, claude-3.5-sonnet, etc")

    # Cost
    estimated_cost_usd: float = Field(default=0.0, description="Estimated cost in USD")

    # Context
    operation: Optional[str] = Field(default=None, description="resume, checkpoint, chat, etc")
    tags: list[str] = Field(default_factory=list)

    recorded_at: datetime = Field(default_factory=datetime.now)


class TokenBudget(BaseModel):
    """Token budget configuration for a project."""
    model_config = ConfigDict(use_enum_values=True)

    project_path: str = Field(...)
    monthly_token_limit: int = Field(default=0, description="0 = unlimited")
    daily_token_limit: int = Field(default=0, description="0 = unlimited")
    alert_threshold_pct: float = Field(default=80.0, description="Alert when usage reaches this %")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class DailyUsage(BaseModel):
    """Aggregated token usage for a single day."""
    date: str = Field(..., description="YYYY-MM-DD")
    tokens_in: int = Field(default=0)
    tokens_out: int = Field(default=0)
    tokens_total: int = Field(default=0)
    estimated_cost_usd: float = Field(default=0.0)
    record_count: int = Field(default=0)
    models: dict[str, int] = Field(default_factory=dict, description="Model → token count")
    performers: dict[str, int] = Field(default_factory=dict, description="Tool → token count")


class ProjectTokenStats(BaseModel):
    """Aggregated token statistics for a project."""
    project_path: str = Field(...)
    project_name: str = Field(default="")

    # Totals
    total_records: int = Field(default=0)
    total_tokens_in: int = Field(default=0)
    total_tokens_out: int = Field(default=0)
    total_tokens: int = Field(default=0)
    total_cost_usd: float = Field(default=0.0)

    # Averages
    avg_tokens_per_record: float = Field(default=0.0)
    avg_tokens_per_day: float = Field(default=0.0)

    # Breakdown
    by_performer: dict[str, int] = Field(default_factory=dict)
    by_model: dict[str, int] = Field(default_factory=dict)
    by_operation: dict[str, int] = Field(default_factory=dict)

    # Budget
    budget_monthly: int = Field(default=0)
    budget_used_pct: float = Field(default=0.0)
    budget_remaining: int = Field(default=0)

    # Time range
    first_record: Optional[str] = Field(default=None)
    last_record: Optional[str] = Field(default=None)
    active_days: int = Field(default=0)


# ---------------------------------------------------------------------------
# Cost constants (per 1K tokens, approximate as of 2025)
# ---------------------------------------------------------------------------

MODEL_COSTS_PER_1K = {
    # OpenAI
    "gpt-4o": {"in": 0.0025, "out": 0.01},
    "gpt-4o-mini": {"in": 0.00015, "out": 0.0006},
    "gpt-4-turbo": {"in": 0.01, "out": 0.03},
    "gpt-3.5-turbo": {"in": 0.0005, "out": 0.0015},
    # Anthropic
    "claude-3.5-sonnet": {"in": 0.003, "out": 0.015},
    "claude-3.5-haiku": {"in": 0.0008, "out": 0.004},
    "claude-3-opus": {"in": 0.015, "out": 0.075},
    "claude-3-sonnet": {"in": 0.003, "out": 0.015},
    "claude-3-haiku": {"in": 0.00025, "out": 0.00125},
    # Local / unknown
    "local": {"in": 0.0, "out": 0.0},
    "unknown": {"in": 0.0, "out": 0.0},
}


def estimate_cost(model: Optional[str], tokens_in: int, tokens_out: int) -> float:
    """Estimate cost in USD based on model and token counts."""
    if not model:
        return 0.0

    model_lower = model.lower()
    costs = MODEL_COSTS_PER_1K.get(model_lower)

    # Try partial match
    if costs is None:
        for key, val in MODEL_COSTS_PER_1K.items():
            if key in model_lower:
                costs = val
                break

    if costs is None:
        costs = MODEL_COSTS_PER_1K.get("unknown", {"in": 0.0, "out": 0.0})

    return (tokens_in / 1000 * costs["in"]) + (tokens_out / 1000 * costs["out"])


# ---------------------------------------------------------------------------
# TokenTrackerService
# ---------------------------------------------------------------------------

class TokenTrackerService:
    """Track token usage across projects with budget management.

    Storage:
        ~/.hits/data/token_tracking/
        ├── records/{date}.jsonl        ← daily record files
        ├── budgets/{project_key}.json   ← per-project budgets
        └── stats_cache.json             ← cached aggregates
    """

    TRACKING_DIR = "token_tracking"

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            data_dir = Path.home() / ".hits" / "data"
        self._base = data_dir / self.TRACKING_DIR
        self._records_dir = self._base / "records"
        self._budgets_dir = self._base / "budgets"
        self._records_dir.mkdir(parents=True, exist_ok=True)
        self._budgets_dir.mkdir(parents=True, exist_ok=True)

    def _project_key(self, project_path: str) -> str:
        return project_path.replace("/", "_").strip("_")

    # -----------------------------------------------------------------------
    # Record
    # -----------------------------------------------------------------------

    def record(
        self,
        project_path: str = "",
        performer: str = "",
        tokens_in: int = 0,
        tokens_out: int = 0,
        model: Optional[str] = None,
        operation: Optional[str] = None,
        session_id: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> TokenRecord:
        """Record a token usage event."""
        tokens_total = tokens_in + tokens_out
        cost = estimate_cost(model, tokens_in, tokens_out)

        rec = TokenRecord(
            project_path=project_path,
            performer=performer,
            session_id=session_id,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            tokens_total=tokens_total,
            model=model,
            estimated_cost_usd=cost,
            operation=operation,
            tags=tags or [],
        )

        # Append to daily file
        date_str = datetime.now().strftime("%Y-%m-%d")
        record_file = self._records_dir / f"{date_str}.jsonl"
        with open(record_file, "a", encoding="utf-8") as f:
            f.write(rec.model_dump_json() + "\n")

        return rec

    # -----------------------------------------------------------------------
    # Budget
    # -----------------------------------------------------------------------

    def set_budget(
        self,
        project_path: str,
        monthly_token_limit: int = 0,
        daily_token_limit: int = 0,
        alert_threshold_pct: float = 80.0,
    ) -> TokenBudget:
        """Set or update token budget for a project."""
        key = self._project_key(project_path)
        budget = TokenBudget(
            project_path=project_path,
            monthly_token_limit=monthly_token_limit,
            daily_token_limit=daily_token_limit,
            alert_threshold_pct=alert_threshold_pct,
        )
        path = self._budgets_dir / f"{key}.json"
        path.write_text(budget.model_dump_json(indent=2), encoding="utf-8")
        return budget

    def get_budget(self, project_path: str) -> Optional[TokenBudget]:
        """Get budget configuration for a project."""
        key = self._project_key(project_path)
        path = self._budgets_dir / f"{key}.json"
        if not path.exists():
            return None
        try:
            return TokenBudget.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def get_remaining_budget(self, project_path: str) -> Optional[int]:
        """Get remaining monthly budget. Returns None if no budget set."""
        budget = self.get_budget(project_path)
        if budget is None or budget.monthly_token_limit == 0:
            return None  # unlimited

        stats = self.get_project_stats(project_path)
        now = datetime.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Calculate this month's usage
        monthly_usage = self._get_usage_in_range(
            project_path,
            since=month_start,
        )
        return max(0, budget.monthly_token_limit - monthly_usage)

    def check_budget_alert(self, project_path: str) -> Optional[str]:
        """Check if budget usage exceeds alert threshold. Returns alert message or None."""
        budget = self.get_budget(project_path)
        if budget is None or budget.monthly_token_limit == 0:
            return None

        now = datetime.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_usage = self._get_usage_in_range(project_path, since=month_start)

        pct = (monthly_usage / budget.monthly_token_limit) * 100
        if pct >= budget.alert_threshold_pct:
            return (
                f"⚠ Token budget alert: {pct:.1f}% used "
                f"({monthly_usage:,} / {budget.monthly_token_limit:,} tokens)"
            )
        return None

    # -----------------------------------------------------------------------
    # Analytics
    # -----------------------------------------------------------------------

    def get_project_stats(self, project_path: str) -> ProjectTokenStats:
        """Get aggregated token statistics for a project."""
        stats = ProjectTokenStats(
            project_path=project_path,
            project_name=Path(project_path).name if project_path else "",
        )

        records = self._load_records(project_path=project_path)
        if not records:
            return stats

        stats.total_records = len(records)
        stats.total_tokens_in = sum(r.tokens_in for r in records)
        stats.total_tokens_out = sum(r.tokens_out for r in records)
        stats.total_tokens = sum(r.tokens_total for r in records)
        stats.total_cost_usd = round(sum(r.estimated_cost_usd for r in records), 4)
        stats.avg_tokens_per_record = round(stats.total_tokens / len(records), 1)

        # Breakdown
        by_performer: dict[str, int] = {}
        by_model: dict[str, int] = {}
        by_operation: dict[str, int] = {}

        for r in records:
            if r.performer:
                by_performer[r.performer] = by_performer.get(r.performer, 0) + r.tokens_total
            if r.model:
                by_model[r.model] = by_model.get(r.model, 0) + r.tokens_total
            if r.operation:
                by_operation[r.operation] = by_operation.get(r.operation, 0) + r.tokens_total

        stats.by_performer = by_performer
        stats.by_model = by_model
        stats.by_operation = by_operation

        # Time range
        stats.first_record = records[0].recorded_at.isoformat()
        stats.last_record = records[-1].recorded_at.isoformat()

        # Active days
        days = {r.recorded_at.strftime("%Y-%m-%d") for r in records}
        stats.active_days = len(days)
        stats.avg_tokens_per_day = round(stats.total_tokens / max(len(days), 1), 1)

        # Budget info
        budget = self.get_budget(project_path)
        if budget and budget.monthly_token_limit > 0:
            stats.budget_monthly = budget.monthly_token_limit
            stats.budget_used_pct = round(
                (stats.total_tokens / budget.monthly_token_limit) * 100, 1
            )
            stats.budget_remaining = max(0, budget.monthly_token_limit - stats.total_tokens)

        return stats

    def get_daily_usage(
        self,
        project_path: str = "",
        days: int = 7,
    ) -> list[DailyUsage]:
        """Get daily aggregated usage for the last N days."""
        now = datetime.now()
        result = []

        for i in range(days - 1, -1, -1):
            date = now - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            daily = DailyUsage(date=date_str)

            records = self._load_records(
                project_path=project_path,
                date_filter=date_str,
            )

            for r in records:
                daily.tokens_in += r.tokens_in
                daily.tokens_out += r.tokens_out
                daily.tokens_total += r.tokens_total
                daily.estimated_cost_usd += r.estimated_cost_usd
                daily.record_count += 1

                if r.model:
                    daily.models[r.model] = daily.models.get(r.model, 0) + r.tokens_total
                if r.performer:
                    daily.performers[r.performer] = daily.performers.get(r.performer, 0) + r.tokens_total

            daily.estimated_cost_usd = round(daily.estimated_cost_usd, 4)
            result.append(daily)

        return result

    def get_top_projects(self, limit: int = 10) -> list[ProjectTokenStats]:
        """Get top projects by total token usage."""
        # Collect all project paths from records
        project_paths: set[str] = set()
        for record_file in self._records_dir.glob("*.jsonl"):
            for line in record_file.read_text(encoding="utf-8").strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    rec = TokenRecord.model_validate_json(line)
                    if rec.project_path:
                        project_paths.add(rec.project_path)
                except Exception:
                    continue

        # Get stats for each
        all_stats = []
        for path in project_paths:
            all_stats.append(self.get_project_stats(path))

        all_stats.sort(key=lambda s: s.total_tokens, reverse=True)
        return all_stats[:limit]

    # -----------------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------------

    def _load_records(
        self,
        project_path: str = "",
        date_filter: Optional[str] = None,
    ) -> list[TokenRecord]:
        """Load token records from JSONL files."""
        records = []

        if date_filter:
            files = [self._records_dir / f"{date_filter}.jsonl"]
        else:
            files = sorted(self._records_dir.glob("*.jsonl"))

        for record_file in files:
            if not record_file.exists():
                continue
            for line in record_file.read_text(encoding="utf-8").strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    rec = TokenRecord.model_validate_json(line)
                    if project_path and rec.project_path != project_path:
                        continue
                    records.append(rec)
                except Exception:
                    continue

        records.sort(key=lambda r: r.recorded_at)
        return records

    def _get_usage_in_range(
        self,
        project_path: str,
        since: datetime,
    ) -> int:
        """Get total tokens used since a given datetime."""
        records = self._load_records(project_path=project_path)
        return sum(r.tokens_total for r in records if r.recorded_at >= since)
