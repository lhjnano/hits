"""Tests for WebSocket EventBus and real-time event streaming.

Covers:
- EventBus: subscribe/unsubscribe/publish lifecycle
- LiveEvent: model serialization
- History: ring buffer + since-filter
- Convenience emitters: emit_checkpoint_created, emit_signal_*, etc.
- Dead client cleanup during publish
- Singleton behavior
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from hits_core.api.routes.ws import (
    EventBus,
    LiveEvent,
    get_event_bus,
    emit_checkpoint_created,
    emit_signal_received,
    emit_signal_consumed,
    emit_work_log_created,
    emit_workflow_stage,
    emit_token_usage,
    _event_bus,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bus():
    """Fresh EventBus for each test."""
    return EventBus()


@pytest.fixture(autouse=True)
def reset_global_bus():
    """Reset the global singleton between tests."""
    import hits_core.api.routes.ws as ws_mod
    old = ws_mod._event_bus
    ws_mod._event_bus = None
    yield
    ws_mod._event_bus = old


def _make_ws() -> AsyncMock:
    """Create a mock WebSocket."""
    ws = AsyncMock()
    ws.send_text = AsyncMock()
    return ws


# ===========================================================================
# LiveEvent model
# ===========================================================================

class TestLiveEvent:
    def test_basic_creation(self):
        e = LiveEvent(type="test_event", data={"key": "value"})
        assert e.type == "test_event"
        assert e.data == {"key": "value"}
        assert e.project_path is None
        assert e.performer is None
        assert e.timestamp is not None

    def test_all_fields(self):
        e = LiveEvent(
            type="checkpoint_created",
            data={"id": "chk_1"},
            project_path="/proj",
            performer="claude",
            timestamp="2025-01-01T00:00:00",
        )
        assert e.project_path == "/proj"
        assert e.performer == "claude"

    def test_json_serialization(self):
        e = LiveEvent(type="ping", data={"n": 42})
        raw = e.model_dump_json()
        parsed = json.loads(raw)
        assert parsed["type"] == "ping"
        assert parsed["data"]["n"] == 42

    def test_default_data_is_empty_dict(self):
        e = LiveEvent(type="empty")
        assert e.data == {}


# ===========================================================================
# EventBus core
# ===========================================================================

class TestEventBusSubscribe:
    @pytest.mark.asyncio
    async def test_subscribe_increments_count(self, bus):
        ws = _make_ws()
        await bus.subscribe(ws)
        assert bus.subscriber_count == 1

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self, bus):
        ws1, ws2, ws3 = _make_ws(), _make_ws(), _make_ws()
        await bus.subscribe(ws1)
        await bus.subscribe(ws2)
        await bus.subscribe(ws3)
        assert bus.subscriber_count == 3


class TestEventBusUnsubscribe:
    @pytest.mark.asyncio
    async def test_unsubscribe_decrements_count(self, bus):
        ws = _make_ws()
        await bus.subscribe(ws)
        await bus.unsubscribe(ws)
        assert bus.subscriber_count == 0

    @pytest.mark.asyncio
    async def test_unsubscribe_unknown_ws_is_noop(self, bus):
        ws = _make_ws()
        # Should not raise
        await bus.unsubscribe(ws)
        assert bus.subscriber_count == 0

    @pytest.mark.asyncio
    async def test_double_unsubscribe(self, bus):
        ws = _make_ws()
        await bus.subscribe(ws)
        await bus.unsubscribe(ws)
        await bus.unsubscribe(ws)  # second time — no error
        assert bus.subscriber_count == 0


class TestEventBusPublish:
    @pytest.mark.asyncio
    async def test_publish_to_single_subscriber(self, bus):
        ws = _make_ws()
        await bus.subscribe(ws)

        delivered = await bus.publish("test_event", data={"hello": "world"})
        assert delivered == 1
        ws.send_text.assert_called_once()

        raw = ws.send_text.call_args[0][0]
        msg = json.loads(raw)
        assert msg["type"] == "test_event"
        assert msg["data"]["hello"] == "world"

    @pytest.mark.asyncio
    async def test_publish_to_multiple_subscribers(self, bus):
        clients = [_make_ws() for _ in range(5)]
        for ws in clients:
            await bus.subscribe(ws)

        delivered = await bus.publish("broadcast")
        assert delivered == 5
        for ws in clients:
            ws.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_to_zero_subscribers(self, bus):
        delivered = await bus.publish("nobody_listening")
        assert delivered == 0

    @pytest.mark.asyncio
    async def test_publish_with_project_and_performer(self, bus):
        ws = _make_ws()
        await bus.subscribe(ws)

        await bus.publish(
            "checkpoint_created",
            data={"id": "chk_1"},
            project_path="/my/proj",
            performer="claude",
        )
        raw = ws.send_text.call_args[0][0]
        msg = json.loads(raw)
        assert msg["project_path"] == "/my/proj"
        assert msg["performer"] == "claude"

    @pytest.mark.asyncio
    async def test_publish_returns_delivered_count(self, bus):
        ws = _make_ws()
        await bus.subscribe(ws)
        count = await bus.publish("test")
        assert count == 1


class TestEventBusDeadClientCleanup:
    @pytest.mark.asyncio
    async def test_dead_client_removed_on_publish(self, bus):
        alive = _make_ws()
        dead = _make_ws()
        dead.send_text.side_effect = ConnectionResetError("gone")

        await bus.subscribe(alive)
        await bus.subscribe(dead)
        assert bus.subscriber_count == 2

        delivered = await bus.publish("cleanup_test")
        assert delivered == 1
        assert bus.subscriber_count == 1

    @pytest.mark.asyncio
    async def test_all_clients_dead(self, bus):
        ws1 = _make_ws()
        ws2 = _make_ws()
        ws1.send_text.side_effect = Exception("fail")
        ws2.send_text.side_effect = Exception("fail")

        await bus.subscribe(ws1)
        await bus.subscribe(ws2)

        delivered = await bus.publish("all_dead")
        assert delivered == 0
        assert bus.subscriber_count == 0

    @pytest.mark.asyncio
    async def test_partial_failure(self, bus):
        clients = []
        for i in range(4):
            ws = _make_ws()
            if i % 2 == 0:
                ws.send_text.side_effect = Exception("fail")
            clients.append(ws)
            await bus.subscribe(ws)

        delivered = await bus.publish("partial")
        assert delivered == 2
        assert bus.subscriber_count == 2


# ===========================================================================
# History
# ===========================================================================

class TestEventBusHistory:
    @pytest.mark.asyncio
    async def test_history_starts_empty(self, bus):
        history = bus.get_history()
        assert history == []

    @pytest.mark.asyncio
    async def test_history_records_events(self, bus):
        await bus.publish("event1")
        await bus.publish("event2")
        await bus.publish("event3")

        history = bus.get_history()
        assert len(history) == 3
        assert history[0].type == "event1"
        assert history[2].type == "event3"

    @pytest.mark.asyncio
    async def test_history_limit(self, bus):
        for i in range(30):
            await bus.publish(f"event_{i}")

        history = bus.get_history(limit=5)
        assert len(history) == 5
        # Should be the last 5
        assert history[0].type == "event_25"
        assert history[4].type == "event_29"

    @pytest.mark.asyncio
    async def test_history_since(self, bus):
        await bus.publish("early")
        # Get timestamp between events
        mid = datetime.now().isoformat()
        await bus.publish("late1")
        await bus.publish("late2")

        since = bus.get_history_since(mid)
        types = [e.type for e in since]
        assert "early" not in types
        assert "late1" in types
        assert "late2" in types

    @pytest.mark.asyncio
    async def test_ring_buffer_overflow(self, bus):
        """History should cap at MAX_HISTORY."""
        for i in range(bus.MAX_HISTORY + 20):
            await bus.publish(f"overflow_{i}")

        assert len(bus._history) == bus.MAX_HISTORY
        # Oldest events should be gone
        first_in_buffer = bus._history[0]
        assert first_in_buffer.type == "overflow_20"


# ===========================================================================
# Singleton
# ===========================================================================

class TestGetEventBus:
    def test_creates_singleton(self):
        bus1 = get_event_bus()
        assert bus1 is not None
        assert isinstance(bus1, EventBus)

    def test_returns_same_instance(self):
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert bus1 is bus2


# ===========================================================================
# Convenience emitters
# ===========================================================================

class TestConvenienceEmitters:
    @pytest.mark.asyncio
    async def test_emit_checkpoint_created(self, bus):
        ws = _make_ws()
        await bus.subscribe(ws)

        # Patch global bus
        import hits_core.api.routes.ws as ws_mod
        ws_mod._event_bus = bus

        delivered = await emit_checkpoint_created(
            project_path="/proj",
            checkpoint_id="chk_123",
            performer="claude",
            completion_pct=75,
        )
        assert delivered == 1
        msg = json.loads(ws.send_text.call_args[0][0])
        assert msg["type"] == "checkpoint_created"
        assert msg["data"]["checkpoint_id"] == "chk_123"
        assert msg["data"]["completion_pct"] == 75

    @pytest.mark.asyncio
    async def test_emit_signal_received(self, bus):
        ws = _make_ws()
        await bus.subscribe(ws)

        import hits_core.api.routes.ws as ws_mod
        ws_mod._event_bus = bus

        delivered = await emit_signal_received(
            sender="claude",
            recipient="opencode",
            signal_type="session_end",
            summary="Auth done",
        )
        assert delivered == 1
        msg = json.loads(ws.send_text.call_args[0][0])
        assert msg["type"] == "signal_received"
        assert msg["performer"] == "claude"
        assert msg["data"]["recipient"] == "opencode"

    @pytest.mark.asyncio
    async def test_emit_signal_consumed(self, bus):
        ws = _make_ws()
        await bus.subscribe(ws)

        import hits_core.api.routes.ws as ws_mod
        ws_mod._event_bus = bus

        delivered = await emit_signal_consumed(
            signal_id="sig_abc",
            consumed_by="opencode",
        )
        assert delivered == 1
        msg = json.loads(ws.send_text.call_args[0][0])
        assert msg["type"] == "signal_consumed"

    @pytest.mark.asyncio
    async def test_emit_work_log_created(self, bus):
        ws = _make_ws()
        await bus.subscribe(ws)

        import hits_core.api.routes.ws as ws_mod
        ws_mod._event_bus = bus

        delivered = await emit_work_log_created(
            project_path="/proj",
            log_id="log_1",
            performer="claude",
            request_text="Fixed auth bug",
        )
        assert delivered == 1
        msg = json.loads(ws.send_text.call_args[0][0])
        assert msg["type"] == "work_log_created"
        # request_text should be truncated to 100 chars
        assert msg["data"]["request_text"] == "Fixed auth bug"

    @pytest.mark.asyncio
    async def test_emit_work_log_truncates_long_text(self, bus):
        ws = _make_ws()
        await bus.subscribe(ws)

        import hits_core.api.routes.ws as ws_mod
        ws_mod._event_bus = bus

        long_text = "x" * 200
        await emit_work_log_created(
            project_path="/proj",
            log_id="log_2",
            request_text=long_text,
        )
        msg = json.loads(ws.send_text.call_args[0][0])
        assert len(msg["data"]["request_text"]) == 100

    @pytest.mark.asyncio
    async def test_emit_workflow_stage(self, bus):
        ws = _make_ws()
        await bus.subscribe(ws)

        import hits_core.api.routes.ws as ws_mod
        ws_mod._event_bus = bus

        delivered = await emit_workflow_stage(
            workflow_id="wf_1",
            stage_id="s1",
            stage_status="started",
            performer="agent-1",
        )
        assert delivered == 1
        msg = json.loads(ws.send_text.call_args[0][0])
        assert msg["type"] == "workflow_stage_started"

    @pytest.mark.asyncio
    async def test_emit_workflow_stage_completed(self, bus):
        ws = _make_ws()
        await bus.subscribe(ws)

        import hits_core.api.routes.ws as ws_mod
        ws_mod._event_bus = bus

        await emit_workflow_stage(
            workflow_id="wf_1",
            stage_id="s2",
            stage_status="completed",
        )
        msg = json.loads(ws.send_text.call_args[0][0])
        assert msg["type"] == "workflow_stage_completed"

    @pytest.mark.asyncio
    async def test_emit_token_usage(self, bus):
        ws = _make_ws()
        await bus.subscribe(ws)

        import hits_core.api.routes.ws as ws_mod
        ws_mod._event_bus = bus

        delivered = await emit_token_usage(
            project_path="/proj",
            tokens_used=5000,
            model="gpt-4o",
            performer="claude",
        )
        assert delivered == 1
        msg = json.loads(ws.send_text.call_args[0][0])
        assert msg["type"] == "token_usage_updated"
        assert msg["data"]["tokens_used"] == 5000
        assert msg["data"]["model"] == "gpt-4o"
