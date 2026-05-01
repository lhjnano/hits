"""WebSocket event bus for real-time UI updates.

Provides a centralized event bus that broadcasts state changes to
all connected WebSocket clients. Any part of the backend can publish
events (checkpoint created, signal received, work log added, etc.)
and all connected browser tabs receive them instantly.

Architecture:
    EventBus (singleton)
    ├── publish(event)         → broadcast to all subscribers
    ├── subscribe(websocket)   → add a client
    ├── unsubscribe(websocket) → remove a client
    └── get_history()          → recent events for reconnecting clients

    WebSocket endpoint:
    /api/ws/events → upgraded to WebSocket, receives live events

Event types:
    - checkpoint_created
    - checkpoint_updated
    - signal_received
    - signal_consumed
    - work_log_created
    - work_log_updated
    - workflow_stage_started
    - workflow_stage_completed
    - workflow_completed
    - token_usage_updated
    - project_selected
"""

import asyncio
import json
from datetime import datetime
from typing import Optional
from collections import deque
from pydantic import BaseModel, Field, ConfigDict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect


# ---------------------------------------------------------------------------
# Event model
# ---------------------------------------------------------------------------

class LiveEvent(BaseModel):
    """A single real-time event."""
    model_config = ConfigDict(use_enum_values=True)

    type: str = Field(..., description="Event type (checkpoint_created, signal_received, etc)")
    data: dict = Field(default_factory=dict, description="Event payload")
    project_path: Optional[str] = Field(default=None)
    performer: Optional[str] = Field(default=None)
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


# ---------------------------------------------------------------------------
# EventBus (singleton)
# ---------------------------------------------------------------------------

class EventBus:
    """In-process pub/sub event bus for WebSocket broadcasting.

    Thread-safe via asyncio. Maintains a ring buffer of recent events
    so reconnecting clients can catch up.
    """

    MAX_HISTORY = 100

    def __init__(self):
        self._subscribers: list[WebSocket] = []
        self._history: deque[LiveEvent] = deque(maxlen=self.MAX_HISTORY)
        self._lock = asyncio.Lock()

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    async def subscribe(self, ws: WebSocket) -> None:
        """Add a WebSocket client as a subscriber."""
        async with self._lock:
            self._subscribers.append(ws)

    async def unsubscribe(self, ws: WebSocket) -> None:
        """Remove a WebSocket client."""
        async with self._lock:
            try:
                self._subscribers.remove(ws)
            except ValueError:
                pass

    async def publish(
        self,
        event_type: str,
        data: Optional[dict] = None,
        project_path: Optional[str] = None,
        performer: Optional[str] = None,
    ) -> int:
        """Broadcast an event to all connected clients.

        Returns the number of clients that received the event.
        """
        event = LiveEvent(
            type=event_type,
            data=data or {},
            project_path=project_path,
            performer=performer,
        )

        self._history.append(event)

        message = event.model_dump_json()
        delivered = 0
        dead_clients = []

        async with self._lock:
            for ws in self._subscribers:
                try:
                    await ws.send_text(message)
                    delivered += 1
                except Exception:
                    dead_clients.append(ws)

            # Clean up disconnected clients
            for ws in dead_clients:
                try:
                    self._subscribers.remove(ws)
                except ValueError:
                    pass

        return delivered

    def get_history(self, limit: int = 20) -> list[LiveEvent]:
        """Get recent events for client catch-up on reconnect."""
        events = list(self._history)
        return events[-limit:]

    def get_history_since(self, since_iso: str, limit: int = 50) -> list[LiveEvent]:
        """Get events since a given timestamp."""
        events = [e for e in self._history if e.timestamp > since_iso]
        return events[-limit:]


# Global singleton
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get or create the global EventBus singleton."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


# ---------------------------------------------------------------------------
# Convenience publisher functions
# ---------------------------------------------------------------------------

async def emit_checkpoint_created(
    project_path: str,
    checkpoint_id: str,
    performer: str = "",
    completion_pct: int = 0,
) -> int:
    """Emit a checkpoint_created event."""
    return await get_event_bus().publish(
        event_type="checkpoint_created",
        data={"checkpoint_id": checkpoint_id, "completion_pct": completion_pct},
        project_path=project_path,
        performer=performer,
    )


async def emit_signal_received(
    sender: str,
    recipient: str,
    signal_type: str = "",
    summary: str = "",
) -> int:
    """Emit a signal_received event."""
    return await get_event_bus().publish(
        event_type="signal_received",
        data={"sender": sender, "recipient": recipient, "signal_type": signal_type, "summary": summary},
        performer=sender,
    )


async def emit_signal_consumed(
    signal_id: str,
    consumed_by: str,
) -> int:
    """Emit a signal_consumed event."""
    return await get_event_bus().publish(
        event_type="signal_consumed",
        data={"signal_id": signal_id, "consumed_by": consumed_by},
        performer=consumed_by,
    )


async def emit_work_log_created(
    project_path: str,
    log_id: str,
    performer: str = "",
    request_text: str = "",
) -> int:
    """Emit a work_log_created event."""
    return await get_event_bus().publish(
        event_type="work_log_created",
        data={"log_id": log_id, "request_text": request_text[:100]},
        project_path=project_path,
        performer=performer,
    )


async def emit_workflow_stage(
    workflow_id: str,
    stage_id: str,
    stage_status: str,
    performer: str = "",
    project_path: str = "",
) -> int:
    """Emit a workflow stage event."""
    return await get_event_bus().publish(
        event_type=f"workflow_stage_{stage_status}",
        data={"workflow_id": workflow_id, "stage_id": stage_id, "stage_status": stage_status},
        project_path=project_path,
        performer=performer,
    )


async def emit_token_usage(
    project_path: str,
    tokens_used: int,
    model: str = "",
    performer: str = "",
) -> int:
    """Emit a token usage update."""
    return await get_event_bus().publish(
        event_type="token_usage_updated",
        data={"tokens_used": tokens_used, "model": model},
        project_path=project_path,
        performer=performer,
    )


# ---------------------------------------------------------------------------
# WebSocket route
# ---------------------------------------------------------------------------

router = APIRouter()


@router.websocket("/ws/events")
async def websocket_events(ws: WebSocket):
    """WebSocket endpoint for real-time event streaming.

    Protocol:
    - Server sends JSON events as they happen
    - Client can send {"action": "history", "limit": 20} to get recent events
    - Client can send {"action": "ping"} to keep connection alive
    - Client can send {"action": "subscribe", "project_path": "/path"} to filter events
    """
    await ws.accept()

    bus = get_event_bus()
    await bus.subscribe(ws)

    try:
        # Send welcome + recent history
        welcome = LiveEvent(
            type="connected",
            data={"message": "HITS event stream connected", "subscriber_count": bus.subscriber_count},
        )
        await ws.send_text(welcome.model_dump_json())

        # Listen for client messages
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            action = msg.get("action", "")

            if action == "history":
                limit = msg.get("limit", 20)
                events = bus.get_history(limit=limit)
                for event in events:
                    await ws.send_text(event.model_dump_json())

            elif action == "ping":
                pong = LiveEvent(type="pong", data={"subscriber_count": bus.subscriber_count})
                await ws.send_text(pong.model_dump_json())

    except WebSocketDisconnect:
        pass
    finally:
        await bus.unsubscribe(ws)
