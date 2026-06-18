#!/usr/bin/env python3
"""Loop 1 closure run — drive real tasks through the full orchestrator path.

Boots a SwarmManager, spawns agents on a real provider lane (Ollama by
default — keyless, local), submits N tasks, and ticks the swarm until every
task reaches a terminal state. Execution runs with DHARMA_SPINE_DISPATCH=1 so
each dispatch emits exactly one EvidenceReceipt through the spine's blessed
path (orchestrator._run_task_via_spine).

Prints a JSON closure report: per-task terminal status, evidence receipt ids,
dispatch_dropoff occurrences, and stigmergy hot paths (the ADAPT half of
Loop 1 — routing in tick N+1 reads outcomes of tick N).

Usage:
    .venv/bin/python scripts/loop1_closure_run.py --tasks 3
    .venv/bin/python scripts/loop1_closure_run.py --tasks 100 --agents 3 \
        --timeout-per-task 240 --report reports/loop_closure/run.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("DHARMA_SPINE_DISPATCH", "1")

from dharma_swarm.models import AgentRole, ProviderType, TaskPriority, TaskStatus

TERMINAL = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}

TASK_PROMPTS = [
    "Summarize in two sentences why feedback loops need both sensing and acting.",
    "Name three failure modes of a distributed task queue and one mitigation each.",
    "Write a one-line docstring for a function that retries with exponential backoff.",
    "Explain the difference between a rate limit and a quota in one paragraph.",
    "List four properties a good evidence receipt should record.",
]


def _task_spec(index: int) -> tuple[str, str]:
    prompt = TASK_PROMPTS[index % len(TASK_PROMPTS)]
    return (f"loop1-closure-{index + 1:04d}", prompt)


async def run(args: argparse.Namespace) -> dict:
    from dharma_swarm.swarm import SwarmManager

    state_dir = args.state_dir or tempfile.mkdtemp(prefix="loop1-closure-")
    swarm = SwarmManager(state_dir=state_dir)
    await swarm.init()

    provider_type = ProviderType(args.provider)
    agents = []
    for i in range(args.agents):
        agent = await swarm.spawn_agent(
            name=f"loop1-agent-{i + 1}",
            role=AgentRole.GENERAL,
            model=args.model,
            provider_type=provider_type,
        )
        agents.append(agent)

    task_ids: list[str] = []
    for i in range(args.tasks):
        title, prompt = _task_spec(i)
        task = await swarm.create_task(
            title=title,
            description=prompt,
            priority=TaskPriority.URGENT,
            metadata={
                "provider_allowlist": [provider_type.value],
                "timeout_seconds": args.timeout_per_task,
            },
        )
        task_ids.append(task.id)

    deadline = time.monotonic() + args.timeout_per_task * args.tasks
    receipts: dict[str, str] = {}
    ticks = 0
    while time.monotonic() < deadline:
        await swarm.tick()
        ticks += 1
        orch = swarm._orchestrator
        receipt = getattr(orch, "_last_evidence_receipt", None)
        if receipt is not None:
            receipts[str(receipt.receipt_id)] = receipt.status
        statuses = {}
        for task_id in task_ids:
            task = await swarm._task_board.get(task_id)
            statuses[task_id] = task.status if task else None
        if all(status in TERMINAL for status in statuses.values()):
            break
        await asyncio.sleep(args.tick_sleep)

    tasks_out = []
    for task_id in task_ids:
        task = await swarm._task_board.get(task_id)
        meta = task.metadata if task and isinstance(task.metadata, dict) else {}
        tasks_out.append(
            {
                "task_id": task_id,
                "title": task.title if task else None,
                "status": task.status.value if task else "missing",
                "failure_source": meta.get("failure_source"),
                "result_preview": (task.result or "")[:160] if task else None,
            }
        )

    hot_paths = []
    try:
        hot_paths = [
            {"path": mark.path, "intensity": round(mark.intensity, 4)}
            for mark in swarm._stigmergy.hot_paths(limit=5)
        ]
    except Exception:
        pass

    dropoffs = sum(
        1 for entry in tasks_out if entry["failure_source"] == "dispatch_dropoff"
    )
    completed = sum(1 for entry in tasks_out if entry["status"] == "completed")
    report = {
        "provider": provider_type.value,
        "model": args.model,
        "spine_dispatch": os.environ.get("DHARMA_SPINE_DISPATCH"),
        "agents": len(agents),
        "tasks_requested": args.tasks,
        "tasks_completed": completed,
        "tasks_failed": sum(1 for e in tasks_out if e["status"] == "failed"),
        "dispatch_dropoffs": dropoffs,
        "evidence_receipts": receipts,
        "ticks": ticks,
        "stigmergy_hot_paths": hot_paths,
        "state_dir": str(state_dir),
        "tasks": tasks_out,
    }
    await swarm.shutdown()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=int, default=1)
    parser.add_argument("--agents", type=int, default=1)
    parser.add_argument("--provider", default=ProviderType.OLLAMA.value)
    parser.add_argument("--model", default="llama3.2")
    parser.add_argument("--timeout-per-task", type=float, default=300.0)
    parser.add_argument("--tick-sleep", type=float, default=1.0)
    parser.add_argument("--state-dir", default=None)
    parser.add_argument("--report", default=None, help="write JSON report here")
    args = parser.parse_args()

    report = asyncio.run(run(args))
    rendered = json.dumps(report, indent=2, default=str)
    print(rendered)
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(rendered + "\n")
    closed = (
        report["tasks_completed"] == report["tasks_requested"]
        and report["dispatch_dropoffs"] == 0
        and bool(report["evidence_receipts"])
    )
    print(f"\nLOOP1_CLOSED={'yes' if closed else 'no'}")
    return 0 if closed else 1


if __name__ == "__main__":
    raise SystemExit(main())
