#!/usr/bin/env python3
"""Run the bounded shadow Evolution Foundry.

This CLI generates deterministic sandbox variants, records recursive-discovery
receipts, archives lineage, and never applies candidate diffs to the live repo.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from dharma_swarm.event_log import EventLog
from dharma_swarm.recursive_discovery import run_shadow_evolution_foundry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run no-apply recursive shadow variants")
    parser.add_argument("--session-id", default="recursive-shadow-foundry")
    parser.add_argument("--task-id", default="")
    parser.add_argument("--trace-id", default=None)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--event-log-dir", type=Path, default=None)
    parser.add_argument("--sandbox-root", type=Path, default=None)
    parser.add_argument("--archive-path", type=Path, default=None)
    parser.add_argument("--variants", type=int, default=10)
    parser.add_argument("--proof-timeout", type=float, default=60.0)
    parser.add_argument("--report-path", type=Path, default=None)
    return parser


async def _run(args: argparse.Namespace) -> int:
    event_log = EventLog(args.event_log_dir) if args.event_log_dir is not None else EventLog()
    result = await run_shadow_evolution_foundry(
        session_id=args.session_id,
        task_id=args.task_id,
        repo_root=args.repo_root,
        sandbox_root=args.sandbox_root,
        archive_path=args.archive_path,
        event_log=event_log,
        variant_count=args.variants,
        proof_timeout=args.proof_timeout,
        trace_id=args.trace_id,
    )
    report = result.to_report()
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report_path is not None:
        args.report_path.parent.mkdir(parents=True, exist_ok=True)
        args.report_path.write_text(payload, encoding="utf-8")
    print(payload, end="")
    promoted = any(decision == "promote_to_pr" for decision in report["promotion_decisions"])
    return 1 if promoted or report["receipt_count"] == 0 else 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
