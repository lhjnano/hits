"""Token-aware compression for checkpoint data.

Unlike the basic SemanticCompressor (keyword → symbol replacement),
this compressor preserves STRUCTURE while minimizing tokens.

Design:
1. Estimate tokens per field (Korean ~2 char/token, English ~4 char/token)
2. Priority-based field pruning when over budget
3. Progressive compression levels:
   - L0: Full structured (all fields)
   - L1: Drop low-priority steps + truncate descriptions
   - L2: Only critical info (purpose + critical steps + must-know)
   - L3: Ultra-compact (single paragraph summary)
"""

from typing import Optional
from ..models.checkpoint import Checkpoint, NextStep, StepPriority


class CheckpointCompressor:
    """Token-aware compressor that preserves actionability."""

    # Token estimation constants
    # Korean: ~2 chars per token, English: ~4 chars per token, Mixed: ~3
    CHARS_PER_TOKEN_KR = 2.0
    CHARS_PER_TOKEN_EN = 4.0
    CHARS_PER_TOKEN_MIXED = 3.0

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        if not text:
            return 0

        korean_chars = sum(1 for c in text if '\uAC00' <= c <= '\uD7A3')
        total_chars = len(text)
        non_korean = total_chars - korean_chars

        kr_tokens = korean_chars / self.CHARS_PER_TOKEN_KR
        en_tokens = non_korean / self.CHARS_PER_TOKEN_EN

        return int(kr_tokens + en_tokens)

    def compress_checkpoint(
        self,
        checkpoint: Checkpoint,
        token_budget: int = 2000,
    ) -> str:
        """Compress checkpoint to fit within token budget.

        Uses progressive compression levels:
        - If fits: full structured output
        - If over budget: progressively strip fields

        Returns compressed string that fits within budget.
        """
        # Try full output first
        full_text = checkpoint.to_text()
        if self.estimate_tokens(full_text) <= token_budget:
            return full_text

        # L1: Drop low-priority steps, truncate descriptions
        l1_text = self._compress_l1(checkpoint)
        if self.estimate_tokens(l1_text) <= token_budget:
            return l1_text

        # L2: Only critical info
        l2_text = self._compress_l2(checkpoint)
        if self.estimate_tokens(l2_text) <= token_budget:
            return l2_text

        # L3: Ultra-compact
        return self._compress_l3(checkpoint)

    def _compress_l1(self, cp: Checkpoint) -> str:
        """Level 1: Drop low-priority items, truncate descriptions."""
        lines = []

        lines.append(f"## {cp.project_name} ({cp.completion_pct}%)")
        lines.append(f"path: {cp.project_path}")
        if cp.git_branch:
            lines.append(f"git: {cp.git_branch}")
        lines.append(f"by: {cp.performer}")
        lines.append("")

        lines.append("PURPOSE: " + cp.purpose[:200])
        if cp.current_state:
            lines.append("STATE: " + cp.current_state[:150])
        lines.append("")

        # Only medium+ priority steps
        important_steps = [s for s in cp.next_steps if s.priority in ("critical", "high", "medium")]
        if important_steps:
            lines.append("NEXT:")
            for i, step in enumerate(important_steps[:5], 1):
                icon = {"critical": "🔴", "high": "🟡", "medium": "🟢"}.get(step.priority, "·")
                line = f"  {i}. {icon} {step.action[:100]}"
                if step.command:
                    line += f" → {step.command[:80]}"
                if step.file:
                    line += f" ({step.file})"
                lines.append(line)
            lines.append("")

        if cp.required_context:
            lines.append("MUST KNOW:")
            for ctx in cp.required_context[:4]:
                lines.append(f"  • {ctx[:120]}")
            lines.append("")

        if cp.blocks:
            lines.append("BLOCKED:")
            for b in cp.blocks[:2]:
                lines.append(f"  ⚠ {b.issue[:100]}")
            lines.append("")

        # Files: just paths
        if cp.files_delta:
            paths = [fd.path for fd in cp.files_delta[:10]]
            lines.append("FILES: " + ", ".join(paths))

        return "\n".join(lines)

    def _compress_l2(self, cp: Checkpoint) -> str:
        """Level 2: Only critical/high info."""
        lines = []

        lines.append(f"## {cp.project_name} ({cp.completion_pct}%) [{cp.performer}]")
        if cp.git_branch:
            lines.append(f"git: {cp.git_branch}")
        lines.append("")

        lines.append("PURPOSE: " + cp.purpose[:150])
        lines.append("")

        # Only critical and high priority steps
        critical_steps = [s for s in cp.next_steps if s.priority in ("critical", "high")]
        if critical_steps:
            lines.append("MUST DO:")
            for i, step in enumerate(critical_steps[:3], 1):
                line = f"  {i}. {step.action[:80]}"
                if step.command:
                    line += f" → {step.command[:60]}"
                lines.append(line)
            lines.append("")

        if cp.required_context:
            lines.append("CONTEXT:")
            for ctx in cp.required_context[:3]:
                lines.append(f"  • {ctx[:80]}")
            lines.append("")

        # Critical blocks only
        critical_blocks = [b for b in cp.blocks if b.severity in ("critical",)]
        if critical_blocks:
            lines.append("BLOCKED:")
            for b in critical_blocks:
                lines.append(f"  🚫 {b.issue[:80]}")

        return "\n".join(lines)

    def _compress_l3(self, cp: Checkpoint) -> str:
        """Level 3: Ultra-compact single paragraph."""
        parts = [f"[{cp.project_name} {cp.completion_pct}%]"]

        parts.append(f"Purpose: {cp.purpose[:100]}")

        if cp.next_steps:
            critical = [s for s in cp.next_steps if s.priority in ("critical", "high")]
            if critical:
                next_actions = "; ".join(s.action[:50] for s in critical[:2])
                parts.append(f"Next: {next_actions}")

        if cp.required_context:
            parts.append(f"Note: {cp.required_context[0][:80]}")

        if cp.blocks:
            parts.append(f"Blocked: {cp.blocks[0].issue[:60]}")

        return " | ".join(parts)

    def estimate_checkpoint_tokens(self, checkpoint: Checkpoint) -> dict:
        """Estimate token usage for a checkpoint at each compression level."""
        full = checkpoint.to_text()
        return {
            "full": self.estimate_tokens(full),
            "l1": self.estimate_tokens(self._compress_l1(checkpoint)),
            "l2": self.estimate_tokens(self._compress_l2(checkpoint)),
            "l3": self.estimate_tokens(self._compress_l3(checkpoint)),
            "field_breakdown": {
                "purpose": self.estimate_tokens(checkpoint.purpose),
                "current_state": self.estimate_tokens(checkpoint.current_state),
                "next_steps": sum(self.estimate_tokens(s.action) for s in checkpoint.next_steps),
                "required_context": sum(self.estimate_tokens(c) for c in checkpoint.required_context),
                "decisions": sum(self.estimate_tokens(d.decision) for d in checkpoint.decisions_made),
                "blocks": sum(self.estimate_tokens(b.issue) for b in checkpoint.blocks),
            },
        }
