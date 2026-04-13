"""Signal service for cross-tool handover via file-based signals.

Signal directory layout:
    ~/.hits/signals/
    ├── pending/       ← Active signals waiting to be consumed
    └── consumed/      ← Processed signals (archive)

Signal filename format:
    {sender}_to_{recipient}_{timestamp}_{id}.json
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from ..models.signal import HandoverSignal, SignalStatus, SignalType, VALID_PERFORMERS


class SignalService:
    SIGNALS_DIR_NAME = "signals"
    PENDING_DIR = "pending"
    CONSUMED_DIR = "consumed"

    def __init__(self, data_path: Optional[str] = None):
        if data_path:
            base = Path(data_path)
        else:
            env_path = os.environ.get("HITS_DATA_PATH")
            if env_path:
                base = Path(env_path)
            else:
                base = Path.home() / ".hits" / "data"

        self.signals_dir = base / self.SIGNALS_DIR_NAME
        self.pending_dir = self.signals_dir / self.PENDING_DIR
        self.consumed_dir = self.signals_dir / self.CONSUMED_DIR

        self.pending_dir.mkdir(parents=True, exist_ok=True)
        self.consumed_dir.mkdir(parents=True, exist_ok=True)

    # ─── Send (create signal) ──────────────────────────────────

    async def send_signal(
        self,
        sender: str,
        recipient: str = "any",
        signal_type: str = "session_end",
        project_path: Optional[str] = None,
        summary: str = "",
        context: Optional[str] = None,
        pending_items: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
        priority: str = "normal",
        handover_available: bool = True,
    ) -> HandoverSignal:
        """Create a new signal in pending/ directory."""

        sender = sender.lower().strip()
        recipient = recipient.lower().strip()

        if sender not in VALID_PERFORMERS:
            sender = "unknown"
        if recipient not in VALID_PERFORMERS and recipient != "any":
            recipient = "any"

        signal = HandoverSignal(
            id=f"sig_{uuid4().hex[:8]}",
            sender=sender,
            recipient=recipient,
            signal_type=signal_type,
            project_path=project_path,
            summary=summary,
            context=context,
            pending_items=pending_items or [],
            tags=tags or [],
            priority=priority,
            handover_available=handover_available,
        )

        path = self.pending_dir / signal.filename()
        with open(path, "w", encoding="utf-8") as f:
            f.write(signal.model_dump_json(indent=2))

        return signal

    # ─── Check (list pending signals) ──────────────────────────

    async def check_signals(
        self,
        recipient: str = "any",
        project_path: Optional[str] = None,
        limit: int = 10,
    ) -> list[HandoverSignal]:
        """Return pending signals addressed to recipient."""
        recipient = recipient.lower().strip()
        signals: list[HandoverSignal] = []

        for path in sorted(self.pending_dir.glob("*.json")):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                signal = HandoverSignal.model_validate(data)

                # Skip consumed/expired
                if signal.status != SignalStatus.PENDING:
                    continue
                if signal.is_expired():
                    # Auto-move to consumed
                    await self._move_to_consumed(path, signal, expired=True)
                    continue

                # Filter: recipient matches 'any' or specific
                if recipient != "any" and signal.recipient != "any" and signal.recipient != recipient:
                    continue

                # Filter by project
                if project_path and signal.project_path != project_path:
                    continue

                signals.append(signal)

                if len(signals) >= limit:
                    break
            except Exception:
                continue

        # Sort by priority (urgent > high > normal), then by time
        priority_order = {"urgent": 0, "high": 1, "normal": 2}
        signals.sort(
            key=lambda s: (priority_order.get(s.priority, 2), s.created_at),
        )

        return signals

    # ─── Consume (mark signal as consumed) ─────────────────────

    async def consume_signal(
        self,
        signal_id: str,
        consumed_by: str,
    ) -> Optional[HandoverSignal]:
        """Mark a signal as consumed and move to archive."""
        for path in self.pending_dir.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                signal = HandoverSignal.model_validate(data)

                if signal.id == signal_id:
                    return await self._move_to_consumed(path, signal, consumed_by=consumed_by)
            except Exception:
                continue

        return None

    # ─── Internal ──────────────────────────────────────────────

    async def _move_to_consumed(
        self,
        path: Path,
        signal: HandoverSignal,
        consumed_by: Optional[str] = None,
        expired: bool = False,
    ) -> HandoverSignal:
        if expired:
            signal.status = SignalStatus.EXPIRED
        else:
            signal.status = SignalStatus.CONSUMED
            signal.consumed_at = datetime.now()
            signal.consumed_by = consumed_by

        # Write updated signal to consumed dir
        consumed_path = self.consumed_dir / signal.filename()
        with open(consumed_path, "w", encoding="utf-8") as f:
            f.write(signal.model_dump_json(indent=2))

        # Remove from pending
        if path.exists():
            path.unlink()

        return signal

    # ─── Cleanup ───────────────────────────────────────────────

    async def cleanup_consumed(self, max_age_hours: int = 72) -> int:
        """Remove consumed signals older than max_age_hours."""
        count = 0
        cutoff = datetime.now().timestamp() - (max_age_hours * 3600)

        for path in self.consumed_dir.glob("*.json"):
            if path.stat().st_mtime < cutoff:
                path.unlink()
                count += 1

        return count
