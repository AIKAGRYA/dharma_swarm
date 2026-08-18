#!/usr/bin/env python3
"""Operator entrypoint for Sublimation Foundry campaigns.

Two subcommands:

    preflight <target>   Report readiness: isolation, provider keys, budget.
    dry-run  <target>    Run the loop hermetically (no keys/network) and print
                         the campaign result as JSON — proves the pipeline.

Live generation (the army calling real models against a pinned external target)
runs from the foundry-lane workflow once provider keys are set as Cloud Agent
secrets; see docs/foundry/OPERATOR_UNBLOCKS.md. This script never merges, never
sends anything external, and never trades.
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

    mt = sub.add_parser("metrics", help="dry-run + emit kill-metrics / walking brief")
    mt.add_argument("target")
    mt.add_argument("--generations", type=int, default=5)
    mt.add_argument("--prior-survival", type=float, default=None,
                    help="prior cohort survival rate (for two-cohort collapse check)")
    mt.set_defaults(func=cmd_metrics)

    gd = sub.add_parser("guardian", help="report One Wire quorum from a receipts dir")
    gd.add_argument("receipts_dir")
    gd.set_defaults(func=cmd_guardian)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
