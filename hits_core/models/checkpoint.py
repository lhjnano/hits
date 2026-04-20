"""Checkpoint model - structured, actionable session snapshots.

Unlike handover summaries (which are informational), checkpoints are
executable: they contain everything needed to immediately resume work.

Key design principles:
- Actionable: every field answers "what do I do next?"
- Token-efficient: structured for compression, not prose
- Diff-aware: tracks file changes as deltas, not full content
- Priority-ordered: most important items first for token budget
"""

from enum import Enum
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class StepPriority(str, Enum):
    CRITICAL = "critical"  # Must do next, blocks all other work
    HIGH = "high"          # Should do next
    MEDIUM = "medium"      # Should do soon
    LOW = "low"            # Can defer


class ChangeType(str, Enum):
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


class NextStep(BaseModel):
    """A single actionable next step."""
    action: str = Field(..., description="What to do (imperative verb)")
    command: Optional[str] = Field(default=None, description="Shell command to run (if applicable)")
    file: Optional[str] = Field(default=None, description="Primary file to edit")
    priority: StepPriority = Field(default=StepPriority.MEDIUM)
    context: Optional[str] = Field(default=None, description="Why this step is needed")
    estimated_tokens: Optional[int] = Field(default=None, description="Estimated tokens needed")


class FileDelta(BaseModel):
    """A file change record."""
    path: str = Field(..., description="File path relative to project root")
    change_type: ChangeType = Field(default=ChangeType.MODIFIED)
    description: Optional[str] = Field(default=None, description="What changed (1 line)")
    lines_added: Optional[int] = Field(default=None)
    lines_removed: Optional[int] = Field(default=None)


class Block(BaseModel):
    """A blocker preventing progress."""
    issue: str = Field(..., description="What's blocking")
    workaround: Optional[str] = Field(default=None, description="Known workaround")
    severity: str = Field(default="medium")  # critical | medium | low


class Decision(BaseModel):
    """A decision made during the session."""
    decision: str = Field(..., description="What was decided")
    rationale: Optional[str] = Field(default=None, description="Why")
    alternatives_rejected: list[str] = Field(default_factory=list)


