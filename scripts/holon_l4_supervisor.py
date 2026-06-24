#!/usr/bin/env python3
"""Render review-only launchd/tmux supervisor artifacts for an L4 HOLON service."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dharma_swarm.holon_bridge import AGENTS_ROOT  # noqa: E402
from dharma_swarm.holon_l4_supervisor import (  # noqa: E402
    build_holon_l4_supervisor_plan,
    write_holon_l4_supervisor_plan,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", nargs="?", default="codex_composer")
    parser.add_argument("--mode", choices=["launchd", "tmux"], required=True)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--agents-root", type=Path, default=AGENTS_ROOT)
    parser.add_argument(
        "--memory-receipt-path",
        type=Path,
        default=Path("reports/sovereign_holons/l4_memory_write_receipts.jsonl"),
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--label", default=None)
    parser.add_argument("--tmux-session", default=None)
    parser.add_argument("--session-id", default="")
    parser.add_argument("--lease-seconds", type=int, default=900)
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--forever", action="store_true", default=True)
    parser.add_argument("--oneshot", action="store_false", dest="forever")
    parser.add_argument("--interval-seconds", type=float, default=60.0)
    parser.add_argument("--lock-path", type=Path, default=None)
    parser.add_argument(
        "--live-model-probe",
        action="store_true",
        help="include the live model probe flag; execution still requires the service to be started later",
    )
    parser.add_argument("--model-probe-first-cycle-only", action="store_true")
    parser.add_argument("--model-probe-timeout-seconds", type=int, default=120)
    parser.add_argument(
        "--model-probe-message",
        default="Reply with one short sentence confirming you are responsive as this holon.",
    )
    parser.add_argument("--allow-subprocess-model-probe", action="store_true")
    parser.add_argument("--safe-subprocess-model-probe", action="store_true")
    parser.add_argument("--safe-subprocess-probe-cwd", type=Path, default=None)
    parser.add_argument("--model-probe-lease-id", default="")
    parser.add_argument("--model-probe-lease-path", type=Path, default=None)
    parser.add_argument("--transport-agent-uid", default="")
    parser.add_argument("--transport-heartbeat-path", type=Path, default=None)
    parser.add_argument("--transport-fresh-after-seconds", type=int, default=3600)
    parser.add_argument("--require-transport-reachable", action="store_true")
    parser.add_argument("--enable-orchestration-probe", action="store_true")
    parser.add_argument("--require-orchestration", action="store_true")
    parser.add_argument(
        "--orchestration-execution-mode",
        choices=["dispatch_aggregation_probe", "bounded_subtask_execution"],
        default="dispatch_aggregation_probe",
    )
    parser.add_argument("--orchestration-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--orchestration-min-subtasks", type=int, default=2)
    parser.add_argument("--orchestration-min-model-tiers", type=int, default=2)
    parser.add_argument(
        "--deterministic-orchestration-plan",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--use-readonly-swarm-manager-orchestrator", action="store_true")
    parser.add_argument("--orchestration-state-dir", type=Path, default=None)
    parser.add_argument("--python-executable", default=None)
    parser.add_argument(
        "--write",
        action="store_true",
        help="write review artifacts to --output-dir or the default holon supervisor directory",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    plan = build_holon_l4_supervisor_plan(
        name=args.name,
        mode=args.mode,
        repo_root=args.repo_root,
        agents_root=args.agents_root,
        memory_receipt_path=args.memory_receipt_path,
        output_dir=args.output_dir,
        label=args.label,
        tmux_session=args.tmux_session,
        lease_seconds=args.lease_seconds,
        cycles=args.cycles,
        forever=args.forever,
        interval_seconds=args.interval_seconds,
        lock_path=args.lock_path,
        session_id=args.session_id,
        live_model_probe=args.live_model_probe,
        model_probe_first_cycle_only=args.model_probe_first_cycle_only,
        model_probe_timeout_seconds=args.model_probe_timeout_seconds,
        model_probe_message=args.model_probe_message,
        allow_subprocess_model_probe=args.allow_subprocess_model_probe,
        safe_subprocess_model_probe=args.safe_subprocess_model_probe,
        safe_subprocess_probe_cwd=args.safe_subprocess_probe_cwd,
        model_probe_lease_id=args.model_probe_lease_id,
        model_probe_lease_path=args.model_probe_lease_path,
        transport_agent_uid=args.transport_agent_uid,
        transport_heartbeat_path=args.transport_heartbeat_path,
        transport_fresh_after_seconds=args.transport_fresh_after_seconds,
        require_transport_reachable=args.require_transport_reachable,
        enable_orchestration_probe=args.enable_orchestration_probe,
        require_orchestration=args.require_orchestration,
        orchestration_execution_mode=args.orchestration_execution_mode,
        orchestration_timeout_seconds=args.orchestration_timeout_seconds,
        orchestration_min_subtasks=args.orchestration_min_subtasks,
        orchestration_min_model_tiers=args.orchestration_min_model_tiers,
        deterministic_orchestration_plan=args.deterministic_orchestration_plan,
        use_readonly_swarm_manager_orchestrator=(
            args.use_readonly_swarm_manager_orchestrator
        ),
        orchestration_state_dir=args.orchestration_state_dir,
        python_executable=args.python_executable,
    )
    if args.write or args.output_dir is not None:
        plan = write_holon_l4_supervisor_plan(plan)
    print(json.dumps(plan.model_dump(mode="json"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
