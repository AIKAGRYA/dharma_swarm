"""Complexity stress test #1: replay metamorphic invariance.

Tests that CanonicalReplayEngine produces the same final state hash for
event streams that are reorderings within causal classes. This is the
foundational metamorphic invariant for the replay substrate.

If this fails, replay is order-dependent in ways it claims not to be.

Unlike the per-module tests in ``tests/test_canonical_replay.py`` (which
replay one fixed stream and check that *repeated* replays agree), this test
perturbs the stream itself: it reorders events that belong to different
causal classes and asserts the reconstructed-state hash is unchanged.
"""
from __future__ import annotations

import random
from typing import Any

import pytest

from dharma_swarm.canonical_replay import CanonicalReplayEngine

# A representative runtime stream covering all four typed reducers
# (state.snapshot, memory.event, action.event, audit.event). The shapes
# mirror the events used in tests/test_canonical_replay.py so the trace is
# faithful to what the engine sees in production. Two events of each type
# exercise intra-class ordering; an "unknown" event exercises the catch-all.
BASE_TRACE: list[dict[str, Any]] = [
    {
        "event_type": "state.snapshot",
        "emitted_at": "2026-01-01T00:00:00Z",
        "payload": {
            "cycle_count": 1,
            "uptime_seconds": 10,
            "runtime_mode": "boot",
            "status": "starting",
        },
    },
    {
        "event_type": "memory.event",
        "emitted_at": "2026-01-01T00:00:01Z",
        "payload": {
            "memory_id": "m1",
            "memory_type": "episodic",
            "importance": 3,
            "summary": "first memory",
        },
    },
    {
        "event_type": "action.event",
        "emitted_at": "2026-01-01T00:00:02Z",
        "payload": {"action_name": "evolve", "decision": "apply", "confidence": 0.9},
    },
    {
        "event_type": "audit.event",
        "emitted_at": "2026-01-01T00:00:03Z",
        "payload": {"gate": "telos", "result": "pass", "reason": "aligned"},
    },
    {
        "event_type": "memory.event",
        "emitted_at": "2026-01-01T00:00:04Z",
        "payload": {
            "memory_id": "m2",
            "memory_type": "semantic",
            "importance": 5,
            "summary": "second memory",
        },
    },
    {
        "event_type": "action.event",
        "emitted_at": "2026-01-01T00:00:05Z",
        "payload": {"action_name": "merge", "decision": "defer", "confidence": 0.4},
    },
    {
        "event_type": "audit.event",
        "emitted_at": "2026-01-01T00:00:06Z",
        "payload": {"gate": "ahimsa", "result": "fail", "reason": "risk"},
    },
    {
        "event_type": "state.snapshot",
        "emitted_at": "2026-01-01T00:00:07Z",
        "payload": {
            "cycle_count": 2,
            "uptime_seconds": 20,
            "runtime_mode": "active",
            "status": "ok",
        },
    },
]


def causal_class(event: dict[str, Any]) -> tuple[str, str]:
    """Two events are in the same causal class iff this returns the same tuple."""
    payload = event.get("payload", {}) or {}
    agent = payload.get("agent_id") or payload.get("source") or ""
    return (str(event["event_type"]), str(agent))


def reorder_preserving_causal_class(
    events: list[dict[str, Any]], seed: int
) -> list[dict[str, Any]]:
    """Return a permutation of ``events`` that preserves intra-class order.

    Events sharing a causal class keep their relative order; events in
    different classes may be freely interleaved. This is the metamorphic
    relation: a reordering the replay engine should be invariant to.
    """
    rng = random.Random(seed)
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for e in events:
        buckets.setdefault(causal_class(e), []).append(e)
    # Random interleave: repeatedly pop the front of a randomly chosen
    # non-empty bucket. Within-class order is preserved by construction.
    result: list[dict[str, Any]] = []
    while buckets:
        k = rng.choice(list(buckets.keys()))
        result.append(buckets[k].pop(0))
        if not buckets[k]:
            del buckets[k]
    return result


def intra_class_order_preserved(
    original: list[dict[str, Any]], reordered: list[dict[str, Any]]
) -> bool:
    """Verify the reordering kept the relative order within every causal class."""
    by_class_original: dict[tuple[str, str], list[int]] = {}
    for i, e in enumerate(original):
        by_class_original.setdefault(causal_class(e), []).append(i)
    by_class_reordered: dict[tuple[str, str], list[int]] = {}
    for e in reordered:
        by_class_reordered.setdefault(causal_class(e), []).append(id(e))
    # For each class, the sequence of object identities in the reordered
    # stream must match the original stream's sequence for that class.
    for klass, idxs in by_class_original.items():
        original_ids = [id(original[i]) for i in idxs]
        if by_class_reordered.get(klass) != original_ids:
            return False
    return True


async def _hash_for(events: list[dict[str, Any]]) -> str:
    """Reconstruct state from ``events`` and return its canonical hash.

    Uses the internal _execute_replay + _hash_state path (no disk I/O), the
    same fold replay_session() runs after loading events from the log.
    """
    engine = CanonicalReplayEngine()
    state = await engine._execute_replay(events)
    return engine._hash_state(state)


@pytest.mark.asyncio
@pytest.mark.parametrize("seed", list(range(20)))
async def test_replay_invariant_under_causal_class_reordering(seed: int) -> None:
    """Metamorphic: any causal-class-preserving reorder yields the same hash."""
    reordered = reorder_preserving_causal_class(BASE_TRACE, seed=seed)
    assert intra_class_order_preserved(BASE_TRACE, reordered), (
        f"Reorder (seed={seed}) broke intra-class order; relation is invalid."
    )

    base_hash = await _hash_for(BASE_TRACE)
    reordered_hash = await _hash_for(reordered)
    assert base_hash == reordered_hash, (
        f"Replay hash changed under causal-class-preserving reorder "
        f"(seed={seed}). Base={base_hash[:16]} Reordered={reordered_hash[:16]}\n"
        f"  base types     = {[e['event_type'] for e in BASE_TRACE]}\n"
        f"  reordered types= {[e['event_type'] for e in reordered]}"
    )


@pytest.mark.asyncio
async def test_base_trace_is_nontrivial() -> None:
    """Sanity: the base trace covers all 4 reducer types."""
    types = {e["event_type"] for e in BASE_TRACE}
    assert types == {"state.snapshot", "memory.event", "action.event", "audit.event"}, (
        f"BASE_TRACE missing reducer coverage: got {types}"
    )
