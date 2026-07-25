"""Property-based tests for canonical replay reducer.

The replay engine claims: "Every runtime mutation must be replayable."
For that to be true, _execute_replay must satisfy:

  P1 DETERMINISM        : replay(events) == replay(events)  (any events)
  P2 HASH-DETERMINISM   : hash(replay(events)) == hash(replay(events))
  P3 KEY-ORDER-AGNOSTIC : hash({a:1, b:2}) == hash({b:2, a:1})
  P4 LENGTH-INVARIANT   : len(state.event_types) == len(events)
  P5 COUNT-INVARIANT    : state.event_count == len(events)
  P6 UNKNOWN-SAFE       : feeding garbage events doesn't raise
  P7 EMPTY-NEUTRAL      : replay([]) is the initial state (with count=0)

These hold for ALL inputs — that's why we use Hypothesis.
If any of these break, replay is broken and the substrate guarantee
("clean if it replays deterministically") is a lie.
"""
from __future__ import annotations

import asyncio

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from dharma_swarm.canonical_replay import CanonicalReplayEngine


@pytest.fixture
def engine(tmp_path):
    return CanonicalReplayEngine(tmp_path / "events")


# Strategy: an event envelope with random type + payload.
event_type_strategy = st.sampled_from([
    "state.snapshot",
    "memory.event",
    "action.event",
    "audit.event",
    "unknown.event",
    "",  # edge case
])

scalar = st.one_of(
    st.integers(min_value=-1000, max_value=1000),
    st.floats(allow_nan=False, allow_infinity=False, width=32),
    st.text(max_size=20),
    st.booleans(),
    st.none(),
)

payload_strategy = st.dictionaries(
    keys=st.text(min_size=1, max_size=15),
    values=scalar,
    max_size=8,
)

event_strategy = st.fixed_dictionaries({
    "event_type": event_type_strategy,
    "emitted_at": st.text(max_size=30),
    "event_id": st.text(min_size=1, max_size=20),
    "payload": payload_strategy,
})

events_strategy = st.lists(event_strategy, max_size=30)


# ----- P1, P2: Determinism -----

@given(events=events_strategy)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
def test_p1_replay_is_deterministic(engine, events):
    """Same events → byte-identical state."""
    state_a = asyncio.run(engine._execute_replay(events))
    state_b = asyncio.run(engine._execute_replay(events))
    assert state_a == state_b


@given(events=events_strategy)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
def test_p2_hash_is_deterministic(engine, events):
    """Same events → same hash."""
    s_a = asyncio.run(engine._execute_replay(events))
    s_b = asyncio.run(engine._execute_replay(events))
    assert engine._hash_state(s_a) == engine._hash_state(s_b)


# ----- P3: Key-order-agnostic hashing -----

@given(d=st.dictionaries(st.text(min_size=1, max_size=10), scalar, max_size=12))
def test_p3_hash_is_key_order_agnostic(d):
    """_hash_state must use sort_keys — order of insertion irrelevant."""
    e = CanonicalReplayEngine.__new__(CanonicalReplayEngine)
    # Build the same dict twice with shuffled key order
    keys = list(d.keys())
    forward = {k: d[k] for k in keys}
    reverse = {k: d[k] for k in reversed(keys)}
    assert e._hash_state(forward) == e._hash_state(reverse)


# ----- P4, P5: Counting invariants -----

@given(events=events_strategy)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
def test_p4_event_types_length_matches_input(engine, events):
    """state.event_types must record every input event."""
    state = asyncio.run(engine._execute_replay(events))
    assert len(state["event_types"]) == len(events)


@given(events=events_strategy)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
def test_p5_event_count_matches_input(engine, events):
    """state.event_count must equal len(events)."""
    state = asyncio.run(engine._execute_replay(events))
    assert state["event_count"] == len(events)


# ----- P6: Unknown-event safety -----

@given(events=events_strategy)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
def test_p6_unknown_events_dont_raise(engine, events):
    """Garbage events must be silently counted, not crash."""
    # Force every event to an unknown type
    twisted = [dict(e, event_type="totally.not.a.real.type") for e in events]
    state = asyncio.run(engine._execute_replay(twisted))
    assert state["unknown_event_count"] >= 0  # Whatever it is, no crash


# ----- P7: Empty-neutral -----

def test_p7_empty_replay_is_initial_state(engine):
    """No events → initial state with count=0."""
    state = asyncio.run(engine._execute_replay([]))
    assert state["event_count"] == 0
    assert state["event_types"] == []
    assert state["memory"]["count"] == 0
    assert state["actions"]["count"] == 0
    assert state["audits"]["count"] == 0
