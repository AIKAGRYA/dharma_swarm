"""End-to-end WIRE-IN proof: a REAL PersistentAgent task is governed by the kernel.

This is the load-bearing integration test for the WIRE-IN axis. It instantiates a
genuine ``dharma_swarm.persistent_agent.PersistentAgent`` (real constructor, tmp
``state_dir``, no monkeypatch), sources a task from the agent's OWN surface
(``accept_task`` drained from ``_task_queue``, and separately ``_generate_self_task``),
and routes it through the full kernel seam:

    build_persistent_wake_payload  ->  normalize_wake_source
      ->  kernel.wake(envelope, lease_owner=agent.name)   (enqueue + lease + run)
      ->  closeback_source_wake(wake_record, result)

The assertions are on REAL durable artifacts read back from disk: the proof ledger
entry, the wake-ledger record, the persistent-self-wake witness receipt, and replay
integrity. No provider client is constructed and nothing is written outside the tmp
run-dir.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

from dharma_swarm.models import AgentRole, ProviderType
from dharma_swarm.operator_core.governed_work_admission import WorkKind
from dharma_swarm.operator_core.living_agent_kernel import (
    KernelRunStore,
    LivingAgentKernel,
)
from dharma_swarm.operator_core.living_agent_kernel_persistent_adapter import (
    build_persistent_wake_payload,
)
from dharma_swarm.persistent_agent import PersistentAgent


def _agent(state_dir: Path, *, name: str = "conductor_e2e") -> PersistentAgent:
    return PersistentAgent(
        name=name,
        role=AgentRole.CONDUCTOR,
        provider_type=ProviderType.ANTHROPIC,
        model="claude-opus-4",
        state_dir=state_dir,
        wake_interval_seconds=1800.0,
    )


def _kernel(tmp_path: Path) -> tuple[LivingAgentKernel, Path]:
    base = tmp_path / "kernel"
    kernel = LivingAgentKernel(
        store=KernelRunStore(base),
        workspace_root=tmp_path,
        persist=True,
    )
    return kernel, base


def _accepted_task(agent: PersistentAgent, task: str) -> str:
    """Drive the REAL agent surface: accept_task -> _task_queue, then drain it."""
    asyncio.run(agent.accept_task(task))
    return agent._task_queue.get_nowait()


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _tree_files(root: Path) -> set[Path]:
    return {p.resolve() for p in root.rglob("*") if p.is_file()}


# -- unit -------------------------------------------------------------------


def test_payload_carries_exact_task_the_real_agent_produced(tmp_path):
    """The task handed to build_persistent_wake_payload is the EXACT value the real
    agent's own task-generation surface produced - proving the wire is TO the agent,
    not a string literal."""
    agent = _agent(tmp_path / "agent")

    # _generate_self_task is the agent's own no-LLM, network-free task generator.
    generated = agent._generate_self_task([("dharma_swarm/swarm.py", 9)], [])
    payload_gen = build_persistent_wake_payload(agent, task=generated)
    assert payload_gen["task"] == generated
    assert payload_gen["task"] == "Investigate high-activity path: dharma_swarm/swarm.py (9 marks in 6h)"

    # accept_task -> _task_queue -> drained is the orchestrator-injection surface.
    drained = _accepted_task(agent, "reconcile control surface rows")
    payload_q = build_persistent_wake_payload(agent, task=drained)
    assert payload_q["task"] == drained == "reconcile control surface rows"
    assert payload_q["agent_uid"] == agent.name


# -- integration ------------------------------------------------------------


def test_real_persistent_agent_task_governed_end_to_end(tmp_path):
    agent = _agent(tmp_path / "agent")
    kernel, base = _kernel(tmp_path)

    task = _accepted_task(agent, "investigate runtime drift in control surface")
    payload = build_persistent_wake_payload(agent, task=task)

    envelope = kernel.normalize_wake_source("persistent_self_wake", payload)
    assert envelope.trigger.source == "persistent_self_wake"
    assert envelope.agent_uid == agent.name
    assert agent.name != "persistent_agent"  # real name, not the normalize fallback
    assert envelope.task.text == task
    assert envelope.authority.work_kind == WorkKind.READ_ONLY
    assert envelope.authority.autonomy_level == "manual"

    execution = kernel.wake(envelope, lease_owner=agent.name)
    assert type(execution).__name__ == "KernelWakeExecution"
    result = execution.result
    assert result is not None
    assert type(result).__name__ == "KernelRunResult"
    assert result.run_id == envelope.run_id
    assert result.status in ("completed", "review")
    assert result.status != "failed"
    assert result.did_persist is True
    assert result.runtime_truth_packet
    assert result.replay_ref.get("integrity_ok") is True

    # durable proof ledger on disk references THIS run.
    proof_path = base / "proof_ledger.jsonl"
    assert proof_path.exists()
    proof_rows = _read_jsonl(proof_path)
    matching_proof = [r for r in proof_rows if r["run_id"] == envelope.run_id]
    assert len(matching_proof) >= 1
    assert matching_proof[0]["agent_uid"] == agent.name

    # durable wake ledger on disk has a record for this wake/run.
    wake_path = base / "wake_ledger.jsonl"
    assert wake_path.exists()
    wake_rows = _read_jsonl(wake_path)
    matching_wake = [r for r in wake_rows if r["run_id"] == envelope.run_id]
    assert matching_wake
    assert {r["envelope"]["agent_uid"] for r in matching_wake} == {agent.name}

    # the persisted proof entry and the wake record reference the SAME run + agent.
    assert matching_proof[0]["run_id"] == matching_wake[0]["run_id"] == envelope.run_id

    # closeback writes a real persistent-self-wake witness receipt.
    closeback = kernel.closeback_source_wake(
        execution.wake_record, result, source_root=agent.state_dir
    )
    assert type(closeback).__name__ == "KernelSourceCloseback"
    assert closeback.source == "persistent_self_wake"
    assert closeback.status in ("closed", "recorded")

    witness_path = agent._witness_log
    assert witness_path.exists()
    witness_rows = _read_jsonl(witness_path)
    receipt = [r for r in witness_rows if r.get("run_id") == envelope.run_id]
    assert receipt, "expected a self-wake witness receipt for this run"
    assert receipt[0]["agent_uid"] == agent.name
    assert receipt[0]["status"] == result.status


def test_generated_self_task_routes_identically(tmp_path):
    """The agent's OTHER real task surface (_generate_self_task) routes the same way."""
    agent = _agent(tmp_path / "agent", name="conductor_gen")
    kernel, base = _kernel(tmp_path)

    task = agent._generate_self_task([], [])  # fallback review task, still real
    payload = build_persistent_wake_payload(agent, task=task)
    envelope = kernel.normalize_wake_source("persistent_self_wake", payload)
    execution = kernel.wake(envelope, lease_owner=agent.name)

    assert execution.result is not None
    assert execution.result.run_id == envelope.run_id
    assert execution.result.status != "failed"
    proof_rows = _read_jsonl(base / "proof_ledger.jsonl")
    assert any(r["run_id"] == envelope.run_id for r in proof_rows)
    assert envelope.task.text == task


