"""Command line entrypoint for Forge Lab."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dharma_swarm.forge_lab.experiment import run_from_args


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m dharma_swarm.forge_lab.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Run a budget-capped EXPLORE evolution smoke")
    run.add_argument("--experiment-id", required=True)
    run.add_argument("--category", default="agent_evolution", choices=["agent_evolution", "swarm_evolution"])
    run.add_argument("--generations", type=int, default=1)
    run.add_argument("--children", type=int, default=2)
    run.add_argument("--novelty-pressure", type=float, default=0.7)
    run.add_argument("--rng-seed", type=int, default=7)
    run.add_argument("--source-repo", default=str(Path.cwd()))
    run.add_argument("--base-ref", default="origin/main")
    run.add_argument("--archive-root", default=str(Path.home() / ".dharma" / "evolution_archive"))
    run.add_argument("--worktree-root", default="")
    run.add_argument("--taskbed-db", default="")
    run.add_argument("--task-count", type=int, default=0)
    run.add_argument("--max-usd", type=float, default=0.0)
    run.add_argument("--use-taskbed", action="store_true")
    run.add_argument("--keep-worktree", action="store_true")
    # WILD EXPLORE knobs (off by default: deterministic, offline, no spend).
    run.add_argument(
        "--allow-model-calls",
        action="store_true",
        help="Enable the frontier genome proposer (real model calls; budget-capped).",
    )
    run.add_argument("--roster-n", type=int, default=8)
    run.add_argument("--per-call-tokens", type=int, default=3500)
    run.add_argument("--token-budget", type=int, default=120000)
    run.add_argument("--proposer-timeout-s", type=int, default=60)
    return parser


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < (3, 11):
        print("Forge Lab requires Python >=3.11; use ~/dharma_swarm/.venv/bin/python", file=sys.stderr)
        return 2
    args = build_parser().parse_args(argv)
    if args.command == "run":
        result = run_from_args(args)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
