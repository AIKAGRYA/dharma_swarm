"""Complexity stress test #1: replay metamorphic relations.

This is the L2 (metamorphic) layer of the replay testing doctrine. It sits
alongside, and is consistent with, the L1 property layer and the L3 golden
layer in ``tests/properties/test_canonical_replay_properties.py`` and
``tests/test_canonical_replay_golden.py``.

What the engine actually guarantees
------------------------------------
``CanonicalReplayEngine`` folds an *already-canonicalized* event stream. The
canonicalization lives upstream in ``EventLog.read_envelopes``, which sorts by
``(emitted_at, event_id)`` before the fold ever runs. So the engine's real
determinism guarantee is:

    replaying a session is invariant to the *delivery / storage* order of its
    envelopes, because ingestion re-imposes a total order first.

It is NOT the stronger claim that the raw fold is order-invariant. The fold
records an ordered ``event_types`` breadcrumb and a last-in-fold-order
``final_timestamp``; both are positional. So feeding the fold a reordering
*without* re-sorting does change the state hash.

This module pins down both halves precisely:

  * the positive metamorphic relation that holds (delivery-order invariance
    via canonical sort), and
  * the fixture-local boundary of the order-sensitivity (for ``BASE_TRACE``'s
    unique reducer keys and preserved snapshot order, only the two positional
    breadcrumbs differ),

and keeps the "full reorder-invariance does not hold" result visible as a
strict xfail finding rather than a silently-masked red test.
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
# exercise intra-class ordering.
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


def canonical_sort(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Re-impose the engine's ingestion order.

    Mirrors ``EventLog.read_envelopes``: sort by ``(emitted_at, event_id)``.
    This is the canonicalization the real replay path applies before folding.
    """
    return sorted(
        events,
        key=lambda e: (str(e.get("emitted_at", "")), str(e.get("event_id", ""))),
    )


def reorder_preserving_causal_class(
    events: list[dict[str, Any]], seed: int
) -> list[dict[str, Any]]:
    """Return a permutation of ``events`` that preserves intra-class order.

    Events sharing a causal class keep their relative order; events in
    different classes may be freely interleaved.
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


async def _replay_state(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Fold ``events`` into final replay state (internal path, no disk I/O)."""
    engine = CanonicalReplayEngine()
    return await engine._execute_replay(events)


async def _hash_for(events: list[dict[str, Any]]) -> str:
    """Reconstruct state from ``events`` and return its canonical hash."""
    engine = CanonicalReplayEngine()
    state = await engine._execute_replay(events)
    return engine._hash_state(state)


def _semantic_state(state: dict[str, Any]) -> dict[str, Any]:
    """Project out the positional breadcrumbs for this fixture.

    Reducers such as ``runtime``, ``actions.last_by_name``, and
    ``audits.by_gate.last_result`` are order-sensitive in general. ``BASE_TRACE``
    avoids that ambiguity by using unique memory/action/audit keys and by
    keeping both snapshots in one causal class, so this projection only needs
    to normalize ``event_types`` and ``final_timestamp``.
    """
    return {**state, "event_types": sorted(state["event_types"]), "final_timestamp": ""}


@pytest.mark.parametrize("seed", list(range(20)))
async def test_replay_hash_invariant_under_delivery_reordering(seed: int) -> None:
    """The real guarantee: hash is invariant to delivery/storage order.

    The engine folds an already-canonicalized stream (``read_envelopes`` sorts
    by ``(emitted_at, event_id)`` first). So any reordering of how envelopes
    arrive or are stored must replay to the same hash once canonicalized.
    """
    reordered = reorder_preserving_causal_class(BASE_TRACE, seed=seed)
    assert intra_class_order_preserved(BASE_TRACE, reordered), (
        f"Reorder (seed={seed}) broke intra-class order; relation is invalid."
    )

    base_hash = await _hash_for(canonical_sort(BASE_TRACE))
    reordered_hash = await _hash_for(canonical_sort(reordered))
    assert base_hash == reordered_hash, (
        f"Replay hash changed under delivery-order reordering after canonical "
        f"sort (seed={seed}). Base={base_hash[:16]} Reordered={reordered_hash[:16]}"
    )


@pytest.mark.parametrize("seed", list(range(20)))
async def test_raw_fold_order_sensitivity_is_isolated_to_breadcrumbs(seed: int) -> None:
    """Fixture-local boundary: order-sensitivity is confined to breadcrumbs.

    Feeding the raw fold a causal-class-preserving reordering (no canonical
    sort) can change the hash, but for ``BASE_TRACE`` the unique reducer keys
    and preserved snapshot order mean only ``event_types`` and
    ``final_timestamp`` differ. If this fixture starts leaking order dependence
    into the projected semantics, this breaks.
    """
    reordered = reorder_preserving_causal_class(BASE_TRACE, seed=seed)
    assert intra_class_order_preserved(BASE_TRACE, reordered)

    base = await _replay_state(BASE_TRACE)
    perturbed = await _replay_state(reordered)
    assert _semantic_state(base) == _semantic_state(perturbed), (
        f"Raw-fold reordering (seed={seed}) changed this fixture's projected "
        f"semantics, not just the positional breadcrumbs."
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "FINDING (engine-property gap): replay determinism is guaranteed only "
        "relative to read_envelopes' (emitted_at, event_id) canonical sort, not "
        "intrinsic to the fold. A raw causal-class-preserving reorder changes the "
        "ordered event_types breadcrumb, so the state hash is NOT reorder-invariant. "
        "This is consistent with #601 property P4 (event_types length == #events, "
        "ordered) and the frozen golden hash. If the engine is ever made "
        "intrinsically reorder-invariant, this xpasses (strict) and the finding "
        "must be revisited."
    ),
)
async def test_full_reorder_invariance_does_not_hold() -> None:
    """Documents that raw-fold reorder-invariance does NOT hold (tracked finding)."""
    # Deterministic, guaranteed-non-identity, causal-class-preserving reorder:
    # move the first audit.event ahead of the opening snapshot.
    reordered = [BASE_TRACE[3], *BASE_TRACE[:3], *BASE_TRACE[4:]]
    assert intra_class_order_preserved(BASE_TRACE, reordered)
    assert reordered != BASE_TRACE

    base_hash = await _hash_for(BASE_TRACE)
    reordered_hash = await _hash_for(reordered)
    assert base_hash == reordered_hash


async def test_base_trace_is_nontrivial() -> None:
    """Sanity: the base trace covers all 4 reducer types."""
    types = {e["event_type"] for e in BASE_TRACE}
    assert types == {"state.snapshot", "memory.event", "action.event", "audit.event"}, (
        f"BASE_TRACE missing reducer coverage: got {types}"
    )
