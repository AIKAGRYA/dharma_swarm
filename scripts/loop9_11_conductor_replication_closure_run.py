#!/usr/bin/env python3
"""Bounded replay for Loop 9 (Conductors) and Loop 11 (Replication Monitor).

This intentionally does not call an external LLM provider. The replay proves the
local cybernetic edges that were still missing:

* Loop 9: conductor-visible signals are read by a PersistentAgent wake cycle,
  converted into an action, persisted to witness/stigmergy/memory state, and
  then the conductor scheduler reads its changed cron state on a later tick.
* Loop 11: a durable replication proposal is read by the monitor-facing
  ReplicationProtocol API, processed through the checkpoint-gated pipeline,
  materialized into child/probation/roster state, and then a later monitor read
  sees the changed proposal/roster state.

The emitted receipts match the generic cybernetics-codex closure predicate:
cycles > 0, real_data true, all five transitions receipted, adapt before !=
after with fed_forward true, and empty tick_errors.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.cybernetics_codex_format import sanitize_audit_paths

TRANSITIONS = ("sense", "interpret", "constrain", "act", "adapt")


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_clone(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def _count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


@contextmanager
def _isolated_runtime_env(state_dir: Path) -> Iterator[None]:
    """Point home/default local state at the replay sandbox for this process."""
    old_env = {
        key: os.environ.get(key)
        for key in ("HOME", "DHARMA_HOME", "DHARMA_READ_ONLY_BOOT")
    }
    home_dir = state_dir.parent if state_dir.name == ".dharma" else state_dir
    home_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    os.environ["HOME"] = str(home_dir)
    os.environ["DHARMA_HOME"] = str(state_dir)
    os.environ.setdefault("DHARMA_READ_ONLY_BOOT", "1")
    try:
        yield
    finally:
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@dataclass
class _LocalMemory:
    path: Path
    working: list[dict[str, Any]] = field(default_factory=list)

    async def load(self) -> None:
        if self.path.exists():
            self.working = json.loads(self.path.read_text(encoding="utf-8"))

    async def remember(self, key: str, value: str, importance: float = 0.5) -> None:
        self.working.append(
            {
                "key": key,
                "value": value,
                "importance": importance,
                "remembered_at": _utc_stamp(),
            }
        )

    async def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.working, indent=2) + "\n", encoding="utf-8")


class _LocalConductorExecutor:
    """Deterministic executor for the provider boundary.

    It deliberately does not report served provider/model truth; the receipt is
    only about local conductor state transitions.
    """

    def __init__(self, memory: _LocalMemory) -> None:
        self.memory = memory
        self.tasks: list[str] = []

    async def wake(self, task: str):
        from dharma_swarm.autonomous_agent import AgentResult

        self.tasks.append(task)
        await self.memory.remember(
            "local_executor_action",
            f"bounded conductor action for task: {task[:120]}",
            importance=0.7,
        )
        return AgentResult(
            summary=(
                "Bounded replay conductor action: recorded the sensed signal "
                f"and scheduled follow-up for {task[:120]}"
            ),
            turns=1,
            tokens_in=0,
            tokens_out=0,
            tool_calls_made=0,
            duration_s=0.0,
        )


def _cron_counts(agent: Any) -> dict[str, dict[str, Any]]:
    return {
        row["name"]: {
            "run_count": row["run_count"],
            "interval_s": row["interval_s"],
            "enabled": row["enabled"],
        }
        for row in agent.cron.list_jobs()
    }


async def _run_loop9_conductor_replay(state_dir: Path) -> dict[str, Any]:
    from dharma_swarm.conductors import CONDUCTOR_CODEX_CONFIG
    from dharma_swarm.message_bus import MessageBus
    from dharma_swarm.models import GateDecision
    from dharma_swarm.persistent_agent import PersistentAgent
    from dharma_swarm.stigmergy import StigmergicMark, StigmergyStore
    from dharma_swarm.telos_gates import GateRegistry, TelosGatekeeper

    tick_errors: list[str] = []
    transitions = {name: False for name in TRANSITIONS}
    cycle_detail: list[dict[str, Any]] = []

    stigmergy = StigmergyStore(base_path=state_dir / "stigmergy")
    signal_path = "runtime/conductor_signal.py"
    for idx in range(2):
        await stigmergy.leave_mark(
            StigmergicMark(
                agent=f"loop9-signal-{idx}",
                file_path=signal_path,
                action="write",
                observation=(
                    "replication monitor scheduling pressure requires conductor follow-up"
                ),
                salience=0.86,
                channel="systems",
            )
        )

    bus = MessageBus(state_dir / "db" / "messages.db")
    await bus.init_db()

    agent = PersistentAgent(
        name=CONDUCTOR_CODEX_CONFIG["name"],
        role=CONDUCTOR_CODEX_CONFIG["role"],
        provider_type=CONDUCTOR_CODEX_CONFIG["provider_type"],
        model=CONDUCTOR_CODEX_CONFIG["model"],
        state_dir=state_dir,
        wake_interval_seconds=CONDUCTOR_CODEX_CONFIG["wake_interval_seconds"],
        system_prompt=CONDUCTOR_CODEX_CONFIG["system_prompt"],
        max_turns=CONDUCTOR_CODEX_CONFIG["max_turns"],
    )
    memory = _LocalMemory(state_dir / "agent_memory" / agent.name / "memory.json")
    local_executor = _LocalConductorExecutor(memory)
    agent._agent = local_executor
    agent._stigmergy = stigmergy
    agent._bus = bus

    gatekeeper = TelosGatekeeper(
        registry=GateRegistry(state_dir / "governance" / "gate_proposals.jsonl")
    )
    gate_checks: list[dict[str, Any]] = []

    def _local_gate(task_text: str) -> dict[str, Any]:
        result = gatekeeper.check(
            action=task_text[:100],
            content=task_text,
            think_phase="conductor_wake",
            reflection=f"Loop 9 bounded replay for {agent.name}",
        )
        row = {
            "decision": result.decision.value,
            "reason": result.reason,
            "gate_results": len(result.gate_results),
        }
        gate_checks.append(row)
        return {
            "blocked": result.decision == GateDecision.BLOCK,
            "reason": result.reason,
        }

    agent._check_gate = _local_gate

    witness_path = state_dir / "witness" / f"conductor_{agent.name}.jsonl"
    cron_before = _cron_counts(agent)
    witness_before = _count_jsonl(witness_path)
    hot_paths = await stigmergy.hot_paths(window_hours=6, min_marks=2)
    salient = await stigmergy.high_salience(threshold=0.7, limit=5)

    try:
        wake_result = await agent.wake()
    except Exception as exc:  # pragma: no cover - retained in receipt on failure.
        tick_errors.append(f"wake: {type(exc).__name__}: {exc}")
        wake_result = {"success": False, "error": str(exc)}

    cron_after_wake = _cron_counts(agent)
    witness_after = _count_jsonl(witness_path)
    conductor_marks = await stigmergy.read_marks(
        file_path=f"conductor:{agent.name}",
        limit=10,
    )
    await memory.load()

    later_tick_results = await agent.cron.tick()
    later_scheduler_read = {
        "immediate_second_tick_jobs_fired": len(later_tick_results),
        "suppressed_by_last_run": len(later_tick_results) == 0,
        "queued_tasks_from_cron": agent._task_queue.qsize(),
    }

    interpreted_task = str(wake_result.get("task", ""))
    transitions["sense"] = bool(hot_paths) and bool(salient)
    transitions["interpret"] = (
        wake_result.get("task_source") == "self"
        and "Investigate high-activity path" in interpreted_task
        and signal_path in interpreted_task
    )
    transitions["constrain"] = bool(gate_checks) and not gate_checks[-1]["decision"] == "block"
    transitions["act"] = (
        bool(wake_result.get("success"))
        and witness_after > witness_before
        and bool(conductor_marks)
        and bool(memory.working)
    )
    cron_changed = cron_before != cron_after_wake
    transitions["adapt"] = cron_changed and later_scheduler_read["suppressed_by_last_run"]

    cycle_detail.append(
        {
            "cycle": 1,
            "phase": "conductor_wake",
            "task_source": wake_result.get("task_source"),
            "task": interpreted_task,
            "hot_paths": hot_paths,
            "salient_marks": len(salient),
            "gate_check": gate_checks[-1] if gate_checks else None,
            "witness_entries_before": witness_before,
            "witness_entries_after": witness_after,
            "conductor_marks_written": len(conductor_marks),
            "memory_entries": len(memory.working),
        }
    )
    cycle_detail.append(
        {
            "cycle": 2,
            "phase": "scheduler_later_read",
            **later_scheduler_read,
        }
    )

    fed_forward = transitions["adapt"]
    return {
        "loop": 9,
        "loop_id": "conductors",
        "cycles": len(cycle_detail),
        "real_data": bool(
            transitions["sense"]
            and transitions["act"]
            and witness_path.exists()
            and (state_dir / "stigmergy" / "marks.jsonl").exists()
        ),
        "provider_truth": {
            "external_provider_called": False,
            "served_provider": None,
            "served_model": None,
            "boundary": "local deterministic executor; no provider truth asserted",
        },
        "transitions_receipted": transitions,
        "adapt_proof": {
            "field": "PersistentAgent AgentCronScheduler run_count/last_run state",
            "before": cron_before,
            "after": cron_after_wake,
            "fed_forward": fed_forward,
            "later_cycle_read": later_scheduler_read,
        },
        "tick_errors": tick_errors,
        "sense_evidence": {
            "surface": "StigmergyStore.hot_paths/high_salience",
            "seeded_signal_path": signal_path,
            "hot_paths": hot_paths,
            "salient_marks": len(salient),
        },
        "interpret_evidence": {
            "surface": "PersistentAgent._generate_self_task",
            "task_source": wake_result.get("task_source"),
            "task": interpreted_task,
        },
        "constrain_evidence": {
            "surface": "TelosGatekeeper.check via conductor wake gate",
            "gate_checks": gate_checks,
        },
        "act_evidence": {
            "surface": "PersistentAgent.wake witness/stigmergy/memory writes",
            "witness_path": str(witness_path),
            "witness_entries_after": witness_after,
            "latest_witness": (_read_jsonl(witness_path)[-1] if witness_after else None),
            "conductor_mark_count": len(conductor_marks),
            "memory_entries": len(memory.working),
            "executor_tasks": list(local_executor.tasks),
        },
        "adapt_evidence": {
            "surface": "AgentCronScheduler.tick later scheduling decision",
            "cron_before": cron_before,
            "cron_after_wake": cron_after_wake,
            "later_scheduler_read": later_scheduler_read,
        },
        "later_cycle_read_evidence": later_scheduler_read,
        "cycle_detail": cycle_detail,
        "state_dir": str(state_dir),
        "observed_at": _utc_stamp(),
    }


async def _run_loop11_replication_replay(state_dir: Path) -> dict[str, Any]:
    from dharma_swarm.agent_constitution import DynamicRoster
    from dharma_swarm.agent_registry import AgentRegistry
    from dharma_swarm.dharma_kernel import KernelGuard
    from dharma_swarm.genome_inheritance import GenomeInheritance
    from dharma_swarm.population_control import PopulationController
    from dharma_swarm.replication_protocol import ReplicationProposal, ReplicationProtocol
    from dharma_swarm.telos_gates import GateRegistry, TelosGatekeeper

    tick_errors: list[str] = []
    transitions = {name: False for name in TRANSITIONS}
    cycle_detail: list[dict[str, Any]] = []

    roster = DynamicRoster(state_dir=state_dir)
    registry = AgentRegistry(agents_dir=state_dir / "ginko" / "agents")
    pop_ctrl = PopulationController(
        state_dir=state_dir,
        max_population=8,
        probation_cycles=3,
        agent_registry=registry,
    )
    protocol = ReplicationProtocol(
        state_dir=state_dir,
        config=SimpleNamespace(max_generations=2),
        kernel_guard=KernelGuard(kernel_path=state_dir / "kernel.json"),
        gate_keeper=TelosGatekeeper(
            registry=GateRegistry(state_dir / "governance" / "gate_proposals.jsonl")
        ),
        population_controller=pop_ctrl,
        genome_inheritance=GenomeInheritance(state_dir=state_dir),
        agent_registry=registry,
        dynamic_roster=roster,
    )

    proposal = ReplicationProposal(
        proposed_role="replication monitor closure analyst",
        justification="Loop 11 bounded replay needs a durable child-lifecycle action.",
        capability_gap="loop11 replication monitor closure proof",
        evidence_cycles=[9, 11],
        parent_agent="systems_architect",
        generation=0,
        severity=0.72,
        proposed_spec_delta={
            "domain": "Replication monitor closure verification",
            "prompt_suffix": "Track proposal lifecycle state and probation receipts.",
            "provider": "openrouter_free",
            "model": "local-bounded-replay",
            "wake_interval": 7200.0,
            "spawn_authority": ["replication_auditor"],
        },
        evidence_metadata={
            "source": "scripts/loop9_11_conductor_replication_closure_run.py",
            "bounded_replay": True,
        },
        resource_estimate={"estimated_daily_tokens": 0, "model_cost_per_day": 0.0},
    )
    protocol._persist_proposal(proposal)

    pending_before = protocol.get_pending_proposals()
    roster_before = [spec.name for spec in DynamicRoster(state_dir=state_dir).get_all()]
    proposals_path = state_dir / "replication" / "proposals.jsonl"
    witness_path = state_dir / "witness" / "replication.jsonl"
    witness_before = _count_jsonl(witness_path)

    outcome = None
    if pending_before:
        try:
            outcome = await protocol.run(pending_before[0].model_dump())
        except Exception as exc:  # pragma: no cover - retained in receipt on failure.
            tick_errors.append(f"protocol.run: {type(exc).__name__}: {exc}")
    else:
        tick_errors.append("no pending proposal found before replication run")

    pending_after = protocol.get_pending_proposals()
    loaded_after = protocol.load_proposals()
    materialized = [p for p in loaded_after if p.status == "materialized"]
    child_name = outcome.child_agent_name if outcome else None
    reloaded_roster = DynamicRoster(state_dir=state_dir)
    child_from_roster = reloaded_roster.get(child_name) if child_name else None
    probation_after = PopulationController(state_dir=state_dir).get_all_probation()
    witness_after = _count_jsonl(witness_path)
    witness_events = [row.get("type") for row in _read_jsonl(witness_path)]
    genome_path = (
        state_dir / "replication" / "genomes" / f"{child_name}.json"
        if child_name
        else None
    )

    transitions["sense"] = bool(pending_before) and proposals_path.exists()
    transitions["interpret"] = (
        bool(pending_before)
        and pending_before[0].parent_agent == "systems_architect"
        and pending_before[0].severity >= 0.3
    )
    transitions["constrain"] = (
        bool(outcome)
        and outcome.success
        and outcome.gate_results.get("decision") in {"allow", "review"}
    )
    transitions["act"] = (
        bool(outcome)
        and outcome.success
        and bool(child_name)
        and child_from_roster is not None
        and genome_path is not None
        and genome_path.exists()
        and "M_MATERIALIZED" in witness_events
    )
    later_cycle_read = {
        "pending_before": len(pending_before),
        "pending_after": len(pending_after),
        "materialized_statuses": len(materialized),
        "child_loaded_from_restarted_roster": child_from_roster is not None,
        "probation_loaded_for_child": bool(child_name and child_name in probation_after),
        "witness_events_after": witness_events,
    }
    transitions["adapt"] = (
        later_cycle_read["pending_before"] > later_cycle_read["pending_after"]
        and later_cycle_read["child_loaded_from_restarted_roster"]
        and later_cycle_read["probation_loaded_for_child"]
    )

    before_state = {
        "pending_count": len(pending_before),
        "dynamic_roster_count": max(0, len(roster_before) - 6),
        "witness_entries": witness_before,
    }
    after_state = {
        "pending_count": len(pending_after),
        "materialized_count": len(materialized),
        "child_agent_name": child_name,
        "dynamic_roster_has_child": child_from_roster is not None,
        "probation_has_child": bool(child_name and child_name in probation_after),
        "witness_entries": witness_after,
    }

    cycle_detail.append(
        {
            "cycle": 1,
            "phase": "monitor_read_and_materialize",
            "pending_before": len(pending_before),
            "outcome_success": bool(outcome and outcome.success),
            "child_agent_name": child_name,
            "gate_results": outcome.gate_results if outcome else {},
        }
    )
    cycle_detail.append(
        {
            "cycle": 2,
            "phase": "monitor_later_read",
            **later_cycle_read,
        }
    )

    fed_forward = transitions["adapt"]
    return {
        "loop": 11,
        "loop_id": "replication_monitor",
        "cycles": len(cycle_detail),
        "real_data": bool(
            transitions["sense"]
            and transitions["act"]
            and proposals_path.exists()
            and witness_path.exists()
        ),
        "provider_truth": {
            "external_provider_called": False,
            "served_provider": None,
            "served_model": None,
            "boundary": "ReplicationProtocol local materialization; no provider dispatch",
        },
        "transitions_receipted": transitions,
        "adapt_proof": {
            "field": "ReplicationProtocol durable proposals/dynamic_roster/probation state",
            "before": before_state,
            "after": after_state,
            "fed_forward": fed_forward,
            "later_cycle_read": later_cycle_read,
        },
        "tick_errors": tick_errors,
        "sense_evidence": {
            "surface": "ReplicationProtocol.get_pending_proposals",
            "proposals_path": str(proposals_path),
            "pending_before": [p.model_dump() for p in pending_before],
        },
        "interpret_evidence": {
            "surface": "ReplicationProtocol._validate_proposal",
            "parent_agent": pending_before[0].parent_agent if pending_before else None,
            "severity": pending_before[0].severity if pending_before else None,
            "capability_gap": pending_before[0].capability_gap if pending_before else None,
        },
        "constrain_evidence": {
            "surface": "ReplicationProtocol._assess_need + _check_gates",
            "gate_results": outcome.gate_results if outcome else {},
            "population_cap": 8,
        },
        "act_evidence": {
            "surface": "ReplicationProtocol._materialize",
            "child_agent_name": child_name,
            "child_spec": outcome.child_spec if outcome else None,
            "genome_path": str(genome_path) if genome_path else None,
            "dynamic_roster_path": str(state_dir / "replication" / "dynamic_roster.json"),
            "witness_events": witness_events,
        },
        "adapt_evidence": {
            "surface": "later monitor reads proposals, roster, probation from disk",
            "before": before_state,
            "after": after_state,
            "later_cycle_read": later_cycle_read,
        },
        "later_cycle_read_evidence": later_cycle_read,
        "cycle_detail": cycle_detail,
        "state_dir": str(state_dir),
        "observed_at": _utc_stamp(),
    }


def _receipt_path(receipt_dir: Path, loop_number: int, slug: str) -> Path:
    return receipt_dir / f"{datetime.now(timezone.utc):%Y-%m-%d}_loop{loop_number}_{slug}_closure.json"


def _write_receipt(path: Path, receipt: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    output = sanitize_audit_paths(_json_clone(receipt))
    path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _closed_by_generic_predicate(receipt: dict[str, Any]) -> bool:
    return (
        int(receipt.get("cycles") or 0) > 0
        and bool(receipt.get("real_data"))
        and all(bool((receipt.get("transitions_receipted") or {}).get(t)) for t in TRANSITIONS)
        and bool((receipt.get("adapt_proof") or {}).get("fed_forward"))
        and (receipt.get("adapt_proof") or {}).get("before")
        != (receipt.get("adapt_proof") or {}).get("after")
        and not (receipt.get("tick_errors") or [])
    )


async def run_replay_async(receipt_dir: Path, state_dir: Path) -> dict[str, dict[str, Any]]:
    with _isolated_runtime_env(state_dir):
        loop9 = await _run_loop9_conductor_replay(state_dir)
        loop11 = await _run_loop11_replication_replay(state_dir)

    paths = {
        "loop9": _receipt_path(receipt_dir, 9, "conductor"),
        "loop11": _receipt_path(receipt_dir, 11, "replication_monitor"),
    }
    _write_receipt(paths["loop9"], loop9)
    _write_receipt(paths["loop11"], loop11)
    return {
        "loop9": {"path": str(paths["loop9"]), "receipt": loop9},
        "loop11": {"path": str(paths["loop11"]), "receipt": loop11},
    }


def run_replay(receipt_dir: Path, state_dir: Path) -> dict[str, dict[str, Any]]:
    return asyncio.run(run_replay_async(receipt_dir=receipt_dir, state_dir=state_dir))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--receipt-dir",
        type=Path,
        default=REPO_ROOT / "reports" / "loop_closure" / "cybernetics_codex",
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=None,
        help=(
            "isolated Dharma state dir for replay; defaults to a new durable "
            "temporary home under /tmp"
        ),
    )
    args = parser.parse_args(argv)

    state_dir = args.state_dir
    if state_dir is None:
        home_dir = Path(tempfile.mkdtemp(prefix="loop9_11_closure_home_"))
        state_dir = home_dir / ".dharma"
    state_dir.mkdir(parents=True, exist_ok=True)

    result = run_replay(receipt_dir=args.receipt_dir, state_dir=state_dir)
    summary = {
        key: {
            "path": value["path"],
            "closed_by_generic_predicate": _closed_by_generic_predicate(value["receipt"]),
            "tick_errors": value["receipt"].get("tick_errors", []),
            "state_dir": value["receipt"].get("state_dir"),
        }
        for key, value in result.items()
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if all(row["closed_by_generic_predicate"] for row in summary.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
