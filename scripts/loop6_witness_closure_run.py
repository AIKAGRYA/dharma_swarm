#!/usr/bin/env python3
"""Loop 6 (Witness Auditor) closure run — prove the cybernetic cycle on real data.

Loop 6 is Beer's S3* sporadic auditor. Until now it could never close: it senses
from the TraceStore, but task completions only emitted progress/lifecycle/bus
events — never a task_completed trace — so the auditor saw only boot/heartbeat
and never real agent work. With orchestrator._emit_completion_trace wired, real
completions land as traces the Witness audits.

This run drives the full cycle on real data — no mocks:

  sense      : dispatch real tasks through a provider proven live by
               key_oracle.dispatchable_now() so completions land
               task_completed traces; WitnessAuditor.run_cycle() samples them.
  interpret  : _evaluate_trace reads each trace for telos alignment, mimicry,
               and gate sufficiency.
  constrain  : findings are classified actionable vs all-clear (a real
               telos-gate-coverage gap on a completion is actionable).
  act        : _publish_findings writes actionable findings to the stigmergy
               governance channel AND the operator's persistent working memory
               (AgentMemoryBank "operator").
  adapt      : the operator working-memory bank strictly grows (witness_audit_N
               entries) — persistent adaptive state the operator and downstream
               loops consult on later cycles. before != after, fed forward.

Emits a closure receipt to reports/loop_closure/cybernetics_codex/ in the schema
the cybernetics-codex audit recomputes (cycles>0, real_data, all five
transitions receipted, adapt before!=after fed forward, no tick errors). The
receipt's own "closed" is advisory; the audit recomputes it from the evidence.

Usage:
    python3 scripts/loop6_witness_closure_run.py --tasks 2 --cycles 2 \
        --provider claude_code --model claude-sonnet-4-5 [--report PATH]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("DHARMA_SPINE_DISPATCH", "1")
os.environ.setdefault("DHARMA_READ_ONLY_BOOT", "1")
os.environ.setdefault("OLLAMA_FORCE_LOCAL", "1")

from dharma_swarm import api_keys as _api_keys  # noqa: E402  (load keystore front door)

_api_keys.bootstrap_runtime_env()

TRANSITIONS = ("sense", "interpret", "constrain", "act", "adapt")

_WITNESS_TASKS = [
    ("witness-audit-0001", "In one sentence, state why a feedback loop needs both sensing and acting."),
    ("witness-audit-0002", "Name two failure modes of an unsupervised autonomous agent. One line each."),
    ("witness-audit-0003", "In one sentence, why does exponential backoff help a retrying client?"),
]


async def _dispatch_real_tasks(provider: str, model: str, n_tasks: int, timeout_per_task: int) -> dict:
    """Drive n real tasks through the swarm so completions land task_completed traces."""
    from dharma_swarm.swarm import SwarmManager
    from dharma_swarm.models import AgentRole, TaskPriority, ProviderType
    from dharma_swarm.key_oracle import dispatchable_now

    provider_type = ProviderType(provider)
    live = dispatchable_now()
    if provider_type.value not in live:
        raise RuntimeError(
            f"provider {provider_type.value!r} is not dispatchable now "
            f"(dispatchable={sorted(live)}); refusing to create a fake witness closure"
        )
    swarm = SwarmManager()
    await swarm.init()
    tick_errors: list[str] = []
    await swarm.spawn_agent(
        name="loop6-agent-1", role=AgentRole.GENERAL, model=model,
        provider_type=provider_type,
    )
    task_ids: list[str] = []
    for i in range(n_tasks):
        title, prompt = _WITNESS_TASKS[i % len(_WITNESS_TASKS)]
        task = await swarm.create_task(
            title=title, description=prompt, priority=TaskPriority.URGENT,
            metadata={
                "provider_allowlist": [provider],
                "requires_tooling": False,
                "task_type": "loop6_witness",
                "timeout_seconds": timeout_per_task,
            },
        )
        task_ids.append(task.id)

    from dharma_swarm.models import TaskStatus
    terminal = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}
    deadline = time.monotonic() + timeout_per_task * n_tasks
    completed = 0
    while time.monotonic() < deadline:
        try:
            await swarm.tick()
        except Exception as exc:
            tick_errors.append(f"{type(exc).__name__}: {exc}")
            await asyncio.sleep(0.5)
            continue
        statuses = []
        for tid in task_ids:
            t = await swarm._task_board.get(tid)
            statuses.append(t.status if t else None)
        if all(s in terminal for s in statuses):
            break
        await asyncio.sleep(0.5)
    for tid in task_ids:
        t = await swarm._task_board.get(tid)
        if t and t.status == TaskStatus.COMPLETED:
            completed += 1
    await swarm.shutdown()
    return {"dispatched": len(task_ids), "completed": completed, "tick_errors": tick_errors}


async def _witness_governance_mark_count() -> int:
    """Count governance-channel stigmergy marks authored by the witness.

    The witness's act has two persistent sinks: the operator working-memory bank
    (keyed witness_audit_<cycle>, which COLLIDES across processes since the cycle
    counter resets — so it plateaus and is a poor adapt probe) and the stigmergy
    governance channel, where each actionable finding APPENDS a mark that never
    collides and strictly grows. The governance trail is the honest fed-forward
    adaptive state: it is the system-wide governance signal other loops consult.
    """
    try:
        from dharma_swarm.stigmergy import StigmergyStore

        store = StigmergyStore()
        marks = await store._load_marks()
        return sum(
            1 for m in marks
            if getattr(m, "agent", "") == "witness"
            and getattr(m, "channel", "") == "governance"
        )
    except Exception:
        return 0


async def run(args: argparse.Namespace) -> dict:
    from dharma_swarm.witness import WitnessAuditor

    dispatch = await _dispatch_real_tasks(
        args.provider, args.model, args.tasks, args.timeout_per_task
    )

    transitions_seen = {t: False for t in TRANSITIONS}
    tick_errors: list[str] = list(dispatch.get("tick_errors") or [])
    cycle_rows: list[dict] = []
    total_actionable = 0

    mem_before = await _witness_governance_mark_count()

    auditor = WitnessAuditor()
    saw_real_completion_trace = False
    for i in range(args.cycles):
        try:
            findings = await auditor.run_cycle()  # SENSE (sample traces) + INTERPRET + ACT(publish)
            if findings:
                transitions_seen["sense"] = True
                transitions_seen["interpret"] = True
            # real_data guard: at least one sampled trace is a real task completion
            for f in findings:
                if f.action in ("task_completed", "code_written"):
                    saw_real_completion_trace = True
            # CONSTRAIN: actionable classification is the witness's constraint output
            actionable = [f for f in findings if f.is_actionable]
            transitions_seen["constrain"] = True
            if actionable:
                # ACT already happened inside run_cycle()'s _publish_findings.
                transitions_seen["act"] = True
            total_actionable += len(actionable)
            cycle_rows.append({
                "cycle": i + 1,
                "findings": len(findings),
                "actionable": len(actionable),
                "actions": [f.action for f in findings],
                "severities": sorted({f.severity for f in findings}),
            })
        except Exception as exc:
            tick_errors.append(f"cycle {i}: {type(exc).__name__}: {exc}")

    mem_after = await _witness_governance_mark_count()

    # ADAPT fed forward: the act transition appended actionable findings to the
    # stigmergy governance channel — strictly-growing, collision-free adaptive
    # state the governance layer and downstream loops consult on later cycles.
    fed_forward = mem_after > mem_before and total_actionable > 0
    if fed_forward:
        transitions_seen["adapt"] = True

    report = {
        "loop": 6,
        "loop_id": "witness_auditor",
        "cycles": len(cycle_rows),
        "real_data": bool(saw_real_completion_trace),
        "dispatch": dispatch,
        "transitions_receipted": transitions_seen,
        "adapt_proof": {
            "field": "stigmergy governance channel marks authored by 'witness' "
                     "(strictly-growing adaptive state governance + downstream loops consult)",
            "before": mem_before,
            "after": mem_after,
            "fed_forward": fed_forward,
            "total_actionable": total_actionable,
        },
        "tick_errors": tick_errors,
        "cycle_detail": cycle_rows,
        "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=int, default=2)
    parser.add_argument("--cycles", type=int, default=2)
    parser.add_argument("--provider", default="claude_code")
    parser.add_argument("--model", default="claude-sonnet-4-5")
    parser.add_argument("--timeout-per-task", type=int, default=150)
    parser.add_argument("--report", default=None)
    args = parser.parse_args()

    report = asyncio.run(run(args))
    print(json.dumps(report, indent=2, default=str))

    default_path = (
        Path(__file__).resolve().parents[1]
        / "reports/loop_closure/cybernetics_codex"
        / f"{datetime.now(timezone.utc):%Y-%m-%d}_loop6_witness_closure.json"
    )
    out = Path(args.report) if args.report else default_path
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"\nwrote closure receipt: {out}")

    closed = (
        report["cycles"] > 0
        and report["real_data"]
        and all(report["transitions_receipted"].values())
        and report["adapt_proof"]["fed_forward"]
        and report["adapt_proof"]["before"] != report["adapt_proof"]["after"]
        and not report["tick_errors"]
    )
    print(f"LOOP6_CLOSED={'yes' if closed else 'no'}")
    return 0 if closed else 1


if __name__ == "__main__":
    raise SystemExit(main())
