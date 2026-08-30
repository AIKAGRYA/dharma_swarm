"""Forge lab CLI — shadow by construction (``--mode`` parses only "shadow")."""

from __future__ import annotations

import argparse
import asyncio
import json
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
    from dharma_swarm.forge_lab.experiment import ExperimentConfig, run_experiment

    if args.dry_run:
        print("--dry-run is test-harness only; wire Seams in code instead", file=sys.stderr)
        return 2
    if not args.solver_model or not args.mutator_model:
        print("--solver-model and --mutator-model are required for a live run", file=sys.stderr)
        return 2
    cfg = ExperimentConfig(
        generations=args.generations,
        children=args.children,
        tasks_per_generation=args.tasks,
        novelty_pressure=args.novelty_pressure,
        solver_model=args.solver_model,
        verifier_model=args.verifier_model,
        mutator_model=args.mutator_model,
        budget_cap_tokens=args.budget_tokens,
        budget_cap_usd=args.budget_usd,
        soft_token_cap=not args.hard_token_cap,
        require_valid_seed=not args.allow_hard_invalid_seed,
        max_experiment_tokens=args.max_experiment_tokens,
        propose_timeout_s=args.propose_timeout,
        grade_timeout_s=args.grade_timeout,
        rng_seed=args.rng_seed,
        source_repo=Path(args.source_repo),
        keep_worktree=args.keep_worktree,
    )
    try:
        closeout = asyncio.run(run_experiment(cfg))
    except Exception as exc:
        # run_experiment already wrote closeout.json (blocked_with_evidence) and
        # after_run_notes before re-raising; surface the failure and exit non-zero.
        print(f"forge_lab run aborted: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(closeout, indent=2, default=str))
    return 0 if closeout.get("closeout_state") in ("inconclusive_low_power", "measured_negative") else 1


if __name__ == "__main__":
    raise SystemExit(main())
