"""Multi-agent coordination with REAL PersistentAgents over ONE shared governed store.

This is the load-bearing coordination proof for the MULTI-AGENT axis. It builds
TWO genuine ``dharma_swarm.persistent_agent.PersistentAgent`` instances (real
constructors, separate tmp ``state_dir``s, no monkeypatch of the kernel seam),
points them at ONE shared ``KernelRunStore`` via the new default-off
``DHARMA_PERSISTENT_KERNEL_STORE_DIR`` env var (with the existing
``DHARMA_PERSISTENT_KERNEL_GOVERNANCE`` flag ON), and drives their REAL
``PersistentAgent.wake()`` hot-path.

Coordination shape (faithful to the verified concurrency finding):

  * Each agent's governed wake on the SHARED store is ENQUEUE-ONLY — it appends a
    ``persistent_self_wake`` to the shared ``wake_ledger.jsonl`` and never leases.
    (The kernel's ``lease_next_wake`` is a non-atomic read-modify-write whose only
    concurrency guard is the SERVICE-LAYER ``fcntl.flock`` in
    ``run_kernel_daemon_service``; inline-draining a shared store off separate
    locks DOUBLE-LEASES — proven by the control assertion below.)
  * Agent A additionally SPAWNS a subagent-wake into the shared store from its own
    governed envelope (``spawn_subagent_wake`` — enqueue-only, inherited-but-subset
    authority), the explicit parent/child coordination primitive.
  * A SINGLE ``run_kernel_daemon_service`` (one shared ``daemon_service.lock``)
    drains every queued wake EXACTLY ONCE under governance.

Every assertion is on REAL durable artifacts reloaded from a FRESH
``KernelRunStore`` after the drain: per-wake exactly-once lease + terminal +
``attempt == 1``, both agents present in the shared ledger, per-run replay
integrity, and a hash-chained ``verify_wake_ledger() == (True, [])``. No provider
client is constructed and nothing is written outside ``tmp_path``.
"""

from __future__ import annotations

import asyncio
import fcntl
import json
import sys
from collections import Counter
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from dharma_swarm.autonomous_agent import AgentResult
from dharma_swarm.models import AgentRole, ProviderType
from dharma_swarm.operator_core.living_agent_kernel import (
    KernelRunStore,
    LivingAgentKernel,
)
from dharma_swarm.operator_core.living_agent_kernel_service import (
    run_kernel_daemon_service,
)
from dharma_swarm.persistent_agent import PersistentAgent


def _agent(state_dir: Path, *, name: str) -> PersistentAgent:
    return PersistentAgent(
        name=name,
        role=AgentRole.CONDUCTOR,
        provider_type=ProviderType.ANTHROPIC,
        model="claude-opus-4",
        state_dir=state_dir,
        wake_interval_seconds=1800.0,
    )


def _stub_react_loop(agent: PersistentAgent, summary: str) -> AsyncMock:
    """Replace ONLY the AutonomousAgent ReAct loop (the provider-LLM step). The
    PersistentAgent.wake() conductor and the kernel governance seam run for real."""
    react = AsyncMock(
        return_value=AgentResult(
            summary=summary, turns=2, tokens_in=11, tokens_out=7, tool_calls_made=0
        )
    )
    agent._agent.wake = react  # type: ignore[method-assign]
    return react


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# control: the verified finding — separate lock paths DO double-lease.
# ---------------------------------------------------------------------------