# -- adversarial ------------------------------------------------------------


def test_apply_patch_under_manual_authority_is_denied_and_recorded(tmp_path):
    """A real agent payload requesting apply_patch under default manual/read-only
    authority is DENIED, the run does not complete, and the denial is durably
    recorded in the proof ledger."""
    agent = _agent(tmp_path / "agent")
    kernel, base = _kernel(tmp_path)

    task = _accepted_task(agent, "try to write a patch")
    payload = build_persistent_wake_payload(agent, task=task)
    payload["tool_calls"] = [{"name": "apply_patch", "arguments": {"patch": "diff"}}]

    envelope = kernel.normalize_wake_source("persistent_self_wake", payload)
    assert envelope.authority.work_kind == WorkKind.READ_ONLY  # not promoted

    execution = kernel.wake(envelope, lease_owner=agent.name)
    result = execution.result
    assert result is not None
    assert result.status == "blocked"

    denied = [r for r in result.tool_results if r.tool_name == "apply_patch"]
    assert denied and denied[0].status == "denied"
    assert denied[0].denial_reason

    # the denial is durably recorded in the proof ledger for this run.
    proof_rows = _read_jsonl(base / "proof_ledger.jsonl")
    proof = [r for r in proof_rows if r["run_id"] == envelope.run_id]
    assert proof and proof[0]["status"] == "blocked"


def test_malformed_agent_payload_rejected_before_any_proof_entry(tmp_path):
    """An empty-name agent is rejected at the adapter boundary, before the kernel
    runs - so NO proof entry is ever emitted."""
    kernel, base = _kernel(tmp_path)

    class EmptyNameAgent:
        name = "   "
        wake_interval = 60.0
        _witness_log = tmp_path / "w.jsonl"

    with pytest.raises(ValueError, match="non-empty agent.name"):
        build_persistent_wake_payload(EmptyNameAgent(), task="real task")

    # nothing was enqueued or proven - the proof ledger never came into existence.
    assert not (base / "proof_ledger.jsonl").exists()
    assert not (base / "wake_ledger.jsonl").exists()


def test_witness_log_outside_source_root_yields_blocked_closeback(tmp_path):
    """A real run whose witness log resolves OUTSIDE the closeback source_root is
    blocked with a recorded reason (no receipt leaks outside the tree)."""
    agent = _agent(tmp_path / "agent")
    kernel, base = _kernel(tmp_path)

    task = _accepted_task(agent, "inspect runtime")
    payload = build_persistent_wake_payload(agent, task=task)
    envelope = kernel.normalize_wake_source("persistent_self_wake", payload)
    execution = kernel.wake(envelope, lease_owner=agent.name)

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    closeback = kernel.closeback_source_wake(
        execution.wake_record, execution.result, source_root=elsewhere
    )
    assert closeback.status == "blocked"
    assert closeback.reason == "persistent_self_wake_witness_log_outside_source_root"


def test_no_provider_client_and_no_writes_outside_tmp(tmp_path):
    """ZERO network calls / no provider client, and every wake/proof/witness write
    stays inside the tmp tree."""
    sys.modules.pop("anthropic", None)
    sys.modules.pop("openai", None)

    agent = _agent(tmp_path / "agent")
    kernel, base = _kernel(tmp_path)

    before = _tree_files(tmp_path)
    task = _accepted_task(agent, "inspect runtime state")
    payload = build_persistent_wake_payload(agent, task=task)
    envelope = kernel.normalize_wake_source("persistent_self_wake", payload)
    execution = kernel.wake(envelope, lease_owner=agent.name)
    kernel.closeback_source_wake(
        execution.wake_record, execution.result, source_root=agent.state_dir
    )

    assert "anthropic" not in sys.modules
    assert "openai" not in sys.modules

    after = _tree_files(tmp_path)
    new_files = after - before
    assert new_files, "expected durable artifacts to be written"
    for path in new_files:
        assert tmp_path.resolve() in path.parents, f"write leaked outside tmp: {path}"

    # the load-bearing durable artifacts all live under tmp.
    assert (base / "proof_ledger.jsonl").resolve() in after
    assert (base / "wake_ledger.jsonl").resolve() in after
    assert agent._witness_log.resolve() in after