class Checkpoint(BaseModel):
    """Structured, actionable session checkpoint.

    This is the evolution of HandoverSummary - instead of a passive summary,
    it's an executable snapshot that the next AI session can immediately act on.
    """
    model_config = ConfigDict(use_enum_values=True)

    # Identity
    id: str = Field(..., description="Unique checkpoint ID (cp_xxxxxxxx)")
    project_path: str = Field(..., description="Project absolute path")
    project_name: str = Field(default="", description="Human-readable project name")
    performer: str = Field(..., description="Who created this checkpoint (claude/opencode/etc)")
    created_at: datetime = Field(default_factory=datetime.now)

    # Git context
    git_branch: Optional[str] = Field(default=None)
    git_status: Optional[str] = Field(default=None)
    git_last_commit: Optional[str] = Field(default=None)

    # Core: Purpose & State
    purpose: str = Field(..., description="What this session was trying to accomplish")
    current_state: str = Field(default="", description="What was actually achieved")
    completion_pct: int = Field(default=0, ge=0, le=100, description="Estimated completion percentage")

    # Actionable next steps (priority-ordered)
    next_steps: list[NextStep] = Field(default_factory=list)

    # Context the next session MUST know
    required_context: list[str] = Field(default_factory=list, description="Critical facts for next session")

    # File changes
    files_delta: list[FileDelta] = Field(default_factory=list)

    # Decisions made
    decisions_made: list[Decision] = Field(default_factory=list)

    # Blockers
    blocks: list[Block] = Field(default_factory=list)

    # Commands that were run (for reproducibility)
    commands_run: list[str] = Field(default_factory=list)

    # Auto-generated resume command
    resume_command: str = Field(default="", description="Command to resume this project")

    # Token budget info
    total_tokens_estimate: Optional[int] = Field(default=None)
    compressed_tokens_estimate: Optional[int] = Field(default=None)

    # Link to work logs that generated this checkpoint
    source_log_ids: list[str] = Field(default_factory=list)

    # Parent checkpoint (for chaining)
    parent_checkpoint_id: Optional[str] = Field(default=None)

    def to_text(self) -> str:
        """Generate token-efficient text representation for AI context.

        Format: structured YAML-like, not prose.
        Optimized for token efficiency while preserving actionability.
        """
        lines = []

        # Header (minimal)
        lines.append(f"## CHECKPOINT: {self.project_name}")
        lines.append(f"path: {self.project_path}")
        if self.git_branch:
            lines.append(f"git: {self.git_branch} ({self.git_status or '?'})")
        lines.append(f"by: {self.performer} @ {self.created_at.strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"progress: {self.completion_pct}%")
        lines.append("")

        # Purpose (always present)
        lines.append("### PURPOSE")
        lines.append(self.purpose)
        lines.append("")

        # Current state
        if self.current_state:
            lines.append("### ACHIEVED")
            lines.append(self.current_state)
            lines.append("")

        # Next steps (most important - actionable)
        if self.next_steps:
            lines.append("### NEXT STEPS")
            for i, step in enumerate(self.next_steps, 1):
                priority_marker = {"critical": "🔴", "high": "🟡", "medium": "🟢", "low": "⚪"}.get(step.priority, "·")
                line = f"{i}. {priority_marker} {step.action}"
                if step.command:
                    line += f"\n   → `{step.command}`"
                if step.file:
                    line += f"\n   📄 {step.file}"
                if step.context:
                    line += f"\n   💡 {step.context}"
                lines.append(line)
            lines.append("")

        # Required context (must-know)
        if self.required_context:
            lines.append("### MUST KNOW")
            for ctx in self.required_context:
                lines.append(f"  • {ctx}")
            lines.append("")

        # Decisions
        if self.decisions_made:
            lines.append("### DECISIONS")
            for d in self.decisions_made:
                line = f"  ★ {d.decision}"
                if d.rationale:
                    line += f" → {d.rationale}"
                lines.append(line)
            lines.append("")

        # Blocks
        if self.blocks:
            lines.append("### BLOCKERS")
            for b in self.blocks:
                icon = {"critical": "🚫", "medium": "⚠️", "low": "ℹ️"}.get(b.severity, "⚠️")
                line = f"  {icon} {b.issue}"
                if b.workaround:
                    line += f" → workaround: {b.workaround}"
                lines.append(line)
            lines.append("")

        # File deltas (compact)
        if self.files_delta:
            lines.append("### FILES")
            for fd in self.files_delta:
                icon = {"created": "+", "modified": "~", "deleted": "-", "renamed": "→"}.get(fd.change_type, "?")
                line = f"  [{icon}] {fd.path}"
                if fd.description:
                    line += f" — {fd.description}"
                lines.append(line)
            lines.append("")

        # Resume command
        if self.resume_command:
            lines.append(f"### RESUME")
            lines.append(f"```bash")
            lines.append(self.resume_command)
            lines.append("```")

        return "\n".join(lines)

    def to_compact(self, token_budget: int = 2000) -> str:
        """Generate compressed representation within token budget.

        Uses priority-based field selection: drops low-priority items first.
        Approximately 4 chars = 1 token for English, 2 chars = 1 token for Korean.
        """
        result = self.to_text()
        estimated_tokens = len(result) // 3  # rough estimate

        if estimated_tokens <= token_budget:
            return result

        # Progressive compression: drop fields from lowest priority
        # Strategy: keep PURPOSE + NEXT_STEPS + MUST_KNOW, drop the rest
        lines = []
        lines.append(f"## CHECKPOINT: {self.project_name} ({self.completion_pct}%)")
        lines.append(f"git: {self.git_branch} | by: {self.performer}")
        lines.append("")

        # Always keep purpose (truncated if needed)
        lines.append("PURPOSE: " + self.purpose[:200])
        lines.append("")

        # Next steps - only critical and high
        critical_steps = [s for s in self.next_steps if s.priority in ("critical", "high")]
        if critical_steps:
            lines.append("NEXT:")
            for i, step in enumerate(critical_steps, 1):
                line = f"  {i}. {step.action}"
                if step.command:
                    line += f" → {step.command}"
                if step.file:
                    line += f" ({step.file})"
                lines.append(line)
            lines.append("")

        # Must-know context
        if self.required_context:
            lines.append("MUST KNOW:")
            for ctx in self.required_context[:5]:
                lines.append(f"  • {ctx[:100]}")
            lines.append("")

        # Blocks (only critical)
        critical_blocks = [b for b in self.blocks if b.severity == "critical"]
        if critical_blocks:
            lines.append("BLOCKED:")
            for b in critical_blocks:
                lines.append(f"  🚫 {b.issue[:100]}")

        return "\n".join(lines)
