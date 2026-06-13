#!/usr/bin/env python3
"""Strict readiness gate for the file-native A2A task queue."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dharma_swarm.operator_core.a2a_task_lifecycle import (
    queue_path,
    read_queue,
    task_lifecycle_state,
)


@dataclass(frozen=True)
class A2AReadinessReport:
    queue_path: str
    gate_status: str
    ready: bool
    total_tasks: int
    open_tasks: int
    unverified_closed_tasks: int
    unknown_status_tasks: int
    reasons: list[str]
    tasks: list[dict[str, Any]]


def evaluate_a2a_readiness(
    state_root: Path | str | None = None,
    *,
    require_artifact_or_evidence: bool = False,
) -> A2AReadinessReport:
    path = queue_path(state_root)
    if not path.exists():
        return A2AReadinessReport(
            queue_path=str(path),
            gate_status="DEGRADED",
            ready=False,
            total_tasks=0,
            open_tasks=0,
            unverified_closed_tasks=0,
            unknown_status_tasks=0,
            reasons=["queue_missing"],
            tasks=[],
        )

    rows = read_queue(state_root)
    task_reports: list[dict[str, Any]] = []
    reasons: list[str] = []
    open_tasks = 0
    unverified_closed_tasks = 0
    unknown_status_tasks = 0

    for row in rows:
        task_id = str(row.get("id") or "")
        status = str(row.get("status") or "pending").lower()
        lifecycle = task_lifecycle_state(
            row,
            require_artifact_or_evidence=require_artifact_or_evidence,
        )
        state = str(lifecycle.get("state") or "")
        closed = bool(lifecycle.get("closed"))
        verified = bool(lifecycle.get("verified"))
        if not closed:
            open_tasks += 1
        elif not verified:
            unverified_closed_tasks += 1
        if state.endswith("_unknown"):
            unknown_status_tasks += 1
        task_reports.append(
            {
                "id": task_id,
                "status": status,
                "lifecycle_state": state,
                "closed": closed,
                "verified": verified,
            }
        )

    if open_tasks:
        reasons.append("open_or_claimed_tasks_present")
    if unverified_closed_tasks:
        reasons.append("unverified_closed_tasks_present")
    if unknown_status_tasks:
        reasons.append("unknown_status_tasks_present")

    ready = not reasons
    return A2AReadinessReport(
        queue_path=str(path),
        gate_status="READY" if ready else "DEGRADED",
        ready=ready,
        total_tasks=len(rows),
        open_tasks=open_tasks,
        unverified_closed_tasks=unverified_closed_tasks,
        unknown_status_tasks=unknown_status_tasks,
        reasons=reasons,
        tasks=task_reports,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", default=None, help="State root; defaults to ~/.dharma")
    parser.add_argument("--strict", action="store_true", help="Exit nonzero unless gate_status is READY")
    parser.add_argument(
        "--require-artifact-or-evidence",
        action="store_true",
        help="Require closed receipts to carry an artifact, evidence, or evaluation block",
    )
    args = parser.parse_args(argv)

    report = evaluate_a2a_readiness(
        args.state_root,
        require_artifact_or_evidence=args.require_artifact_or_evidence,
    )
    print(json.dumps(asdict(report), indent=2, sort_keys=True))
    if args.strict and not report.ready:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
