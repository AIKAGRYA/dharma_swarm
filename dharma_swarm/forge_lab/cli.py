"""Retired legacy Forge experiment CLI.

Scientific seams remain importable for tests, but the old direct live launcher
cannot satisfy campaign fencing, checkpoint, or spend-authority contracts and
therefore fails closed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="forge_lab", description="Forge v3 EXPLORE chassis")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run one EXPLORE experiment")
    run.add_argument("--mode", choices=["shadow"], default="shadow")
    run.add_argument("--category", choices=["agent"], default="agent")
    run.add_argument("--generations", type=int, default=2)
    run.add_argument("--children", type=int, default=3, help="TOTAL children per generation")
    run.add_argument("--tasks", type=int, default=3, help="explore tasks per generation")
    run.add_argument("--novelty-pressure", type=float, default=0.7)
    run.add_argument("--solver-model", default="", help="seed genome generator (model_pool id)")
    run.add_argument("--verifier-model", default="")
    run.add_argument("--mutator-model", default="", help="the mutation operator's model")
    run.add_argument("--budget-tokens", type=int, default=120_000, help="per candidate-grade cap")
    run.add_argument("--budget-usd", type=float, default=2.0)
    run.add_argument(
        "--hard-token-cap",
        action="store_true",
        help="legacy behavior: token overage invalidates candidates instead of being measured as explore-open compute",
    )
    run.add_argument(
        "--allow-hard-invalid-seed",
        action="store_true",
        help="continue even if the seed baseline hits a hard invalid budget condition",
    )
    run.add_argument("--max-experiment-tokens", type=int, default=600_000)
    run.add_argument("--propose-timeout", type=int, default=240)
    run.add_argument("--grade-timeout", type=int, default=600)
    run.add_argument("--rng-seed", type=int, default=20260706)
    run.add_argument("--source-repo", default=str(Path.home() / "dharma_swarm"))
    run.add_argument("--keep-worktree", action="store_true")
    run.add_argument("--dry-run", action="store_true", help="no worktree/network; injected fakes only (tests)")
    return parser


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < (3, 11):
        print(
            "forge_lab requires Python >= 3.11 — use ~/dharma_swarm/.venv/bin/python",
            file=sys.stderr,
        )
        return 2
    args = build_parser().parse_args(argv)
    if args.dry_run:
        print("--dry-run is test-harness only; wire Seams in code instead", file=sys.stderr)
        return 2
    print(
        "GOVERNED_CAMPAIGN_REQUIRED: direct forge_lab.cli execution is retired; "
        "use rsi campaign plan/run with a content-addressed manifest",
        file=sys.stderr,
    )
    return 7


if __name__ == "__main__":
    raise SystemExit(main())
