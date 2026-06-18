#!/usr/bin/env python3
"""Loop 1 closure run — drive real tasks through the full orchestrator path.

Boots a SwarmManager in bounded/read-only boot mode, spawns only the requested
agents on a real provider lane (Ollama by default — keyless, local), submits N
tasks, and ticks the swarm until every task reaches a terminal state. Execution
runs with DHARMA_SPINE_DISPATCH=1 so each dispatch emits exactly one
EvidenceReceipt through the spine's blessed path (orchestrator._run_task_via_spine).

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
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("DHARMA_SPINE_DISPATCH", "1")
os.environ.setdefault("DHARMA_READ_ONLY_BOOT", "1")
os.environ.setdefault("OLLAMA_FORCE_LOCAL", "1")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")

from dharma_swarm.models import AgentRole, ProviderType, TaskPriority, TaskStatus

TERMINAL = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}

TASK_PROMPTS = [
    "Summarize in two sentences why feedback loops need both sensing and acting.",
    "Name three failure modes of a distributed task queue and one mitigation each.",
    "State one concise principle for retrying transient failures with exponential backoff.",
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
                "requires_tooling": False,
                "task_type": "loop1_closure",
                "timeout_seconds": args.timeout_per_task,
            },
        )
        task_ids.append(task.id)

    deadline = time.monotonic() + args.timeout_per_task * args.tasks
    receipts: dict[str, str] = {}
    tick_errors: list[dict[str, str]] = []
    ticks = 0
    while time.monotonic() < deadline:
        try:
            await swarm.tick()
        except Exception as exc:  # noqa: BLE001 - report proof gaps, do not hide them
            tick_errors.append(
                {
                    "type": type(exc).__name__,
                    "error": str(exc)[:500],
                }
            )
            await asyncio.sleep(args.tick_sleep)
            continue
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
    provider_truth = _read_served_provider_truth(Path(state_dir))
    report = {
        "provider": provider_type.value,
        "model": args.model,
        "spine_dispatch": os.environ.get("DHARMA_SPINE_DISPATCH"),
        "read_only_boot": os.environ.get("DHARMA_READ_ONLY_BOOT"),
        "ollama_force_local": os.environ.get("OLLAMA_FORCE_LOCAL"),
        "agents": len(agents),
        "tasks_requested": args.tasks,
        "tasks_completed": completed,
        "tasks_failed": sum(1 for e in tasks_out if e["status"] == "failed"),
        "dispatch_dropoffs": dropoffs,
        "served_provider_truth": provider_truth,
        "evidence_receipts": receipts,
        "tick_errors": tick_errors,
        "ticks": ticks,
        "stigmergy_hot_paths": hot_paths,
        "state_dir": str(state_dir),
        "tasks": tasks_out,
    }
    await swarm.shutdown()
    return report


def _read_served_provider_truth(state_dir: Path) -> dict[str, object]:
    db_path = state_dir / "state" / "runtime.db"
    out: dict[str, object] = {
        "runtime_db": str(db_path),
        "exists": db_path.exists(),
        "completed_runs_with_truth": 0,
        "delegation_receipts_with_truth": 0,
        "runtime_receipts_with_truth": 0,
        "sample": None,
    }
    if not db_path.exists():
        return out
    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2.0) as conn:
            conn.row_factory = sqlite3.Row
            cols = {
                row[1] for row in conn.execute("pragma table_info(delegation_runs)")
            }
            if "status" in cols and (
                "metadata_json" in cols or "receipt_json" in cols
            ):
                select_cols = ["run_id", "status"]
                select_cols.append(
                    "metadata_json" if "metadata_json" in cols else "null as metadata_json"
                )
                select_cols.append(
                    "receipt_json" if "receipt_json" in cols else "null as receipt_json"
                )
                for row in conn.execute(
                    f"select {', '.join(select_cols)} from delegation_runs "
                    "where status='completed'"
                ):
                    metadata_truth = _served_truth(json.loads(row["metadata_json"] or "{}"))
                    receipt_truth = _served_truth(json.loads(row["receipt_json"] or "{}"))
                    truth = metadata_truth or receipt_truth
                    if truth:
                        out["completed_runs_with_truth"] = int(out["completed_runs_with_truth"]) + 1
                        if receipt_truth:
                            out["delegation_receipts_with_truth"] = int(out["delegation_receipts_with_truth"]) + 1
                        out["sample"] = {
                            "source": "metadata_json" if metadata_truth else "receipt_json",
                            "run_id": row["run_id"],
                            **truth,
                        }
            cols = {
                row[1] for row in conn.execute("pragma table_info(runtime_receipts)")
            }
            if "payload_json" in cols:
                for row in conn.execute(
                    """
                    select receipt_id, run_id, payload_json
                    from runtime_receipts
                    """
                ):
                    truth = _served_truth(json.loads(row["payload_json"] or "{}"))
                    if truth:
                        out["runtime_receipts_with_truth"] = int(out["runtime_receipts_with_truth"]) + 1
                        out["sample"] = {
                            "receipt_id": row["receipt_id"],
                            "run_id": row["run_id"],
                            **truth,
                        }
    except (sqlite3.Error, json.JSONDecodeError) as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def _served_truth(payload: object) -> dict[str, str] | None:
    if not isinstance(payload, dict):
        return None
    provider = str(
        payload.get("actual_served_provider")
        or payload.get("served_provider")
        or payload.get("provider")
        or ""
    ).strip()
    model = str(
        payload.get("actual_served_model")
        or payload.get("served_model")
        or payload.get("model")
        or ""
    ).strip()
    if provider and model and provider != "orchestrator":
        return {"served_provider": provider, "served_model": model}
    for value in payload.values():
        if isinstance(value, dict):
            truth = _served_truth(value)
            if truth:
                return truth
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=int, default=1)
    parser.add_argument("--agents", type=int, default=1)
    parser.add_argument("--provider", default=ProviderType.OLLAMA.value)
    parser.add_argument("--model", default=os.environ.get("OLLAMA_LOCAL_MODEL", "llama3.2:latest"))
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
        and not report["tick_errors"]
        and bool(report["evidence_receipts"])
        and (
            int(report["served_provider_truth"]["completed_runs_with_truth"]) > 0
            or int(report["served_provider_truth"]["runtime_receipts_with_truth"]) > 0
        )
    )
    print(f"\nLOOP1_CLOSED={'yes' if closed else 'no'}")
    return 0 if closed else 1


if __name__ == "__main__":
    raise SystemExit(main())
