"""Tests for Trace Attractor signal fanout via SignalBus.

Verifies that outcome and value-event signals from TelicSeam
can be consumed by the projector's subscriber pattern.
"""

from __future__ import annotations

import pytest

from dharma_swarm.signal_bus import SignalBus


async def test_subscriber_receives_outcome_signal():
    """Signal subscribers receive SIGNAL_OUTCOME_RECORDED events."""
    bus = SignalBus()
    received: list[dict] = []

    def on_outcome(payload: dict) -> None:
        received.append(payload)

    bus.subscribe("SIGNAL_OUTCOME_RECORDED", on_outcome)
    bus.emit({
        "type": "SIGNAL_OUTCOME_RECORDED",
        "trace_id": "trc_fanout_test",
        "outcome_id": "out_001",
        "success": True,
    })

    assert len(received) == 1
    assert received[0]["trace_id"] == "trc_fanout_test"


async def test_subscriber_receives_value_event_signal():
    """Signal subscribers receive SIGNAL_VALUE_EVENT_RECORDED events."""
    bus = SignalBus()
    received: list[dict] = []

    def on_value(payload: dict) -> None:
        received.append(payload)

    bus.subscribe("SIGNAL_VALUE_EVENT_RECORDED", on_value)
    bus.emit({
        "type": "SIGNAL_VALUE_EVENT_RECORDED",
        "trace_id": "trc_fanout_test",
        "value_event_id": "ve_001",
    })

    assert len(received) == 1
    assert received[0]["value_event_id"] == "ve_001"


async def test_subscriber_only_fires_on_matching_event():
    """Subscriber for one event type ignores other event types."""
    bus = SignalBus()
    received: list[dict] = []

    def on_outcome(payload: dict) -> None:
        received.append(payload)

    bus.subscribe("SIGNAL_OUTCOME_RECORDED", on_outcome)
    bus.emit({"type": "SIGNAL_VALUE_EVENT_RECORDED", "trace_id": "trc_test"})

    assert len(received) == 0


async def test_bad_subscriber_cannot_crash_emit():
    """A failing subscriber must not prevent signal delivery."""
    bus = SignalBus()
    received: list[dict] = []

    def bad_subscriber(payload: dict) -> None:
        raise RuntimeError("boom")

    def good_subscriber(payload: dict) -> None:
        received.append(payload)

    bus.subscribe("SIGNAL_OUTCOME_RECORDED", bad_subscriber)
    bus.subscribe("SIGNAL_OUTCOME_RECORDED", good_subscriber)

    bus.emit({"type": "SIGNAL_OUTCOME_RECORDED", "trace_id": "trc_test"})
    assert len(received) == 1


async def test_unsubscribe():
    """Unsubscribed callbacks no longer receive events."""
    bus = SignalBus()
    received: list[dict] = []

    def on_outcome(payload: dict) -> None:
        received.append(payload)

    bus.subscribe("SIGNAL_OUTCOME_RECORDED", on_outcome)
    bus.unsubscribe("SIGNAL_OUTCOME_RECORDED", on_outcome)
    bus.emit({"type": "SIGNAL_OUTCOME_RECORDED", "trace_id": "trc_test"})

    assert len(received) == 0


async def test_multiple_subscribers():
    """Multiple subscribers for the same event all receive the signal."""
    bus = SignalBus()
    r1: list[dict] = []
    r2: list[dict] = []

    bus.subscribe("SIGNAL_OUTCOME_RECORDED", lambda p: r1.append(p))
    bus.subscribe("SIGNAL_OUTCOME_RECORDED", lambda p: r2.append(p))
    bus.emit({"type": "SIGNAL_OUTCOME_RECORDED", "trace_id": "trc_multi"})

    assert len(r1) == 1
    assert len(r2) == 1
