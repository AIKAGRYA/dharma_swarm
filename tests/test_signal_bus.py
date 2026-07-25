"""Tests for signal_bus.py — inter-loop temporal coherence."""
import threading
import time
import pytest
from dharma_swarm.signal_bus import SignalBus


class TestSignalBus:
    def test_emit_and_drain_all(self):
        bus = SignalBus()
        bus.emit({"type": "A", "val": 1})
        bus.emit({"type": "B", "val": 2})
        events = bus.drain()
        assert len(events) == 2
        assert events[0]["type"] == "A"
        assert events[1]["type"] == "B"
        # drained — second call returns empty
        assert bus.drain() == []

    def test_drain_by_type(self):
        bus = SignalBus()
        bus.emit({"type": "ANOMALY_DETECTED"})
        bus.emit({"type": "CASCADE_EIGENFORM_DISTANCE"})
        bus.emit({"type": "ANOMALY_DETECTED"})
        anomalies = bus.drain(["ANOMALY_DETECTED"])
        assert len(anomalies) == 2
        # CASCADE should still be there
        remaining = bus.drain()
        assert len(remaining) == 1
        assert remaining[0]["type"] == "CASCADE_EIGENFORM_DISTANCE"

    def test_ttl_expiry(self):
        bus = SignalBus(ttl_seconds=0.1)
        bus.emit({"type": "OLD"})
        time.sleep(0.15)
        events = bus.drain()
        assert len(events) == 0

    def test_peek_non_destructive(self):
        bus = SignalBus()
        bus.emit({"type": "X"})
        peeked = bus.peek()
        assert len(peeked) == 1
        # still there after peek
        drained = bus.drain()
        assert len(drained) == 1

    def test_pending_count(self):
        bus = SignalBus()
        assert bus.pending_count == 0
        bus.emit({"type": "A"})
        bus.emit({"type": "B"})
        assert bus.pending_count == 2

    def test_clear(self):
        bus = SignalBus()
        bus.emit({"type": "A"})
        bus.clear()
        assert bus.pending_count == 0
        assert bus.drain() == []

    def test_drain_mixed_types(self):
        bus = SignalBus()
        bus.emit({"type": "FITNESS_IMPROVED"})
        bus.emit({"type": "FITNESS_DEGRADED"})
        bus.emit({"type": "RECOGNITION_UPDATED"})
        improved = bus.drain(["FITNESS_IMPROVED", "FITNESS_DEGRADED"])
        assert len(improved) == 2
        rest = bus.drain()
        assert len(rest) == 1

    def test_empty_drain(self):
        bus = SignalBus()
        assert bus.drain() == []
        assert bus.drain(["ANYTHING"]) == []

    # ------------------------------------------------------------------
    # Subscriber pattern tests
    # ------------------------------------------------------------------

    def test_subscribe_fires_on_emit(self):
        bus = SignalBus()
        received: list[dict] = []
        bus.subscribe("OUTCOME_RECORDED", lambda e: received.append(e))
        bus.emit({"type": "OUTCOME_RECORDED", "task_id": "t1"})
        assert len(received) == 1
        assert received[0]["task_id"] == "t1"

    def test_subscribe_only_matching_type(self):
        bus = SignalBus()
        received: list[dict] = []
        bus.subscribe("OUTCOME_RECORDED", lambda e: received.append(e))
        bus.emit({"type": "OTHER_EVENT", "val": 1})
        assert len(received) == 0

    def test_multiple_subscribers(self):
        bus = SignalBus()
        a: list[dict] = []
        b: list[dict] = []
        bus.subscribe("X", lambda e: a.append(e))
        bus.subscribe("X", lambda e: b.append(e))
        bus.emit({"type": "X"})
        assert len(a) == 1
        assert len(b) == 1

    def test_subscriber_error_does_not_break_emit(self):
        bus = SignalBus()
        received: list[dict] = []

        def bad_cb(e):
            raise ValueError("boom")

        bus.subscribe("X", bad_cb)
        bus.subscribe("X", lambda e: received.append(e))
        bus.emit({"type": "X"})
        # Second subscriber still fires despite first raising
        assert len(received) == 1
        # Event still in deque
        assert bus.pending_count == 1

    def test_subscriber_mutation_cannot_change_queued_event(self):
        bus = SignalBus()
        original = {"type": "AUDIT", "payload": {"value": 1}}

        def mutate(event):
            event["mutated_by_subscriber"] = True
            event["payload"]["value"] = 99

        bus.subscribe("AUDIT", mutate)
        bus.emit(original)

        assert bus.drain() == [{"type": "AUDIT", "payload": {"value": 1}}]
        assert original == {"type": "AUDIT", "payload": {"value": 1}}

    def test_emit_accepts_non_deepcopyable_opaque_payload(self):
        bus = SignalBus()
        lock = threading.Lock()
        received: list[dict] = []
        bus.subscribe("RUNTIME_HANDLE", received.append)

        bus.emit({"type": "RUNTIME_HANDLE", "payload": {"lock": lock}})

        assert received[0]["payload"]["lock"] is lock
        assert bus.drain()[0]["payload"]["lock"] is lock

    def test_peek_mutation_cannot_change_queued_event(self):
        bus = SignalBus()
        bus.emit({"type": "AUDIT", "payload": {"value": 1}})

        peeked = bus.peek()
        peeked[0]["payload"]["value"] = 99

        assert bus.drain() == [{"type": "AUDIT", "payload": {"value": 1}}]

    def test_fitness_view_mutation_cannot_change_queued_event(self):
        bus = SignalBus()
        bus.emit({"type": "AGENT_FITNESS", "agent": "fixture", "scores": [1]})

        viewed = bus.get_agent_fitness("fixture")
        viewed[0]["scores"].append(99)

        assert bus.peek()[0]["scores"] == [1]

    def test_unsubscribe(self):
        bus = SignalBus()
        received: list[dict] = []
        cb = lambda e: received.append(e)
        bus.subscribe("X", cb)
        bus.emit({"type": "X"})
        assert len(received) == 1
        bus.unsubscribe("X", cb)
        bus.emit({"type": "X"})
        assert len(received) == 1  # no new callback

    def test_unsubscribe_nonexistent_is_noop(self):
        bus = SignalBus()
        bus.unsubscribe("X", lambda e: None)  # should not raise
