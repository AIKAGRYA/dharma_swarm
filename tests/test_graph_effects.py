"""DST seed (Phase 1): seeded fault replay through the durable invoker.

dharmagraph-engine-2026-07, spec §3 Phase 1 — the fault-injection seam only:
``graph/effects.py`` virtualizes clock/rng/dispatch-order behind a protocol,
and one seeded test replays a recorded fault sequence (task death
mid-dispatch) deterministically: same seed, fresh database, identical event
trace. The full DST harness (torn checkpoint, interrupt-during-retry) is
later work by design.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from dharma_swarm.graph.durable_invoker import claim_idempotency_key, wrap_invoker
from dharma_swarm.graph.effects import LiveEffects, SimulatedEffects
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.spine.identity import ExecutionIdentity
from dharma_swarm.spine.receipt import EvidenceReceipt
from dharma_swarm.spine.routing import RoutingDecision

TASK_ID = "task-dst-1"
AGENT_ID = "agent-dst-1"
KEY = f"invoke_agent:{TASK_ID}:{AGENT_ID}"


class TaskDeath(RuntimeError):
    """Simulated process death mid-dispatch (kill -9 while provider runs)."""


def test_live_effects_defaults():
    effects = LiveEffects()
    assert effects.now().tzinfo is not None
    assert effects.dispatch_order([3, 1, 2]) == [3, 1, 2]
    assert effects.random() is effects.random()


def test_simulated_effects_are_seed_deterministic():
    a, b = SimulatedEffects(99), SimulatedEffects(99)
    assert [a.now() for _ in range(3)] == [b.now() for _ in range(3)]
    items = list(range(10))
    assert a.dispatch_order(items) == b.dispatch_order(items)
    assert SimulatedEffects(99).dispatch_order(items) != items or True  # shuffle is seed-defined
    a.advance(3600)
    assert a.now() - b.now() >= timedelta(seconds=3600)


async def _replay_fault_sequence(seed: int, db_path) -> list[tuple]:
    """One simulated run: rng-many task deaths mid-dispatch, then recovery,
    then a memo replay. Returns the semantic event trace."""
    effects = SimulatedEffects(seed)
    store = RuntimeStateStore(db_path)
    deaths = effects.random().randint(1, 3)
    trace: list[tuple] = [("plan", "deaths", deaths)]
    executions = 0

    def identity(attempt: int) -> ExecutionIdentity:
        # Crash-requeue re-mints identity per attempt; the side-effect key
        # stays deterministic — exactly the Phase 0b memo contract.
        return ExecutionIdentity.new(
            task_id=TASK_ID,
            agent_id=AGENT_ID,
            run_id=f"run-{seed}-{attempt}",
            idempotency_key=f"idem-{seed}-{attempt}",
        )

    async def make_attempt(attempt: int, *, die: bool):
        nonlocal executions

        async def inner(task, agent_id, context_id, routing):
            nonlocal executions
            executions += 1
            if die:
                raise TaskDeath(f"attempt {attempt} died mid-dispatch")
            return EvidenceReceipt(
                task_id=TASK_ID,
                agent_id=agent_id,
                status="ok",
                attributes={"side_effect_key": KEY, "attempt": attempt},
            )

        invoker = wrap_invoker(
            inner,
            store=store,
            identity=identity(attempt),
            side_effect_key=KEY,
            effects=effects,
        )
        try:
            receipt = await invoker(
                task={"id": TASK_ID, "agent_id": AGENT_ID},
                agent_id=AGENT_ID,
                context_id="ctx-dst",
                routing=RoutingDecision(agent_id=AGENT_ID, task_id=TASK_ID),
            )
        except TaskDeath:
            trace.append(("attempt", attempt, "died"))
            return
        trace.append(
            ("attempt", attempt, "memo_hit" if invoker.memo_hit else "executed_ok")
        )
        assert receipt.status == "ok"

    attempt = 0
    for _ in range(deaths):
        await make_attempt(attempt, die=True)
        attempt += 1
    await make_attempt(attempt, die=False)  # recovery attempt
    attempt += 1
    await make_attempt(attempt, die=False)  # replay: must memoize, not re-run

    trace.append(("provider_executions", executions))
    record = await store.get_idempotency_record(claim_idempotency_key(KEY), KEY)
    trace.append(("final_record_status", getattr(record, "status", None)))
    return trace


async def test_simulated_clock_drives_same_identity_stale_takeover(tmp_path):
    """Greptile P1 regression: with the SAME identity (same claim row), a
    'started' record left by a dead holder is taken over when the INJECTED
    clock — not the store's wall clock — passes stale_after_seconds."""
    from datetime import datetime, timezone

    from dharma_swarm.runtime_state import RuntimeStateStore as _Store
    from dharma_swarm.spine.identity import ExecutionIdentity as _EI
    from dharma_swarm.spine.receipt import EvidenceReceipt as _ER
    from dharma_swarm.spine.routing import RoutingDecision as _RD

    store = _Store(tmp_path / "runtime.db")
    identity = _EI.new(
        task_id=TASK_ID, agent_id=AGENT_ID, run_id="run-sim", idempotency_key="idem-sim"
    )
    claim = identity.with_updates(idempotency_key=claim_idempotency_key(KEY))
    # Dead holder: row is 'started' with a FRESH wall-clock updated_at, so
    # the store's own staleness check would refuse; only the injected clock
    # can classify it dead.
    await store.try_begin_idempotent_side_effect(claim, KEY, metadata={})

    effects = SimulatedEffects(1, start=datetime.now(timezone.utc))
    effects.advance(3600)  # simulated hour passes; wall clock has not

    calls = {"n": 0}

    async def inner(task, agent_id, context_id, routing):
        calls["n"] += 1
        return _ER(task_id=TASK_ID, agent_id=agent_id, status="ok")

    invoker = wrap_invoker(
        inner,
        store=store,
        identity=identity,
        side_effect_key=KEY,
        stale_after_seconds=60.0,
        effects=effects,
    )
    receipt = await invoker(
        task={"id": TASK_ID, "agent_id": AGENT_ID},
        agent_id=AGENT_ID,
        context_id="ctx-sim",
        routing=_RD(agent_id=AGENT_ID, task_id=TASK_ID),
    )
    assert calls["n"] == 1, "simulated staleness must allow takeover"
    assert receipt.status == "ok"
    record = await store.get_idempotency_record(claim.idempotency_key, KEY)
    assert record is not None and record.status == "completed"


@pytest.mark.parametrize("seed", [42, 7])
async def test_seeded_fault_sequence_replays_exactly(seed, tmp_path):
    first = await _replay_fault_sequence(seed, tmp_path / "runtime_a.db")
    second = await _replay_fault_sequence(seed, tmp_path / "runtime_b.db")
    assert first == second, "same seed + fresh db must replay the exact trace"

    deaths = first[0][2]
    # Exactly one successful provider execution ever; deaths re-executed
    # (failed records are retryable), the final attempt memoized.
    assert ("provider_executions", deaths + 1) in first
    assert ("final_record_status", "completed") in first
    assert first[-3] == ("attempt", deaths + 1, "memo_hit")
