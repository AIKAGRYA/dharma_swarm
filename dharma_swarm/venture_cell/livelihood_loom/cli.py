"""CLI for Livelihood Loom VentureCell projections."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from dharma_swarm.venture_cell.livelihood_loom.ceo_agent import (
    DEFAULT_DHARMA_HOME,
    REPO_ROOT,
    build_external_worker_registration,
    register_livelihood_loom_ceo_sync,
)
from dharma_swarm.venture_cell.livelihood_loom.execution import (
    DEFAULT_ENABLER_CSV,
    bootstrap_summary,
    run_safe_bootstrap,
)
from dharma_swarm.venture_cell.livelihood_loom.demand import build_demand_artifacts
from dharma_swarm.venture_cell.livelihood_loom.enablement_packets import (
    build_enablement_packets,
)
from dharma_swarm.venture_cell.livelihood_loom.evidence import run_cultivation_cycle
from dharma_swarm.venture_cell.livelihood_loom.prioritization import (
    DEFAULT_REPORT_ROOT,
    DEFAULT_TOP_N,
    write_top_50_reports,
)
from dharma_swarm.venture_cell.livelihood_loom.promotion import build_promotion_readiness
from dharma_swarm.venture_cell.livelihood_loom.safety import build_safety_review
from dharma_swarm.venture_cell.livelihood_loom.status import project_readiness


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m dharma_swarm.venture_cell.livelihood_loom.cli")
    subcommands = parser.add_subparsers(dest="command", required=True)
    status = subcommands.add_parser("status", help="Print read-only readiness projection")
    status.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    status.add_argument("--dharma-home", default=str(DEFAULT_DHARMA_HOME))

    register = subcommands.add_parser("register-ceo", help="Register the persistent CEO identity")
    register.add_argument("--dharma-home", default=str(DEFAULT_DHARMA_HOME))
    register.add_argument("--repo-root", default=str(REPO_ROOT))
    register.add_argument("--agents-dir", default="")
    register.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the registration packet without writing",
    )
    register.add_argument(
        "--no-onboarding",
        action="store_true",
        help="Skip canonical living-agent/A2A/telemetry onboarding writes",
    )
    register.add_argument("--json", action="store_true", help="Print machine-readable JSON")

    bootstrap = subcommands.add_parser("run-bootstrap", help="Run a safe local CEO bootstrap cycle")
    bootstrap.add_argument("--dharma-home", default=str(DEFAULT_DHARMA_HOME))
    bootstrap.add_argument("--repo-root", default=str(REPO_ROOT))
    bootstrap.add_argument("--agents-dir", default="")
    bootstrap.add_argument("--candidate-csv", default=str(DEFAULT_ENABLER_CSV))
    bootstrap.add_argument("--candidate-limit", type=int, default=1000)
    bootstrap.add_argument("--top-n", type=int, default=25)
    bootstrap.add_argument("--receipt-dir", default="")
    bootstrap.add_argument("--external-action-log", default="")
    bootstrap.add_argument("--skip-registration", action="store_true")
    bootstrap.add_argument("--no-onboarding", action="store_true")
    bootstrap.add_argument("--json", action="store_true", help="Print full machine-readable JSON")

    top_50 = subcommands.add_parser("top-50", help="Build Top 50 cultivation list")
    top_50.add_argument("--candidate-csv", default=str(DEFAULT_ENABLER_CSV))
    top_50.add_argument("--candidate-limit", type=int, default=1000)
    top_50.add_argument("--top-n", type=int, default=DEFAULT_TOP_N)
    top_50.add_argument("--report-root", default=str(DEFAULT_REPORT_ROOT))
    top_50.add_argument("--json", action="store_true")

    safety = subcommands.add_parser("safety-review", help="Red-team the Top 50")
    safety.add_argument(
        "--top-50",
        default=str(DEFAULT_REPORT_ROOT / "cultivation" / "top_50.json"),
    )
    safety.add_argument("--report-root", default=str(DEFAULT_REPORT_ROOT))
    safety.add_argument("--json", action="store_true")

    packets = subcommands.add_parser("build-packets", help="Build enablement packets")
    packets.add_argument(
        "--safety-review",
        default=str(DEFAULT_REPORT_ROOT / "safety" / "top_50_safety_review.json"),
    )
    packets.add_argument(
        "--wedges",
        default=str(DEFAULT_REPORT_ROOT / "cultivation" / "wedges.json"),
    )
    packets.add_argument("--report-root", default=str(DEFAULT_REPORT_ROOT))
    packets.add_argument("--json", action="store_true")

    demand = subcommands.add_parser("draft-demand", help="Draft offer and sponsor briefs")
    demand.add_argument(
        "--top-50",
        default=str(DEFAULT_REPORT_ROOT / "cultivation" / "top_50.json"),
    )
    demand.add_argument(
        "--safety-review",
        default=str(DEFAULT_REPORT_ROOT / "safety" / "top_50_safety_review.json"),
    )
    demand.add_argument(
        "--wedges",
        default=str(DEFAULT_REPORT_ROOT / "cultivation" / "wedges.json"),
    )
    demand.add_argument(
        "--packets-dir",
        default=str(DEFAULT_REPORT_ROOT / "enablement_packets"),
    )
    demand.add_argument("--report-root", default=str(DEFAULT_REPORT_ROOT))
    demand.add_argument("--dharma-home", default=str(DEFAULT_DHARMA_HOME))
    demand.add_argument("--external-action-log", default="")
    demand.add_argument("--json", action="store_true")

    cycle = subcommands.add_parser(
        "run-cultivation-cycle",
        help="Run the full internal cultivation cycle",
    )
    cycle.add_argument("--candidate-csv", default=str(DEFAULT_ENABLER_CSV))
    cycle.add_argument("--candidate-limit", type=int, default=1000)
    cycle.add_argument("--top-n", type=int, default=DEFAULT_TOP_N)
    cycle.add_argument("--report-root", default=str(DEFAULT_REPORT_ROOT))
    cycle.add_argument("--dharma-home", default=str(DEFAULT_DHARMA_HOME))
    cycle.add_argument("--external-action-log", default="")
    cycle.add_argument("--json", action="store_true")

    promotion = subcommands.add_parser(
        "build-promotion-kit",
        help="Build the internal homepage/promotion approval packet",
    )
    promotion.add_argument("--report-root", default=str(DEFAULT_REPORT_ROOT))
    promotion.add_argument("--dharma-home", default=str(DEFAULT_DHARMA_HOME))
    promotion.add_argument("--external-action-log", default="")
    promotion.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "status":
        readiness = project_readiness(dharma_home=args.dharma_home)
        payload = readiness.to_dict()
        if args.json:
            print(json.dumps(payload, sort_keys=True))
        else:
            print(f"{payload['cell_id']}: {payload['overall_status']}")
            for gate in payload["gates"]:
                print(f"- {gate['name']}: {gate['status']} ({gate['detail']})")
        return 0
    if args.command == "register-ceo":
        home = Path(args.dharma_home).expanduser()
        repo = Path(args.repo_root).expanduser()
        agents_dir = Path(args.agents_dir).expanduser() if args.agents_dir else None
        if args.dry_run:
            worker = build_external_worker_registration(dharma_home=home, repo_root=repo)
            payload = worker.model_dump()
            payload["dry_run"] = True
            payload["would_write"] = {
                "external_registration": str(home / "external_agents" / worker.agent_uid / "registration.json"),
                "living_agent": str(home / "agents" / worker.agent_uid / "living_agent.json"),
                "a2a_card": str(home / "a2a" / "cards" / f"{worker.callsign}.json"),
                "agent_registry_identity": str((agents_dir or home / "ginko" / "agents") / worker.agent_uid / "identity.json"),
            }
        else:
            payload = register_livelihood_loom_ceo_sync(
                dharma_home=home,
                repo_root=repo,
                agents_dir=agents_dir,
                write_canonical_onboarding=not args.no_onboarding,
            )
        if args.json or args.dry_run:
            print(json.dumps(payload, indent=2, ensure_ascii=True, default=str))
        else:
            print(f"registered livelihood_loom_ceo at {payload['agent_registry_path']}")
        return 0
    if args.command == "run-bootstrap":
        receipt = run_safe_bootstrap(
            dharma_home=args.dharma_home,
            repo_root=args.repo_root,
            agents_dir=args.agents_dir or None,
            candidate_csv=args.candidate_csv or None,
            candidate_limit=args.candidate_limit,
            top_n=args.top_n,
            receipt_dir=args.receipt_dir or None,
            external_action_log=args.external_action_log or None,
            write_canonical_onboarding=not args.no_onboarding,
            register_ceo=not args.skip_registration,
        )
        payload = receipt if args.json else bootstrap_summary(receipt)
        print(json.dumps(payload, indent=2, ensure_ascii=True, default=str))
        return 0
    if args.command == "top-50":
        payload = write_top_50_reports(
            candidate_csv=args.candidate_csv,
            report_root=args.report_root,
            candidate_limit=args.candidate_limit,
            top_n=args.top_n,
        )
        print(json.dumps(payload, indent=2, ensure_ascii=True, default=str))
        return 0
    if args.command == "safety-review":
        payload = build_safety_review(
            top_50_path=args.top_50,
            report_root=args.report_root,
        )
        print(json.dumps(payload, indent=2, ensure_ascii=True, default=str))
        return 0
    if args.command == "build-packets":
        payload = build_enablement_packets(
            safety_review_path=args.safety_review,
            wedges_path=args.wedges,
            report_root=args.report_root,
        )
        print(json.dumps(payload, indent=2, ensure_ascii=True, default=str))
        return 0
    if args.command == "draft-demand":
        payload = build_demand_artifacts(
            top_50_path=args.top_50,
            safety_review_path=args.safety_review,
            wedges_path=args.wedges,
            packets_dir=args.packets_dir,
            report_root=args.report_root,
            dharma_home=args.dharma_home,
            external_action_log=args.external_action_log or None,
        )
        print(json.dumps(payload, indent=2, ensure_ascii=True, default=str))
        return 0
    if args.command == "run-cultivation-cycle":
        payload = run_cultivation_cycle(
            candidate_csv=args.candidate_csv,
            candidate_limit=args.candidate_limit,
            top_n=args.top_n,
            report_root=args.report_root,
            dharma_home=args.dharma_home,
            external_action_log=args.external_action_log or None,
        )
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=True, default=str))
        else:
            print(
                json.dumps(
                    {
                        "receipt_id": payload["receipt_id"],
                        "status": payload["status"],
                        "latest_path": payload["latest_path"],
                    },
                    indent=2,
                    ensure_ascii=True,
                )
            )
        return 0
    if args.command == "build-promotion-kit":
        payload = build_promotion_readiness(
            report_root=args.report_root,
            dharma_home=args.dharma_home,
            external_action_log=args.external_action_log or None,
        )
        print(json.dumps(payload, indent=2, ensure_ascii=True, default=str))
        return 0
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