def test_control_separate_lock_paths_double_lease_a_shared_store(tmp_path):
    """The invariant the design relies on: ``lease_next_wake`` is a NON-ATOMIC
    read-modify-write (read the whole ledger -> pick the first queued -> append a
    'leased' row), with NO kernel-level lock. Two drainers that race that window
    on ONE shared store — NOT serialized through the single service flock — both
    pick the SAME queued wake and DOUBLE-LEASE.

    This deterministically reproduces, in-process, the mechanism the dedicated
    subprocess race test (``test_living_agent_kernel_race_double_lease.py``)
    proves under genuine OS concurrency. It is the failure the enqueue-only +
    single-flock-drain design exists to prevent: it is WHY shared coordination
    must drain through exactly one ``run_kernel_daemon_service`` flock and the
    agents only ever enqueue.
    """
    import threading

    from dharma_swarm.operator_core.living_agent_kernel import (
        AgentRunEnvelope,
        KernelRunStore as _Store,
        KernelTask,
        TriggerEnvelope,
    )

    store_dir = tmp_path / "kernel"
    kernel = LivingAgentKernel(store=_Store(store_dir), workspace_root=tmp_path)
    env = AgentRunEnvelope(
        agent_uid="codex_composer",
        task=KernelTask(text="contended work"),
        trigger=TriggerEnvelope(source="persistent_self_wake", correlation_id="corr-ctl"),
    )
    kernel.enqueue_wake(env, wake_id="wake-contended")

    # A barrier patched INTO the read-modify-write window: both drainers complete
    # the ledger READ (pick the same queued wake) BEFORE either APPENDS its lease,
    # exactly the non-atomic window. No shared service flock guards it here.
    both_read = threading.Barrier(2)
    real_append = _Store._append_wake_record

    def _append_after_barrier(self, record):
        if record.status == "leased":
            both_read.wait(timeout=5)
        return real_append(self, record)

    leases: dict[str, KernelRunStore] = {}

    def _drain(owner: str) -> None:
        store = _Store(store_dir)
        store._append_wake_record = _append_after_barrier.__get__(store, _Store)  # type: ignore[attr-defined]
        leased = store.lease_next_wake(lease_owner=owner)
        if leased is not None:
            leases[owner] = leased

    t_a = threading.Thread(target=_drain, args=("drainer-a",))
    t_b = threading.Thread(target=_drain, args=("drainer-b",))
    t_a.start()
    t_b.start()
    t_a.join(timeout=10)
    t_b.join(timeout=10)

    # Both drainers leased — and they leased the SAME wake: the double-lease the
    # single-flock-drain design must (and does) prevent.
    assert set(leases) == {"drainer-a", "drainer-b"}
    assert leases["drainer-a"].wake_id == leases["drainer-b"].wake_id == "wake-contended"


# ---------------------------------------------------------------------------
# coordination: two REAL agents -> one shared governed store -> single flock drain.
# ---------------------------------------------------------------------------


