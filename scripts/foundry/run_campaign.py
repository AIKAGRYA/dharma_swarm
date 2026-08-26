#!/usr/bin/env python3
"""Operator entrypoint for Sublimation Foundry campaigns.

Subcommands:

    preflight <target>   Report readiness: isolation, provider keys, budget.
    dry-run   <target>   Run the loop hermetically (no keys/network) and print
                         the campaign result as JSON — proves the pipeline.
    run-real  <target>   The REAL campaign: pin the target, baseline its own
                         oracle under isolation, run the live army, mint
                         receipts whose digests/isolation are measured, never
                         asserted. Docker required for promotion-grade runs.
    metrics / guardian / report-card — standing kill-metrics and receipt views.

This script never merges, never sends anything external, and never trades.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict

# Allow running as a plain script from the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import glob  # noqa: E402
import json as _json  # noqa: E402

from dharma_swarm.foundry.campaign import CampaignConfig, dry_run_campaign  # noqa: E402
from dharma_swarm.foundry.guardian_feed import build_guardian_receipt, count_quorum  # noqa: E402
from dharma_swarm.foundry.kill_metrics import (  # noqa: E402
    evaluate_kill_metrics,
    render_walking_brief,
    snapshot_json,
)
from dharma_swarm.foundry.runner_isolation import docker_available  # noqa: E402
from dharma_swarm.foundry.targets import TARGET_REGISTRY, assert_contributable  # noqa: E402

_PROVIDER_KEYS = {
    "OpenRouter": "OPENROUTER_API_KEY",
    "Groq": "GROQ_API_KEY",
    "Cerebras": "CEREBRAS_API_KEY",
    "NVIDIA NIM": "NVIDIA_NIM_API_KEY",
}


def _resolve(target: str):
    spec = TARGET_REGISTRY.get(target)
    if spec is None:
        raise SystemExit(
            f"unknown target '{target}'. known: {', '.join(sorted(TARGET_REGISTRY))}"
        )
    return spec


def cmd_preflight(args: argparse.Namespace) -> int:
    spec = _resolve(args.target)
    assert_contributable(spec)
    keys_present = {name: bool(os.environ.get(env)) for name, env in _PROVIDER_KEYS.items()}
    report = {
        "target": spec.id,
        "ai_policy": spec.ai_policy,
        "license": spec.license,
        "evolve_paths": spec.evolve_paths,
        "strong_isolation_available": docker_available(),
        "provider_keys_present": keys_present,
        "free_lanes_ready": any(
            keys_present[k] for k in ("OpenRouter", "Groq", "Cerebras", "NVIDIA NIM")
        ),
        "note": (
            "strong_isolation_available must be true before any promotion (ring 2/3); "
            "without provider keys the army runs free lanes only."
        ),
    }
    print(json.dumps(report, indent=2))
    return 0


def cmd_dry_run(args: argparse.Namespace) -> int:
    spec = _resolve(args.target)
    config = CampaignConfig(
        generations=args.generations,
        per_generation=args.per_generation,
        strategy=args.strategy,
        budget_cap_usd=args.budget,
    )
    state_root = args.state_root if getattr(args, "state_root", None) else None
    result = dry_run_campaign(spec, config=config, state_root=state_root)
    print(json.dumps(asdict(result), indent=2))
    return 0


def cmd_run_real(args: argparse.Namespace) -> int:
    """The REAL campaign: pin the target, baseline its oracle, run the army.

    Everything the receipts assert is measured here: the pinned tree digest,
    the resolved SHA, the actual isolation level, and metered proposer spend.
    Without Docker the run is degraded (explore-only, promotion blocked) and
    requires --allow-degraded to proceed.
    """
    from pathlib import Path

    from dharma_swarm.foundry.campaign import run_campaign  # noqa: PLC0415
    from dharma_swarm.foundry.live import estimate_cost_usd  # noqa: PLC0415
    from dharma_swarm.foundry.oracle_evaluator import (  # noqa: PLC0415
        OracleEvaluator,
        sentinel_metrics_parser,
    )
    from dharma_swarm.foundry.real_proposer import real_proposer  # noqa: PLC0415
    from dharma_swarm.foundry.runner_isolation import IsolationPolicy  # noqa: PLC0415
    from dharma_swarm.foundry.target_ingest import ingest  # noqa: PLC0415

    spec = _resolve(args.target)
    assert_contributable(spec)

    docker_ok = docker_available()
    if not docker_ok and not args.allow_degraded:
        raise SystemExit(
            "docker (--network none) unavailable: promotion would be impossible. "
            "Pass --allow-degraded to explore anyway (ring 2/3 stays blocked)."
        )

    local_source = Path(args.local_source) if args.local_source else None
    pinned = ingest(spec, local_source=local_source)

    evolve_file = args.evolve_file
    if not evolve_file:
        first = (spec.evolve_paths or [""])[0]
        if not first or first.endswith("/"):
            raise SystemExit("target evolve scope is a directory; pass --evolve-file")
        evolve_file = first

    policy = IsolationPolicy(
        timeout_s=args.timeout,
        docker_image=spec.docker_image or "python:3.11-slim",
        readonly_workdir=args.readonly,
    )

    def _make_eval(eid: str, cmd) -> OracleEvaluator:
        ev = OracleEvaluator(
            evaluator_id=eid, pinned_root=Path(pinned.root), oracle_cmd=cmd,
            evolve_paths=spec.evolve_paths, metric_parser=sentinel_metrics_parser(),
            policy=policy, docker_ok=docker_ok,
        )
        ev.prepare()  # baseline; raises if the target is broken
        return ev

    evaluator = _make_eval(f"oracle:{spec.id}", spec.oracle_cmd)
    baseline = evaluator.baseline.primary_score if evaluator.baseline else 0.0

    heldout = {}
    if args.heldout_cmd:
        heldout["heldout"] = _make_eval(f"heldout:{spec.id}", ["bash", "-c", args.heldout_cmd])
    else:
        print("WARNING: no --heldout-cmd; ring 2 is skipped and NO receipts will be minted.",
              file=sys.stderr)

    propose = real_proposer(
        target_id=spec.id, pinned_root=Path(pinned.root),
        evolve_file=evolve_file, objective=args.objective,
    )

    config = CampaignConfig(
        generations=args.generations, per_generation=args.per_generation,
        strategy=args.strategy, budget_cap_usd=args.budget,
        baseline_metric=baseline,
    )
    result = run_campaign(
        spec, evaluator, propose,
        heldout_evaluators=heldout, config=config,
        state_root=args.state_root,
        tree_digest=pinned.tree_digest, resolved_sha=pinned.resolved_sha,
        isolation_level=evaluator.last_isolation_level or "local_restricted",
    )

    usage = getattr(propose, "usage", {"tokens": 0, "calls": 0})
    provider = getattr(propose, "resolved", {}).get("provider", "none")
    print(json.dumps({
        **asdict(result),
        "baseline_metric": baseline,
        "isolation_level": evaluator.last_isolation_level,
        "promotion_allowed": evaluator.last_promotion_allowed,
        "resolved_sha": pinned.resolved_sha,
        "tree_digest": pinned.tree_digest,
        "proposer_provider": provider,
        "proposer_tokens": usage["tokens"],
        "proposer_est_cost_usd_upper_bound": round(sum(
            estimate_cost_usd(route, tokens)
            for route, tokens in usage.get("tokens_by_provider", {provider: usage["tokens"]}).items()
        ), 6),
    }, indent=2))
    return 0


def cmd_metrics(args: argparse.Namespace) -> int:
    spec = _resolve(args.target)
    result = dry_run_campaign(spec, config=CampaignConfig(generations=args.generations))
    snapshot = evaluate_kill_metrics(
        cohort_survival=result.mean_survival,
        verified_improvements=result.ring2_survivors,
        prior_cohort_survival=args.prior_survival,
    )
    print(render_walking_brief(snapshot))
    print()
    print(snapshot_json(snapshot))
    return 1 if snapshot.any_kill() else 0


def cmd_report_card(args: argparse.Namespace) -> int:
    from dharma_swarm.foundry.report_card import card_from_receipt_file

    print(card_from_receipt_file(args.receipt))
    return 0


def cmd_guardian(args: argparse.Namespace) -> int:
    receipts = []
    for path in sorted(glob.glob(os.path.join(args.receipts_dir, "*.json"))):
        try:
            receipts.append(_json.loads(open(path, encoding="utf-8").read()))
        except (OSError, ValueError):
            continue
    quorum = count_quorum(receipts)
    payload = build_guardian_receipt(receipts)  # never grants authority from the CLI
    print(json.dumps({
        "receipts_scanned": len(receipts),
        "confirmed": quorum.confirmed,
        "domains": quorum.domains,
        "domain_breakdown": quorum.domain_breakdown,
        "eligible": quorum.eligible,
        "guardian_receipt": payload,
        "note": "authority is NEVER granted from the CLI; an operator grants it explicitly.",
    }, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    pf = sub.add_parser("preflight", help="report campaign readiness")
    pf.add_argument("target")
    pf.set_defaults(func=cmd_preflight)

    dr = sub.add_parser("dry-run", help="run the loop hermetically")
    dr.add_argument("target")
    dr.add_argument("--generations", type=int, default=5)
    dr.add_argument("--per-generation", type=int, default=6)
    dr.add_argument("--strategy", default="explore")
    dr.add_argument("--budget", type=float, default=300.0)
    dr.add_argument("--state-root", default=None,
                    help="write receipts here instead of ~/.dharma/foundry")
    dr.set_defaults(func=cmd_dry_run)

    rr = sub.add_parser("run-real", help="REAL campaign: pinned target, real oracle, live army")
    rr.add_argument("target")
    rr.add_argument("--objective", required=True,
                    help="one-line optimization objective fed to the mutation prompt")
    rr.add_argument("--evolve-file", default=None,
                    help="file to evolve (defaults to the target's first evolve path if a file)")
    rr.add_argument("--heldout-cmd", default=None,
                    help="shell command for the ring-2 held-out oracle (sentinel output)")
    rr.add_argument("--generations", type=int, default=5)
    rr.add_argument("--per-generation", type=int, default=6)
    rr.add_argument("--strategy", default="explore")
    rr.add_argument("--budget", type=float, default=300.0)
    rr.add_argument("--timeout", type=float, default=300.0,
                    help="per-oracle-run timeout seconds")
    rr.add_argument("--readonly", action="store_true",
                    help="mount the workdir read-only (tamper prevention instead of detection)")
    rr.add_argument("--allow-degraded", action="store_true",
                    help="proceed without docker (explore-only; promotion blocked)")
    rr.add_argument("--local-source", default=None,
                    help="ingest from a local tree instead of cloning (offline/test)")
    rr.add_argument("--state-root", default=None,
                    help="write receipts here instead of ~/.dharma/foundry")
    rr.set_defaults(func=cmd_run_real)

    mt = sub.add_parser("metrics", help="dry-run + emit kill-metrics / walking brief")
    mt.add_argument("target")
    mt.add_argument("--generations", type=int, default=5)
    mt.add_argument("--prior-survival", type=float, default=None,
                    help="prior cohort survival rate (for two-cohort collapse check)")
    mt.set_defaults(func=cmd_metrics)

    gd = sub.add_parser("guardian", help="report One Wire quorum from a receipts dir")
    gd.add_argument("receipts_dir")
    gd.set_defaults(func=cmd_guardian)

    rc = sub.add_parser("report-card", help="render a report card from a sealed receipt")
    rc.add_argument("receipt")
    rc.set_defaults(func=cmd_report_card)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