def test_two_real_persistent_agents_coordinate_through_one_shared_governed_store(tmp_path):
    sys.modules.pop("anthropic", None)
    sys.modules.pop("openai", None)

    shared = tmp_path / "shared"
    shared_kernel_dir = shared / "living_agent_kernel"

    agent_a = _agent(tmp_path / "agent_a", name="conductor_a")
    agent_b = _agent(tmp_path / "agent_b", name="conductor_b")
    react_a = _stub_react_loop(agent_a, summary="A surveyed the control surface")
    react_b = _stub_react_loop(agent_b, summary="B reconciled receipts")

    task_a = "investigate runtime drift in the control surface"
    task_b = "reconcile control-surface rows against the ledger"

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DHARMA_PERSISTENT_KERNEL_GOVERNANCE", "1")
        mp.setenv("DHARMA_PERSISTENT_KERNEL_STORE_DIR", str(shared))

        # Both real agents wake. Each governed wake ENQUEUE-ONLY appends a
        # persistent_self_wake to the SHARED store (never leases) -> no race.
        info_a = asyncio.run(agent_a.wake(injected_task=task_a))
        info_b = asyncio.run(agent_b.wake(injected_task=task_b))

        # Both agents still completed their OWN task (observe+govern never replaces it).
        react_a.assert_awaited_once_with(task_a)
        react_b.assert_awaited_once_with(task_b)
        assert info_a["success"] is True and info_b["success"] is True
        assert info_a["kernel_governed"] is True and info_b["kernel_governed"] is True
        # The shared-store path returns enqueue-only facts (queued, not yet run).
        assert info_a["kernel_status"] == "queued"
        assert info_b["kernel_status"] == "queued"

        # Agent A spawns a SUBAGENT-wake into the SHARED store from its own governed
        # envelope — the explicit parent/child coordination primitive (enqueue-only).
        pre_drain = KernelRunStore(shared_kernel_dir)
        parent_record = pre_drain.latest_wake_records()[info_a["kernel_wake_id"]]
        coord_kernel = LivingAgentKernel(
            store=KernelRunStore(shared_kernel_dir), workspace_root=agent_a.state_dir
        )
        dispatch = coord_kernel.spawn_subagent_wake(
            parent_record.envelope,
            child_agent_uid="conductor_a_sub",
            task_text="Review A's coordinated finding for B",
            role="reviewer",
            allowed_files=list(parent_record.envelope.authority.allowed_files),
            requested_tools=["session_status"],
            tool_calls=[{"name": "session_status", "arguments": {}}],
            wake_id=f"subagent:{agent_a.name}:{info_a['kernel_wake_id']}",
        )
        assert dispatch.status == "spawned"

        # Three wakes are now QUEUED in the shared store; none has been leased.
        queued = KernelRunStore(shared_kernel_dir).latest_wake_records()
        assert {r.status for r in queued.values()} == {"queued"}
        assert len(queued) == 3

        # ONE flock-protected daemon service drains the shared store. Its lock
        # defaults to <shared>/daemon_service.lock — one shared lock path.
        drain = run_kernel_daemon_service(
            store_dir=shared_kernel_dir,
            workspace_root=shared,
            daemon_id="shared-coord-drain",
            cycles=6,
            max_wakes=3,
            interval_seconds=0,
        )

    assert drain.status == "completed"

    # ---- proof: reload from a FRESH store; exactly-once + replay integrity ----
    fresh = KernelRunStore(shared_kernel_dir)
    latest = fresh.latest_wake_records()

    wake_a = info_a["kernel_wake_id"]
    wake_b = info_b["kernel_wake_id"]
    wake_sub = dispatch.wake_id

    # Every queued wake reached a terminal status, leased EXACTLY ONCE.
    for wid in (wake_a, wake_b, wake_sub):
        record = latest[wid]
        assert record.status in {"completed", "review"}, f"{wid} not terminal: {record.status}"
        assert record.attempt == 1, f"{wid} re-attempted: {record.attempt}"
        # durable receipt: a proof entry + replay integrity for the run behind it.
        replay = fresh.replay_run(record.run_id)
        assert replay.proof_entries, f"missing proof entry for {wid}"
        assert replay.integrity_ok is True
        assert replay.integrity_errors == []

    # Exactly one 'leased' transition per wake in the shared ledger -> no double-lease.
    rows = _read_jsonl(shared_kernel_dir / "wake_ledger.jsonl")
    leased = Counter(r["wake_id"] for r in rows if r["status"] == "leased")
    for wid in (wake_a, wake_b, wake_sub):
        assert leased[wid] == 1, f"{wid} double-leased: {dict(leased)}"

    # BOTH agents' activity landed in the SHARED ledger.
    agent_uids = {latest[wid].envelope.agent_uid for wid in (wake_a, wake_b)}
    assert agent_uids == {"conductor_a", "conductor_b"}
    # The subagent inherited A as its parent and writes its own lessons namespace.
    sub_record = latest[wake_sub]
    assert sub_record.envelope.trigger.parent_run_id == parent_record.run_id
    assert sub_record.envelope.agent_uid == "conductor_a_sub"

    # durable proof ledger references BOTH agents' runs.
    proof_rows = _read_jsonl(shared_kernel_dir / "proof_ledger.jsonl")
    proven_agents = {
        r["agent_uid"]
        for r in proof_rows
        if r["run_id"] in {latest[wake_a].run_id, latest[wake_b].run_id}
    }
    assert proven_agents == {"conductor_a", "conductor_b"}

    # full hash-chained ledger verify on a fresh reload after the shared drain.
    assert fresh.verify_wake_ledger() == (True, [])
    assert fresh.verify_daemon_cycle_ledger() == (True, [])

    # nothing leaked into either agent's OWN state_dir kernel store (shared-only).
    assert not (agent_a.state_dir / "living_agent_kernel").exists()
    assert not (agent_b.state_dir / "living_agent_kernel").exists()


# ---------------------------------------------------------------------------
# default-off: the per-agent (non-shared) governance path still works unchanged.
# ---------------------------------------------------------------------------


def test_per_agent_governance_still_works_when_shared_dir_unset(tmp_path):
    """With ``DHARMA_PERSISTENT_KERNEL_STORE_DIR`` UNSET (only the existing
    governance flag on), the agent roots its store per-agent and inline-completes
    exactly as before — proving the non-shared path is unbroken and byte-identical."""
    sys.modules.pop("anthropic", None)
    sys.modules.pop("openai", None)

    agent = _agent(tmp_path / "agent", name="conductor_solo")
    react = _stub_react_loop(agent, summary="solo wake governed per-agent")

    task = "inspect runtime state of the control surface"
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DHARMA_PERSISTENT_KERNEL_GOVERNANCE", "1")
        mp.delenv("DHARMA_PERSISTENT_KERNEL_STORE_DIR", raising=False)
        info = asyncio.run(agent.wake(injected_task=task))

    react.assert_awaited_once_with(task)
    assert info["success"] is True
    assert info["kernel_governed"] is True
    # Inline-completed on the per-agent store: a real terminal status, not "queued".
    assert info["kernel_status"] in ("completed", "review")
    assert "shared" not in info

    # the per-agent store was created under the agent's OWN state_dir, and replays.
    kernel_dir = agent.state_dir / "living_agent_kernel"
    assert kernel_dir.exists()
    run_id = info["kernel_run_id"]
    store = KernelRunStore(kernel_dir)
    replay = store.replay_run(run_id)
    assert replay.integrity_ok is True
    assert store.verify_wake_ledger() == (True, [])
